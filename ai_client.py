import asyncio
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODES = {"skin", "hair", "perfume"}
ENGINE_CIRCUIT_SECONDS = 45.0
_SHARED_ENGINE_RETRY_AT = 0.0


class BeautyServiceBusyError(ValueError):
    """Temporary upstream rate limit; the saved request can be retried safely."""


def _as_text(value, limit: int = 700) -> str:
    return str(value or "").strip()[:limit]


def _store_key(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower().removeprefix("www.")
    for marker, key in (
        ("goldapple", "goldapple"),
        ("letu", "letu"),
        ("rivegauche", "rivegauche"),
        ("wildberries", "wildberries"),
        ("market.yandex", "yandex"),
        ("ozon", "ozon"),
        ("tsum", "tsum"),
    ):
        if marker in host:
            return key
    return ""


def _ensure_complete_result(data: dict, mode: str, minimum: int = 3) -> dict:
    """Keep the website engine contract intact and reject malformed transport data."""
    if data.get("status") != "complete":
        return data
    products = data.get("products") if isinstance(data.get("products"), list) else []
    result = []
    seen = set()
    for raw in products:
        if not isinstance(raw, dict):
            continue
        product = dict(raw)
        name = _as_text(product.get("name"), 180)
        key = re.sub(r"\s+", " ", name.lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        links = product.get("marketplaces") if isinstance(product.get("marketplaces"), list) else []
        verified_links = [
            dict(item)
            for item in links
            if isinstance(item, dict) and _store_key(_as_text(item.get("href"), 700))
        ][:8]
        if len({_store_key(item["href"]) for item in verified_links}) < 3:
            continue
        priced_links = [item for item in verified_links if isinstance(item.get("price"), (int, float))]
        if len({_store_key(item["href"]) for item in priced_links}) < 2:
            continue
        if not _as_text(product.get("priceRange"), 80):
            prices = [int(item["price"]) for item in priced_links]
            product["priceRange"] = f"{min(prices):,}–{max(prices):,} ₽".replace(",", " ")
        product["marketplaces"] = verified_links
        result.append(product)
        if len(result) >= 4:
            break
    if len(result) < minimum:
        return {
            "status": "no_verified_products",
            "mode": mode,
            "summary": (
                "Магазины пока не отдали достаточно данных для трёх честных сравнений. "
                "Я сохранила запрос и не подменяю карточки поисковыми ссылками."
            ),
            "followUpQuestion": "Можно повторить запрос через минутку — отвечать заново не придётся 💗",
            "products": [],
            "methodology": "grounded-v4",
        }
    output = dict(data)
    output["products"] = result
    return output


def _shared_endpoint() -> str:
    value = os.getenv("BEAUTY_OS_API_URL", "https://krasavitsa-ai.ru/api/recommendations").strip().rstrip("/")
    if not value or value.lower() in {"off", "disabled", "none"}:
        return ""
    return value if value.endswith("/api/recommendations") else f"{value}/api/recommendations"


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        header_delay = float(response.headers.get("retry-after", ""))
    except (TypeError, ValueError):
        header_delay = 0.0
    return min(3.0, max(header_delay, 0.8 * (attempt + 1)))


async def _call_shared_engine(user_text: str, mode: str) -> dict:
    endpoint = _shared_endpoint()
    if not endpoint:
        raise ValueError("SHARED_ENGINE_NOT_CONFIGURED")
    try:
        try:
            timeout = float(os.getenv("BEAUTY_OS_TIMEOUT_SECONDS", "55"))
        except ValueError:
            timeout = 55.0
        timeout = max(8.0, min(60.0, timeout))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for attempt in range(2):
                response = await client.post(endpoint, json={"query": user_text, "mode": mode})
                if response.status_code != 429:
                    response.raise_for_status()
                    data = response.json()
                    break
                if attempt == 0:
                    await asyncio.sleep(_retry_delay(response, attempt))
            else:
                raise BeautyServiceBusyError(
                    "Поиск сейчас очень занят. Запрос сохранён — повторите его через минутку 💗"
                )
    except BeautyServiceBusyError:
        raise
    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as exc:
        raise ValueError("Единый поиск «Красавицы» временно недоступен.") from exc
    if not isinstance(data, dict):
        raise ValueError("Единый поиск вернул неверный формат.")
    return data


async def ask_deepseek(user_text: str, mode: str = "skin") -> dict:
    """Use the website search processor; Telegram never runs a divergent local core."""
    global _SHARED_ENGINE_RETRY_AT
    mode = mode if mode in MODES else "skin"
    now = time.monotonic()
    if now < _SHARED_ENGINE_RETRY_AT:
        return {
            "status": "no_verified_products",
            "mode": mode,
            "summary": "Единый поиск восстанавливает соединение. Ваш запрос уже сохранён 💗",
            "followUpQuestion": "Повторите подбор через минутку — заполнять параметры заново не нужно.",
            "products": [],
            "methodology": "grounded-v4",
        }
    try:
        return _ensure_complete_result(await _call_shared_engine(user_text, mode), mode)
    except BeautyServiceBusyError:
        raise
    except ValueError:
        _SHARED_ENGINE_RETRY_AT = time.monotonic() + ENGINE_CIRCUIT_SECONDS
        return {
            "status": "no_verified_products",
            "mode": mode,
            "summary": "Единый поиск временно не ответил. Я сохранила запрос, чтобы ничего не потерялось 💗",
            "followUpQuestion": "Нажмите «Повторить запрос» через минутку.",
            "products": [],
            "methodology": "grounded-v4",
        }
