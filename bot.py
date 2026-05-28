import os
print("ALL ENV KEYS:", list(os.environ.keys()))
print("BOT_TOKEN DEBUG:", os.getenv("BOT_TOKEN"))
import asyncio


from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from ai_client import ask_deepseek
from links import make_market_links


BOT_TOKEN = os.getenv("BOT_TOKEN")

print("BOT_TOKEN DEBUG:", BOT_TOKEN)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN НЕ НАЙДЕН В RAILWAY VARIABLES")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💄 Подобрать уход")],
        [
            KeyboardButton(text="🧴 Мой тип кожи"),
            KeyboardButton(text="💰 Бюджет")
        ],
        [
            KeyboardButton(text="🛒 Где искать"),
            KeyboardButton(text="⚠️ Когда к врачу")
        ],
        [KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)

@dp.message(F.text == "/start")
async def start(message: Message):
    text = (
        "Привет! Я «Красавица» — AI-помощник по подбору базового косметического ухода.\n\n"
        "Я могу подобрать не лекарственный уход, предложить категории средств и дать ссылки на маркетплейсы.\n\n"
        "Выбери действие кнопкой ниже или просто напиши, что беспокоит кожу."
    )

    await message.answer(text, reply_markup=main_menu)


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

@dp.message(F.text == "💄 Подобрать уход")
async def choose_care(message: Message):
    await message.answer(
        "Опиши, что беспокоит кожу.\n\n"
        "Например:\n"
        "«Сухая кожа, шелушение, хочется базовый уход до 3000 ₽»"
    )


@dp.message(F.text == "🧴 Мой тип кожи")
async def skin_type(message: Message):
    await message.answer(
        "Напиши тип кожи:\n\n"
        "• сухая\n"
        "• жирная\n"
        "• комбинированная\n"
        "• чувствительная\n\n"
        "И добавь, что именно беспокоит."
    )


@dp.message(F.text == "💰 Бюджет")
async def budget(message: Message):
    await message.answer(
        "Можешь сразу указать бюджет в запросе:\n\n"
        "• до 1000 ₽\n"
        "• 1000–3000 ₽\n"
        "• 3000–6000 ₽\n"
        "• без ограничений\n\n"
        "Пример: «Комбинированная кожа, нужен уход до 3000 ₽»"
    )


@dp.message(F.text == "🛒 Где искать")
async def where_to_search(message: Message):
    await message.answer(
        "Я даю ссылки на поиск средств в:\n\n"
        "• Яндекс Маркете\n"
        "• Золотом Яблоке\n"
        "• Ozon\n"
        "• Wildberries\n"
        "• Лэтуаль\n"
        "• Рив Гош"
    )


@dp.message(F.text == "⚠️ Когда к врачу")
async def doctor_warning(message: Message):
    await message.answer(
        "Лучше обратиться к дерматологу, если есть:\n\n"
        "• сильное воспаление\n"
        "• боль\n"
        "• гнойные высыпания\n"
        "• ожог\n"
        "• резкая аллергическая реакция\n"
        "• сильный зуд\n"
        "• быстрое ухудшение кожи\n\n"
        "Я подбираю только косметический, не лекарственный уход."
    )


@dp.message(F.text == "ℹ️ Помощь")
async def help_button(message: Message):
    await help_cmd(message)

@dp.message(F.text)
async def handle_text(message: Message):
    loading_msg = await message.answer("Подбираю базовый уход и ссылки на маркетплейсы...")

    try:
        data = await ask_deepseek(message.text)

        
        await loading_msg.delete()

        summary = data.get("summary", "")
        morning = data.get("morning", [])
        evening = data.get("evening", [])
        recommended_products = data.get("recommended_products", [])
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

        if recommended_products:
            answer += "\n<b>Конкретные варианты:</b>\n"

            for product in recommended_products[:5]:
                name = product.get("name", "")
                category = product.get("category", "")
                why = product.get("why", "")

                answer += f"• <b>{name}</b>\n"

                if category:
                    answer += f"  {category}\n"

                if why:
                    answer += f"  {why}\n"

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

        if recommended_products:
            main_query = recommended_products[0].get("name", search_queries[0] if search_queries else "")
        elif search_queries:
            main_query = search_queries[0]
        else:
            main_query = ""

        if main_query:
            links = make_market_links(main_query)

            buttons = []

            for name, url in links.items():
                buttons.append(
                    [InlineKeyboardButton(text=name, url=url)]
                )

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await message.answer(
                f"🔎 Искать: <b>{main_query}</b>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

    except Exception as e:
        try:
            await loading_msg.delete()
        except Exception:
            pass

        await message.answer(
            "Не получилось обработать запрос. Проверь API-ключ DeepSeek или попробуй переформулировать вопрос."
        )

        print(e)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
