import asyncio
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from dotenv import load_dotenv

from prompts import reviewer_prompt, specialist_prompt, triage_prompt
from curated_catalog import curated_fallback

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODES = {"skin", "hair", "perfume"}
DEFAULT_ALLOWED_HOSTS = {
    "purito.com", "cosrx.com", "beautyofjoseon.com", "lador.co.kr",
    "olaplex.com", "chi.com", "maisonmargiela.com",
    "maisonmargiela-fragrances.us", "jomalone.com", "diptyqueparis.com",
    "goldapple.ru", "letu.ru", "rivegauche.ru", "ozon.ru",
    "wildberries.ru", "market.yandex.ru",
}

_SHARED_ENGINE_RETRY_AT = 0.0
_LOCAL_ENGINE_RETRY_AT = 0.0
ENGINE_CIRCUIT_SECONDS = 180.0


class BeautyServiceBusyError(ValueError):
    """Temporary upstream rate limit; the saved request can be retried safely."""


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        header_delay = float(response.headers.get("retry-after", ""))
    except (TypeError, ValueError):
        header_delay = 0
    return min(3.0, max(header_delay, 0.8 * (attempt + 1)))


def _get_default_base_url(api_key: str) -> str:
    return "https://api.aitunnel.ru/v1" if api_key.startswith("sk-aitunnel-") else "https://api.deepseek.com"


def _get_deepseek_config() -> tuple[str, str, str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
    base_url = os.getenv("DEEPSEEK_API_BASE", "").strip() or _get_default_base_url(api_key)
    return api_key, model, base_url.rstrip("/")


def _as_text(value, limit: int = 700) -> str:
    return str(value or "").strip()[:limit]


def _as_list(value, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_as_text(item, 260) for item in value if _as_text(item, 260)][:limit]


def _is_exploratory_request(user_text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(user_text or "").lower().replace("ё", "е")).strip()
    markers = (
        "осознанный ознакомительный подбор",
        "не знаю",
        "без предпочтений",
        "не важно",
        "покажи варианты",
        "хочу варианты",
        "подбери сразу",
    )
    return any(marker in normalized for marker in markers)


def _score(value) -> int:
    try:
        return max(40, min(99, round(float(value))))
    except (TypeError, ValueError):
        return 60


def _extract_model_json(response_json: dict) -> dict:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Ответ DeepSeek не содержит choices.")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content", first.get("content"))
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek вернул пустой ответ.")
    text = re.sub(r"^```json\s*|```$", "", content.strip(), flags=re.IGNORECASE).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("DeepSeek нарушил JSON-контракт.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek вернул JSON не того типа.")
    return parsed


async def _call_model(system: str, user: str, max_tokens: int) -> dict:
    api_key, model, base_url = _get_deepseek_config()
    if not api_key:
        raise ValueError("Не настроен ни BEAUTY_OS_API_URL, ни DEEPSEEK_API_KEY.")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.15,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=28, follow_redirects=True) as client:
            for attempt in range(3):
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                if response.status_code != 429:
                    response.raise_for_status()
                    return _extract_model_json(response.json())
                if attempt < 2:
                    await asyncio.sleep(_retry_delay(response, attempt))
            raise BeautyServiceBusyError(
                "Сервис подбора сейчас перегружен. Параметры сохранены — повтори запрос через минуту."
            )
    except httpx.TimeoutException as exc:
        raise ValueError("Превышено время ожидания DeepSeek.") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise ValueError("DeepSeek не принял API-ключ.") from exc
        if exc.response.status_code == 402:
            raise ValueError("На аккаунте DeepSeek нет доступного баланса.") from exc
        if exc.response.status_code == 429:
            raise BeautyServiceBusyError(
                "Сервис подбора сейчас перегружен. Параметры сохранены — повтори запрос через минуту."
            ) from exc
        raise ValueError("Сервис подбора временно недоступен.") from exc
    except (httpx.RequestError, json.JSONDecodeError) as exc:
        raise ValueError("Не удалось получить корректный ответ DeepSeek.") from exc


def _shared_endpoint() -> str:
    value = os.getenv("BEAUTY_OS_API_URL", "https://krasavitsa-ai.ru/api/recommendations").strip().rstrip("/")
    if not value or value.lower() in {"off", "disabled", "none"}:
        return ""
    return value if value.endswith("/api/recommendations") else f"{value}/api/recommendations"


