import asyncio
import importlib
import os
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update


os.environ.setdefault("BOT_TOKEN", "123:ABC")
bot_module = importlib.import_module("bot")


class CaptureSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.methods = []

    async def close(self):
        return None

    async def make_request(self, bot, method, timeout=None):
        self.methods.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=100 + len(self.methods),
                date=datetime.now(timezone.utc),
                chat=Chat(id=1, type="private"),
                text=method.text,
            ).as_(bot)
        return True

    async def stream_content(self, *_args, **_kwargs):
        if False:
            yield b""


def test_pick_command_is_routed_to_menu_without_ai(monkeypatch):
    session = CaptureSession()
    test_bot = Bot(token="123:ABC", session=session)
    monkeypatch.setattr(bot_module, "save_user", lambda **_kwargs: None)
    monkeypatch.setattr(bot_module, "ask_deepseek", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("AI must not be called")))
    update = Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=Chat(id=1, type="private"),
            from_user={"id": 77, "is_bot": False, "first_name": "Test"},
            text="/pick",
        ),
    )

    asyncio.run(bot_module.dp.feed_update(test_bot, update))

    sent_messages = [method for method in session.methods if isinstance(method, SendMessage)]
    assert len(sent_messages) == 2
    assert sent_messages[0].reply_markup.remove_keyboard is True
    assert "Что подбираем?" in sent_messages[1].text
    assert sent_messages[1].reply_markup.inline_keyboard[0][0].callback_data == "mode:skin"
