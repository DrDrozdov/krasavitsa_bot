import asyncio
from unittest.mock import AsyncMock

import ai_client


def test_shared_engine_defaults_to_production_site(monkeypatch):
    monkeypatch.delenv("BEAUTY_OS_API_URL", raising=False)
    assert ai_client._shared_endpoint() == "https://krasavitsa-ai.ru/api/recommendations"


def test_shared_engine_outage_uses_short_circuit_without_local_core(monkeypatch):
    shared = AsyncMock(side_effect=ValueError("offline"))
    monkeypatch.setattr(ai_client, "_SHARED_ENGINE_RETRY_AT", 0.0)
    monkeypatch.setattr(ai_client, "_call_shared_engine", shared)

    result = asyncio.run(ai_client.ask_deepseek("Подбери уход за волосами", "hair"))
    second = asyncio.run(ai_client.ask_deepseek("Подбери уход за волосами", "hair"))

    assert result["status"] == "no_verified_products"
    assert second["status"] == "no_verified_products"
    assert result["products"] == []
    assert shared.await_count == 1


def test_needs_input_is_preserved_by_the_shared_engine(monkeypatch):
    monkeypatch.setattr(ai_client, "_SHARED_ENGINE_RETRY_AT", 0.0)
    monkeypatch.setattr(
        ai_client,
        "_call_shared_engine",
        AsyncMock(return_value={"status": "needs_input", "products": [], "summary": "Уточните запрос"}),
    )

    result = asyncio.run(ai_client.ask_deepseek("Нужна термозащита", "hair"))

    assert result["status"] == "needs_input"


def test_incomplete_shared_result_is_rejected():
    result = ai_client._ensure_complete_result(
        {"status": "complete", "products": [{"name": "Starter"}]},
        "perfume",
    )

    assert result["status"] == "no_verified_products"
    assert result["products"] == []


def test_shared_contract_keeps_three_direct_links_with_two_real_prices():
    product = {
        "name": "Verified Product",
        "priceRange": "900–1 200 ₽",
        "marketplaces": [
            {"label": "Яндекс Маркет", "href": "https://market.yandex.ru/card/item/123", "price": 900},
            {"label": "Ozon", "href": "https://www.ozon.ru/product/item-456/", "price": 1200},
            {"label": "Wildberries", "href": "https://www.wildberries.ru/catalog/789/detail.aspx"},
        ],
    }
    data = {"status": "complete", "products": [dict(product) for _ in range(3)]}
    for index, item in enumerate(data["products"]):
        item["name"] += str(index)

    result = ai_client._ensure_complete_result(data, "skin")

    assert result["status"] == "complete"
    assert all(len(item["marketplaces"]) == 3 for item in result["products"])
