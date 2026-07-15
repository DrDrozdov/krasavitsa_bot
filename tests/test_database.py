import os
from pathlib import Path

import pytest

import database

TEST_DB = Path(__file__).resolve().parent / "test_krasavitsa.db"


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    monkeypatch.setattr(database, "DB_NAME", str(TEST_DB))
    if TEST_DB.exists():
        TEST_DB.unlink()
    database.init_db()
    yield
    if TEST_DB.exists():
        TEST_DB.unlink()


def test_get_total_recommended_products_increments():
    before = database.get_total_recommended_products()
    assert before == 0

    database.save_recommended_product(user_id=1, product_name="Test Product")
    after = database.get_total_recommended_products()

    assert after == before + 1


def test_favorites_save_and_list():
    rec_id = database.save_recommendation(user_id=1, user_request="Hello", answer="Answer")
    fav_id = database.save_favorite(user_id=1, recommendation_id=rec_id, title="My Favorite")

    favorites = database.get_favorites(user_id=1)
    assert len(favorites) == 1
    assert favorites[0][0] == fav_id
    assert favorites[0][1] == rec_id
    assert favorites[0][2] == "My Favorite"


def test_favorite_delete():
    rec_id = database.save_recommendation(user_id=1, user_request="Hello", answer="Answer")
    fav_id = database.save_favorite(user_id=1, recommendation_id=rec_id, title="My Favorite")

    database.delete_favorite(fav_id)
    favorites = database.get_favorites(user_id=1)
    assert len(favorites) == 0


def test_beauty_profile_persists_each_mode_independently():
    database.save_user(user_id=1, username="tester")
    database.save_beauty_profile(1, "skin", {"skin_type": "combo", "budget": "3000"}, 2)
    database.save_beauty_profile(1, "hair", {"hair_type": "curly"}, 1)

    skin = database.get_beauty_profile(1, "skin")
    hair = database.get_beauty_profile(1, "hair")

    assert skin["answers"] == {"budget": "3000", "skin_type": "combo"}
    assert skin["current_step"] == 2
    assert hair["answers"] == {"hair_type": "curly"}


def test_user_beauty_state_keeps_last_query_when_only_mode_changes():
    database.save_user_beauty_state(1, "perfume", "подбери древесный аромат")
    database.save_user_beauty_state(1, "hair")

    state = database.get_user_beauty_state(1)
    assert state["active_mode"] == "hair"
    assert state["last_query"] == "подбери древесный аромат"
    assert state["last_query_mode"] == "perfume"


def test_product_feedback_is_one_current_vote_per_shown_card():
    product_id = database.save_recommended_product(user_id=1, product_name="COSRX Cleanser")
    database.save_product_feedback(1, "COSRX Cleanser", "good", recommended_product_id=product_id)
    database.save_product_feedback(1, "COSRX Cleanser", "bad", recommended_product_id=product_id)

    stats = database.get_product_feedback_stats()
    assert stats == {"likes": 0, "dislikes": 1, "unique_users": 1}


def test_recommended_product_cannot_be_rated_by_another_user():
    product_id = database.save_recommended_product(user_id=1, product_name="Private Product")
    assert database.get_recommended_product_name(product_id, user_id=1) == "Private Product"
    assert database.get_recommended_product_name(product_id, user_id=2) is None
