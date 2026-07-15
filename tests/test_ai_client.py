import asyncio
from unittest.mock import AsyncMock

import pytest

import ai_client


class RateLimitedResponse:
    status_code = 429
    headers = {"retry-after": "0"}


class RateLimitedClient:
    def __init__(self):
        self.post = AsyncMock(return_value=RateLimitedResponse())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def test_model_retries_rate_limit_and_returns_friendly_error(monkeypatch):
    client = RateLimitedClient()
    monkeypatch.setattr(ai_client, "_get_deepseek_config", lambda: ("test-key", "test-model", "https://example.com"))
    monkeypatch.setattr(ai_client.httpx, "AsyncClient", lambda **_kwargs: client)
    monkeypatch.setattr(ai_client.asyncio, "sleep", AsyncMock())

    with pytest.raises(ai_client.BeautyServiceBusyError) as error:
        asyncio.run(ai_client._call_model("system", "user", 100))

    assert client.post.await_count == 3
    assert ai_client.asyncio.sleep.await_count == 2
    assert "HTTP 429" not in str(error.value)
    assert "перегружен" in str(error.value)


def test_short_indecision_is_treated_as_exploratory_request():
    assert ai_client._is_exploratory_request("Не знаю")
    assert ai_client._is_exploratory_request("Покажи варианты")
    assert not ai_client._is_exploratory_request("Нужен древесный аромат до 10 000 ₽")


def test_shared_engine_defaults_to_production_site(monkeypatch):
    monkeypatch.delenv("BEAUTY_OS_API_URL", raising=False)
    assert ai_client._shared_endpoint() == "https://krasavitsa-ai.ru/api/recommendations"


def test_shared_engine_outage_never_invents_unpriced_fallback(monkeypatch):
    shared = AsyncMock(side_effect=ValueError("offline"))
    local = AsyncMock(side_effect=ValueError("no balance"))
    monkeypatch.setattr(ai_client, "_SHARED_ENGINE_RETRY_AT", 0.0)
    monkeypatch.setattr(ai_client, "_LOCAL_ENGINE_RETRY_AT", 0.0)
    monkeypatch.setattr(ai_client, "_call_shared_engine", shared)
    monkeypatch.setattr(ai_client, "_local_pipeline", local)

    result = asyncio.run(ai_client.ask_deepseek("Подбери уход за волосами", "hair"))
    second = asyncio.run(ai_client.ask_deepseek("Подбери уход за волосами", "hair"))

    assert result["status"] == "no_verified_products"
    assert second["status"] == "no_verified_products"
    assert result["products"] == []
    assert shared.await_count == 1
    local.assert_not_awaited()


def test_needs_input_is_preserved_by_the_shared_engine(monkeypatch):
    monkeypatch.setattr(ai_client, "_SHARED_ENGINE_RETRY_AT", 0.0)
    monkeypatch.setattr(
        ai_client,
        "_call_shared_engine",
        AsyncMock(return_value={"status": "needs_input", "products": [], "summary": "Уточните запрос"}),
    )

    result = asyncio.run(ai_client.ask_deepseek("Нужна термозащита", "hair"))

    assert result["status"] == "needs_input"


def test_incomplete_shared_result_is_rejected_without_local_algorithm(monkeypatch):
    monkeypatch.setattr(ai_client, "_SHARED_ENGINE_RETRY_AT", 0.0)
    monkeypatch.setattr(ai_client, "_LOCAL_ENGINE_RETRY_AT", 0.0)
    monkeypatch.setattr(
        ai_client,
        "_call_shared_engine",
        AsyncMock(return_value={
            "status": "complete",
            "products": [{"name": "Starter"}],
            "methodology": "curated-fallback",
        }),
    )
    local = AsyncMock()
    monkeypatch.setattr(ai_client, "_local_pipeline", local)

    result = asyncio.run(ai_client.ask_deepseek("Нужен аромат", "perfume"))

    assert result["status"] == "no_verified_products"
    assert result["products"] == []
    local.assert_not_awaited()
