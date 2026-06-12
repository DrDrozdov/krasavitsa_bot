import os
print("ALL ENV KEYS:", list(os.environ.keys()))
print("BOT_TOKEN DEBUG:", os.getenv("BOT_TOKEN"))
import asyncio


from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from ai_client import ask_deepseek
from links import make_market_links

from database import (
    init_db,
    save_user,
    update_user_profile,
    get_user_profile,
    save_recommendation,
    get_user_recommendations,
    save_feedback,
    save_product_feedback,
    get_product_stats,
    save_recommended_product,
    get_recommended_product_name,
    get_product_rating,
    get_last_recommendations
)

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
            KeyboardButton(text="📜 Мои подборы")
        ],
        [
            KeyboardButton(text="⚠️ Когда к врачу"),
            KeyboardButton(text="ℹ️ Помощь")
        ],
    ],
    resize_keyboard=True
)

@dp.message(F.text == "/start")
async def start(message: Message):
    save_user(
        user_id=message.from_user.id,
        username=message.from_user.username
    )

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

@dp.message(F.text == "📖 Мои рекомендации")
async def my_recommendations(message: Message):
    rows = get_last_recommendations(message.from_user.id)

    if not rows:
        await message.answer("Пока нет сохранённых рекомендаций.")
        return

    text = "📖 <b>Последние рекомендации</b>\n\n"

    for index, row in enumerate(rows, start=1):
        user_request, answer, feedback, created_at = row

        text += f"<b>{index}. Запрос:</b> {user_request}\n"

        if feedback:
            text += f"<b>Оценка:</b> {feedback}\n"

        text += "\n"

    await message.answer(text, parse_mode="HTML")


@dp.callback_query(F.data.startswith("feedback_good:"))
async def feedback_good(callback: CallbackQuery):
    rec_id = int(callback.data.split(":")[1])
    save_feedback(rec_id, "good")

    await callback.message.edit_text("Спасибо. Буду чаще учитывать такие рекомендации 👍")
    await callback.answer()


@dp.callback_query(F.data.startswith("feedback_bad:"))
async def feedback_bad(callback: CallbackQuery):
    rec_id = int(callback.data.split(":")[1])
    save_feedback(rec_id, "bad")

    await callback.message.edit_text("Понял. Буду осторожнее с такими вариантами 👎")
    await callback.answer()

@dp.message(F.text == "📜 Мои подборы")
async def my_recommendations(message: Message):
    rows = get_user_recommendations(message.from_user.id)

    if not rows:
        await message.answer("У тебя пока нет сохранённых подборов 🌷")
        return

    text = "📜 <b>Последние подборы</b>\n\n"

    for index, row in enumerate(rows, start=1):
        user_request, feedback, created_at = row

        text += f"<b>{index}. Запрос:</b> {user_request}\n"

        if feedback == "good":
            text += "Оценка: 👍 Полезно\n"
        elif feedback == "bad":
            text += "Оценка: 👎 Не подошло\n"
        else:
            text += "Оценка: пока нет\n"

        text += "\n"

    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "/product_stats")
