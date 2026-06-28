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
