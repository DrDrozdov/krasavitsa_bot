import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import beauty_flow
from beauty_flow import (
    FLOW_STEPS,
    all_callback_data,
    build_query,
    choose_option,
    main_text,
    previous_step,
    serialize_answers,
    skip_step,
    start_flow,
)


def test_start_screen_names_all_three_directions():
    text = main_text().lower()
    assert "кож" in text
    assert "волос" in text
    assert "парфюм" in text


def test_perfume_flow_supports_gender_and_no_preference():
    options = FLOW_STEPS["perfume"][0].options
    assert {option.value for option in options} == {"female", "male", "unisex", "any"}


def test_perfume_flow_can_finish_with_no_answers():
    session = start_flow(9001, "perfume")
    for step_index in range(len(FLOW_STEPS["perfume"])):
        session, complete = skip_step(9001, "perfume", step_index)
    assert complete
    query = build_query(session, "perfume", exploratory=True)
    assert "не знает точных предпочтений" in query.lower()
    assert "не блокируй" in query.lower()


def test_selected_options_are_included_in_search_query():
    start_flow(9002, "perfume")
    session, _ = choose_option(9002, "perfume", 0, "unisex")
    session, _ = choose_option(9002, "perfume", 1, "woody")
    query = build_query(session, "perfume")
    assert "Унисекс" in query
    assert "Древесный" in query


def test_hair_flow_covers_type_scalp_and_length_state():
    keys = {step.key for step in FLOW_STEPS["hair"]}
    assert {"focus", "hair_type", "scalp_type", "hair_state", "budget"} <= keys


def test_going_back_preserves_selected_answers():
    start_flow(9003, "skin")
    session, _ = choose_option(9003, "skin", 0, "dry")
    session, _ = choose_option(9003, "skin", 1, "combo")
    session = previous_step(9003, "skin", 2)
    assert serialize_answers(session) == {"goal": "dry", "skin_type": "combo"}


def test_every_callback_data_fits_telegram_limit():
    assert all(len(value.encode("utf-8")) <= 64 for value in all_callback_data())


def test_intro_always_sends_final_menu_when_edit_fails(monkeypatch):
    temporary_card = SimpleNamespace(delete=AsyncMock())
    final_card = SimpleNamespace()
    message = SimpleNamespace(
        chat=SimpleNamespace(id=1),
        bot=SimpleNamespace(send_chat_action=AsyncMock()),
        answer=AsyncMock(side_effect=[temporary_card, final_card]),
    )

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(beauty_flow.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(beauty_flow, "safe_edit", AsyncMock(side_effect=[False, False]))

    result = asyncio.run(beauty_flow.animate_intro(message))

    assert result is final_card
    assert message.answer.await_count == 2
    assert "Красавица" in message.answer.await_args_list[-1].args[0]
    temporary_card.delete.assert_awaited_once()