async def product_stats(message: Message):
    rows = get_product_stats()

    if not rows:
        await message.answer("Пока нет статистики по средствам.")
        return

    text = "📊 <b>Статистика по средствам</b>\n\n"

    for index, row in enumerate(rows, start=1):
        product_name, likes, dislikes = row

        text += (
            f"<b>{index}. {product_name}</b>\n"
            f"👍 {likes or 0}   👎 {dislikes or 0}\n\n"
        )

    await message.answer(text, parse_mode="HTML")

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

        sent_answer = await message.answer(answer, parse_mode="HTML")

        rec_id = save_recommendation(
            user_id=message.from_user.id,
            user_request=message.text,
            answer=answer
        )

        feedback_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍 Полезно", callback_data=f"feedback_good:{rec_id}"),
                    InlineKeyboardButton(text="👎 Не подошло", callback_data=f"feedback_bad:{rec_id}")
                ]
            ]
        )

        await message.answer(
            "Оцени подбор — так «Красавица» станет точнее.",
            reply_markup=feedback_keyboard
        )

        if recommended_products:
            await message.answer("🛒 <b>Ссылки на поиск по каждому варианту:</b>", parse_mode="HTML")

            for index, product in enumerate(recommended_products[:5], start=1):
                product_name = product.get("name", "").strip()
                product_category = product.get("category", "").strip()

                if not product_name:
                    continue

                links = make_market_links(product_name)

                product_id = save_recommended_product(
                    user_id=message.from_user.id,
                    product_name=product_name
                )

                buttons = [
                    [
                        InlineKeyboardButton(text="Яндекс", url=links["Яндекс Маркет"]),
                        InlineKeyboardButton(text="Ozon", url=links["Ozon"]),
                    ],
                    [
                        InlineKeyboardButton(text="WB", url=links["Wildberries"]),
                        InlineKeyboardButton(text="ЗЯ", url=links["Золотое Яблоко"]),
                    ],
                    [
                        InlineKeyboardButton(text="Лэтуаль", url=links["Лэтуаль"]),
                        InlineKeyboardButton(text="Рив Гош", url=links["Рив Гош"]),
                    ],
                    [
                        InlineKeyboardButton(text="👍 Подходит", callback_data=f"product_good:{product_id}"),
                        InlineKeyboardButton(text="👎 Не подходит", callback_data=f"product_bad:{product_id}"),
                    ],
                ]

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

                emoji = get_category_emoji(product_category)

                rating = get_product_rating(product_name)

                text = f"{emoji}\n<code>{product_name}</code>\n\n{rating['text']}"

                await message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

        elif search_queries:
            main_query = search_queries[0]
            links = make_market_links(main_query)

            buttons = [
                [
                    InlineKeyboardButton(text="Яндекс", url=links["Яндекс Маркет"]),
                    InlineKeyboardButton(text="Ozon", url=links["Ozon"]),
                ],
                [
                    InlineKeyboardButton(text="WB", url=links["Wildberries"]),
                    InlineKeyboardButton(text="ЗЯ", url=links["Золотое Яблоко"]),
                ],
                [
                    InlineKeyboardButton(text="Лэтуаль", url=links["Лэтуаль"]),
                    InlineKeyboardButton(text="Рив Гош", url=links["Рив Гош"]),
                ],
            ]

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await message.answer(
                f"🔎 <b>Искать:</b> {main_query}",
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


def get_category_emoji(category: str) -> str:
    category = category.lower()

    if "крем" in category:
        return "🧴"
    if "сыворот" in category:
        return "💧"
    if "гель" in category:
        return "🫧"
    if "пенк" in category or "очищ" in category:
        return "🧼"
    if "тоник" in category or "тонер" in category:
        return "🌿"
    if "spf" in category or "солнц" in category:
        return "☀️"
    if "маск" in category:
        return "🎭"

    return "✨"

@dp.callback_query(F.data.startswith("product_good:"))
async def product_good(callback: CallbackQuery):
    product_id = int(callback.data.replace("product_good:", ""))
    product_name = get_recommended_product_name(product_id)

    if not product_name:
        await callback.answer("Не удалось найти средство")
        return

    save_product_feedback(
        user_id=callback.from_user.id,
        product_name=product_name,
        feedback="good"
    )

    await callback.answer("Сохранил: средство подошло 👍")


@dp.callback_query(F.data.startswith("product_bad:"))
async def product_bad(callback: CallbackQuery):
    product_id = int(callback.data.replace("product_bad:", ""))
    product_name = get_recommended_product_name(product_id)

    if not product_name:
        await callback.answer("Не удалось найти средство")
        return

    save_product_feedback(
        user_id=callback.from_user.id,
        product_name=product_name,
        feedback="bad"
    )

    await callback.answer("Сохранил: средство не подошло 👎")

async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

