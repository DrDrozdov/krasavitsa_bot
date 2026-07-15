import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot


def test_direct_mode_waits_for_user_text_instead_of_starting_search(monkeypatch):
    callback = SimpleNamespace(
        data="direct:skin",
        from_user=SimpleNamespace(id=77),
        message=SimpleNamespace(),
        answer=AsyncMock(),
    )
    state = SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())
    search = AsyncMock()
    render = AsyncMock()
    monkeypatch.setattr(bot, "run_callback_search", search)
    monkeypatch.setattr(bot, "render_panel", render)
    monkeypatch.setattr(bot, "save_user_beauty_state", lambda *_args, **_kwargs: None)

    asyncio.run(bot.callback_direct(callback, state))

    search.assert_not_awaited()
    state.set_state.assert_awaited_once_with(bot.InputState.free_request)
    state.update_data.assert_awaited_once_with(mode="skin")
    render.assert_awaited_once()
    assert "не начну поиск" in render.await_args.args[1].lower()