async def _call_shared_engine(user_text: str, mode: str) -> dict:
    endpoint = _shared_endpoint()
    if not endpoint:
        raise ValueError("SHARED_ENGINE_NOT_CONFIGURED")
    try:
        try:
            timeout = float(os.getenv("BEAUTY_OS_TIMEOUT_SECONDS", "12"))
        except ValueError:
            timeout = 12.0
        timeout = max(5.0, min(45.0, timeout))
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
                    "Сервис подбора сейчас перегружен. Параметры сохранены — повтори запрос через минуту."
                )
    except BeautyServiceBusyError:
        raise
    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as exc:
        raise ValueError("Общий движок «Красавицы» временно недоступен.") from exc
    if not isinstance(data, dict):
        raise ValueError("Общий движок вернул неверный формат.")
    return data


def _allowed_hosts() -> set[str]:
    extra = {item.strip().lower() for item in os.getenv("PRODUCT_LINK_ALLOWED_HOSTS", "").split(",") if item.strip()}
    return DEFAULT_ALLOWED_HOSTS | extra


def _is_allowed_host(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in _allowed_hosts())


def _direct_url(value: str) -> str:
    try:
        parsed = urlparse(_as_text(value, 700))
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.netloc or not _is_allowed_host(parsed.hostname or ""):
        return ""
    route = f"{parsed.path} {parsed.query}".lower()
    if re.search(r"/(search|catalogsearch|catalog/0/search|category|collections/all)(/|\?|$)", route):
        return ""
    if re.search(r"(^|&)(q|query|text|search)=", parsed.query.lower()):
        return ""
    if parsed.path in {"", "/"} or len(parsed.path) < 8:
        return ""
    return parsed.geturl()


def _tokens(name: str) -> list[str]:
    stop = {"the", "and", "with", "for", "eau", "de", "parfum", "toilette", "cream", "gel", "serum", "shampoo", "conditioner", "spray", "крем", "гель", "для"}
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", name.lower().replace("ё", "е"))
    return list(dict.fromkeys(token for token in normalized.split() if len(token) >= 3 and token not in stop))[:8]


