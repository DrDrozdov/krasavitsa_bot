import os
import asyncio


from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from ai_client import ask_deepseek
from links import make_market_links


BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(F.text == "/start")
async def start(message: Message):
    text = (
        "Привет! Я «Красавица» — AI-помощник по подбору базового косметического ухода.\n\n"
        "Напиши, что беспокоит кожу: сухость, жирный блеск, шелушение, чувствительность, неровный тон.\n\n"
        "Я подберу не лекарственный уход и дам ссылки для поиска средств на популярных площадках."
    )

    await message.answer(text)


@dp.message(F.text == "/help")
async def help_cmd(message: Message):
    text = (
        "Опиши кожу по схеме:\n\n"
        "1. Тип кожи: сухая / жирная / комбинированная / чувствительная.\n"
        "2. Что беспокоит: сухость, шелушение, блеск, покраснение и т.д.\n"
        "3. Что уже используешь.\n"
        "4. Есть ли аллергия или раздражение.\n\n"
        "Пример: «Комбинированная кожа, жирный блеск в Т-зоне, щеки сухие, хочу базовый уход»."
    )

    await message.answer(text)


@dp.message(F.text)
async def handle_text(message: Message):
    await message.answer("Подбираю базовый уход и ссылки на маркетплейсы...")

    try:
        data = await ask_deepseek(message.text)

        summary = data.get("summary", "")
        morning = data.get("morning", [])
        evening = data.get("evening", [])
        search_queries = data.get("search_queries", [])
        avoid = data.get("avoid", [])
        warning = data.get("warning", "")

        answer = "💄 <b>Красавица подобрала базовый уход</b>\n\n"
        answer += f"<b>Что понял по запросу:</b>\n{summary}\n\n"

        answer += "<b>Утро:</b>\n"
        for item in morning:
            answer += f"• {item}\n"

        answer += "\n<b>Вечер:</b>\n"
        for item in evening:
            answer += f"• {item}\n"

        answer += "\n<b>Что искать:</b>\n"
        for item in search_queries:
            answer += f"• {item}\n"

        if avoid:
            answer += "\n<b>Чего лучше избегать:</b>\n"
            for item in avoid:
                answer += f"• {item}\n"

        if warning:
            answer += f"\n<b>Важно:</b>\n{warning}"

        await message.answer(answer, parse_mode="HTML")

        if search_queries:
            main_query = search_queries[0]
            links = make_market_links(main_query)

            buttons = []

            for name, url in links.items():
                buttons.append(
                    [InlineKeyboardButton(text=name, url=url)]
                )

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await message.answer(
                f"🔎 Поиск по запросу: <b>{main_query}</b>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

    except Exception as e:
        await message.answer(
            "Не получилось обработать запрос. Проверь API-ключ DeepSeek или попробуй переформулировать вопрос."
        )

        print(e)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
