from beauty_flow import (
    FLOW_STEPS,
    all_callback_data,
    build_query,
    choose_option,
    main_text,
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


def test_every_callback_data_fits_telegram_limit():
    assert all(len(value.encode("utf-8")) <= 64 for value in all_callback_data())