async def _verify_url(client: httpx.AsyncClient, product_name: str, value: str) -> str:
    url = _direct_url(value)
    if not url:
        return ""
    product_tokens = _tokens(product_name)
    path = re.sub(r"[^a-zа-я0-9]+", " ", unquote(urlparse(url).path).lower())
    path_matches = sum(token in path for token in product_tokens)
    try:
        async with client.stream("GET", url, headers={"User-Agent": "KrasavitsaProductVerifier/2.0", "Accept": "text/html"}) as response:
            final_url = _direct_url(str(response.url))
            if not final_url:
                return ""
            if response.status_code in {403, 429}:
                return final_url if path_matches >= 2 else ""
            if response.status_code >= 400 or "text/html" not in response.headers.get("content-type", ""):
                return ""
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) >= 180_000:
                    break
        page = content.decode("utf-8", errors="ignore").lower()
        matches = sum(token in page for token in product_tokens)
        required = min(3, max(2, (len(product_tokens) + 1) // 2))
        return final_url if matches >= required else ""
    except httpx.RequestError:
        return url if path_matches >= 3 else ""


def _link_label(url: str, fallback: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    labels = {
        "goldapple": "Золотое Яблоко", "letu": "Лэтуаль", "rivegauche": "Рив Гош",
        "ozon": "Ozon", "wildberries": "Wildberries", "market.yandex": "Яндекс Маркет",
    }
    return next((label for marker, label in labels.items() if marker in host), fallback or "Карточка товара")


async def _verify_product(client: httpx.AsyncClient, raw: dict) -> dict | None:
    name = _as_text(raw.get("name"), 180)
    category = _as_text(raw.get("category"), 100)
    reason = _as_text(raw.get("reason"), 700)
    if len(name) < 5 or not category or not reason:
        return None
    proposed = []
    official = _as_text(raw.get("official_url"), 700)
    if official:
        proposed.append(("Официальная карточка", official, "official"))
    retailers = raw.get("retailer_urls") if isinstance(raw.get("retailer_urls"), list) else []
    for item in retailers[:4]:
        if isinstance(item, dict):
            proposed.append((_as_text(item.get("label"), 40), _as_text(item.get("url"), 700), "retailer"))
    verified = await asyncio.gather(*[_verify_url(client, name, url) for _, url, _ in proposed])
    links = []
    for (label, _, kind), url in zip(proposed, verified):
        if url and all(link["href"] != url for link in links):
            links.append({"label": _link_label(url, label), "href": url, "kind": kind})
    if not links:
        return None
    return {
        "name": name,
        "category": category,
        "reason": reason,
        "matchScore": _score(raw.get("match_score")),
        "usage": _as_text(raw.get("usage"), 400),
        "tradeoffs": _as_list(raw.get("tradeoffs"), 4),
        "marketplaces": links[:4],
    }


async def _local_pipeline(user_text: str, mode: str) -> dict:
    triage = await _call_model(triage_prompt(mode), f"<user_request>{user_text}</user_request>", 1400)
    decision = triage.get("decision", "ready")
    summary = _as_text(triage.get("summary")) or "Запрос принят."
    question = _as_text(triage.get("question"), 300)
    if decision == "clarify" and _is_exploratory_request(user_text):
        decision = "ready"
        summary = summary or "Пользователь хочет посмотреть разные направления без жёстких ограничений."
    if decision in {"clarify", "decline"}:
        return {"status": "needs_input", "mode": mode, "summary": summary, "followUpQuestion": question or "Уточни цель, ограничения и бюджет.", "products": [], "methodology": "grounded-v2"}
    if decision == "safety":
        return {"status": "safety_redirect", "mode": mode, "summary": summary, "followUpQuestion": question or "При таких симптомах безопаснее обратиться к профильному врачу.", "products": [], "methodology": "grounded-v2"}

    profile = triage.get("profile") if isinstance(triage.get("profile"), dict) else {}
    candidates = await _call_model(
        specialist_prompt(mode),
        json.dumps({"user_query": user_text, "extracted_profile": profile}, ensure_ascii=False),
        4200,
    )
    raw_products = candidates.get("products") if isinstance(candidates.get("products"), list) else []
    async with httpx.AsyncClient(timeout=8, follow_redirects=True, verify=True) as client:
        checked = await asyncio.gather(*[_verify_product(client, item) for item in raw_products[:8] if isinstance(item, dict)])
    products = [item for item in checked if item]
    if not products:
        return {"status": "no_verified_products", "mode": mode, "summary": "Не удалось подтвердить отдельные карточки предложенных товаров, поэтому я не показываю вымышленные ссылки.", "followUpQuestion": "Уточни бюджет, страну покупки или 1–2 знакомых бренда.", "products": [], "methodology": "grounded-v2"}

    try:
        review = await _call_model(
            reviewer_prompt(mode),
            json.dumps({"user_query": user_text, "profile": profile, "verified_products": [{k: v for k, v in item.items() if k != "marketplaces"} for item in products]}, ensure_ascii=False),
            2600,
        )
        decisions = review.get("decisions") if isinstance(review.get("decisions"), list) else []
        by_name = {item["name"].lower(): item for item in products}
        selected = []
        for decision_item in decisions:
            if not isinstance(decision_item, dict) or decision_item.get("keep") is False:
                continue
            product = by_name.get(_as_text(decision_item.get("name"), 180).lower())
            if not product or product in selected:
                continue
            product = dict(product)
            product["matchScore"] = _score(decision_item.get("match_score"))
            product["reason"] = _as_text(decision_item.get("reason"), 700) or product["reason"]
            product["usage"] = _as_text(decision_item.get("usage"), 400) or product["usage"]
            product["tradeoffs"] = _as_list(decision_item.get("tradeoffs"), 4) or product["tradeoffs"]
            selected.append(product)
        if selected:
            products = selected
            summary = _as_text(review.get("summary")) or summary
    except ValueError:
        products.sort(key=lambda item: item["matchScore"], reverse=True)

    return {"status": "complete", "mode": mode, "summary": summary, "products": products[:4], "methodology": "grounded-v2"}


async def ask_deepseek(user_text: str, mode: str = "skin") -> dict:
    global _SHARED_ENGINE_RETRY_AT, _LOCAL_ENGINE_RETRY_AT
    mode = mode if mode in MODES else "skin"
    now = time.monotonic()
    if _shared_endpoint() and now >= _SHARED_ENGINE_RETRY_AT:
        try:
            shared = await _call_shared_engine(user_text, mode)
            if shared.get("status") == "complete" and shared.get("products"):
                return shared
            if shared.get("status") == "safety_redirect":
                return shared
            if shared.get("status") == "needs_input":
                return curated_fallback(
                    mode,
                    "Запрос можно уточнить, но для начала показываю несколько проверенных направлений. "
                    "Выберите близкий вариант или измените параметры профиля.",
                )
        except ValueError:
            _SHARED_ENGINE_RETRY_AT = time.monotonic() + ENGINE_CIRCUIT_SECONDS
    if now >= _LOCAL_ENGINE_RETRY_AT:
        try:
            local = await _local_pipeline(user_text, mode)
            if local.get("status") == "complete" and local.get("products"):
                return local
            if local.get("status") == "safety_redirect":
                return local
            if local.get("status") == "needs_input":
                return curated_fallback(
                    mode,
                    "Запрос можно уточнить, но для начала показываю несколько проверенных направлений. "
                    "Выберите близкий вариант или измените параметры профиля.",
                )
        except ValueError:
            _LOCAL_ENGINE_RETRY_AT = time.monotonic() + ENGINE_CIRCUIT_SECONDS
    return curated_fallback(mode)
