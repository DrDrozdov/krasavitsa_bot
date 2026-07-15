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
