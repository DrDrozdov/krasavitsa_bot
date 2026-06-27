import os
import json
import re
from pathlib import Path
import httpx

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Masked startup info to help debug missing env on deployment
if DEEPSEEK_API_KEY:
    masked = f"{DEEPSEEK_API_KEY[:4]}...{DEEPSEEK_API_KEY[-4:]}"
    logger.info("DEEPSEEK_API_KEY loaded: %s (len=%d)", masked, len(DEEPSEEK_API_KEY))
else:
    logger.info("DEEPSEEK_API_KEY not set (empty)")


async def ask_deepseek(user_text: str) -> dict:
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY не найден. Проверь .env или переменную окружения.")

    url = "https://api.aitunnel.ru/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": DEEPSEEK_MODEL,
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
        "response_format": {
            "type": "json_object"
        }
    }

    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

        response.raise_for_status()

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