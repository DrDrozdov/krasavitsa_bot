import os
import json
import re
from pathlib import Path
import httpx

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_default_base_url(api_key: str) -> str:
    if api_key.startswith("sk-aitunnel-"):
        return "https://api.aitunnel.ru/v1"
    return "https://api.deepseek.com"


def _get_deepseek_config() -> tuple[str, str, str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
    base_url = os.getenv("DEEPSEEK_API_BASE", "").strip()
    if not base_url:
        base_url = _get_default_base_url(api_key)
    base_url = base_url.rstrip("/")
    return api_key, model, base_url


async def ask_deepseek(user_text: str) -> dict:
    api_key, model, base_url = _get_deepseek_config()

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY не найден. Проверь .env или переменную окружения.")

    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_text
            }
        ],
        "temperature": 0.4,
        "max_tokens": 1800,
        "response_format": {
            "type": "json_object"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ValueError("Превышено время ожидания ответа DeepSeek.") from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 401:
            raise ValueError("DeepSeek не принял API-ключ. Проверь DEEPSEEK_API_KEY.") from exc
        if status_code == 402:
            raise ValueError("DeepSeek принял ключ, но на аккаунте нет доступного баланса или кредитов.") from exc
        raise ValueError(f"DeepSeek вернул ошибку HTTP: {status_code}") from exc
    except httpx.RequestError as exc:
        raise ValueError(f"Не удалось связаться с DeepSeek: {exc}") from exc

    try:
        response_json = response.json()
    except json.JSONDecodeError:
        raise ValueError("Ответ DeepSeek не является корректным JSON.")

    if isinstance(response_json, dict) and response_json.get("error"):
        raise ValueError(f"DeepSeek вернул ошибку: {response_json['error']}")

    choices = response_json.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        raise ValueError("Ответ DeepSeek не содержит корректный список choices.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("Первая запись choices не является объектом.")

    content = None
    message_data = first_choice.get("message")
    if isinstance(message_data, dict):
        content = message_data.get("content")
    if content is None:
        content = first_choice.get("content")

    if content is None:
        raise ValueError("Не удалось получить content из ответа DeepSeek.")

    if isinstance(content, dict):
        return content

    if not isinstance(content, str):
        raise ValueError("Ответ DeepSeek пришёл в неожиданном формате.")

    text = content.strip()
    if not text:
        raise ValueError("Пустой ответ от DeepSeek.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Не удалось распарсить JSON из ответа DeepSeek: {text}")
