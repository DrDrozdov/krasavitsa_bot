import importlib
import os
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock


os.environ.setdefault("BOT_TOKEN", "123:ABC")
bot = importlib.import_module("bot")


def test_offtopic_travel_request_is_not_cosmetic():
    assert not bot.is_cosmetic_request("Хочу в Москву")


def test_smalltalk_is_not_cosmetic():
    assert not bot.is_cosmetic_request("как дела?")


def test_short_cosmetic_requests_are_allowed():
    assert bot.is_cosmetic_request("акне")
    assert bot.is_cosmetic_request("spf")
    assert bot.is_cosmetic_request("сухая кожа")


def test_full_cosmetic_request_is_allowed():
    assert bot.is_cosmetic_request(
        "Комбинированная кожа, жирный блеск в Т-зоне, хочу уход до 3000"
    )


def test_offtopic_reply_is_friendly_and_has_smile():
    reply = bot.build_offtopic_reply()

    assert "🙂" in reply
    assert "косметике" in reply
    assert "ароматах" in reply
    assert bot.WEBSITE_URL in reply


def test_thanks_reply_uses_feminine_voice():
    assert bot.is_thanks_message("спасибо")
    assert bot.build_thanks_reply().startswith("Рада помочь")


def test_website_note_points_to_project_site():
    assert bot.WEBSITE_URL == "https://krasavitsa-ai.ru/"
    assert bot.WEBSITE_URL in bot.build_website_note()


def test_website_keyboard_points_to_project_site():
    keyboard = bot.website_keyboard()

    assert keyboard.inline_keyboard[0][0].url == bot.WEBSITE_URL


def test_command_fallback_never_sends_unknown_command_to_ai():
    message = SimpleNamespace(
        text="/pick",
        from_user=SimpleNamespace(id=77, username="tester"),
        answer=AsyncMock(),
    )

    asyncio.run(bot.handle_text(message))

    message.answer.assert_awaited_once()
    assert "Красавица" in message.answer.await_args.args[0]
