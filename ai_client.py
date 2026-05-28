import os
import json
import httpx

from dotenv import load_dotenv
load_dotenv()

from prompts import SYSTEM_PROMPT


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")


async def ask_deepseek(user_text: str) -> dict:
    url = "https://api.deepseek.com/chat/completions"

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

    content = response.json()["choices"][0]["message"]["content"]

    return json.loads(content)