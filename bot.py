import html
import os
import re
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
    get_last_recommendations,
    get_total_users,
    get_total_recommendations,
    get_feedback_stats,
    get_product_feedback_stats
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN НЕ НАЙДЕН В RAILWAY VARIABLES")

# ID администраторов (можно указать через ADMIN_IDS в переменных окружения)
ADMIN_IDS = []
admin_ids_str = os.getenv("ADMIN_IDS", "")
if admin_ids_str:
    try:
        ADMIN_IDS = [int(uid.strip()) for uid in admin_ids_str.split(",")]
    except ValueError:
        pass

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

scenarios_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="💧 Сухость"),
            KeyboardButton(text="✨ Жирный блеск")
        ],
        [
            KeyboardButton(text="🌿 Чувствительность"),
            KeyboardButton(text="😬 Акне")
        ],
        [
            KeyboardButton(text="☀️ SPF защита"),
            KeyboardButton(text="📝 Другое")
        ],
        [
            KeyboardButton(text="◀️ В главное меню")
        ],
    ],
    resize_keyboard=True
)

budget_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="до 1000 ₽"),
            KeyboardButton(text="до 3000 ₽")
        ],
        [
            KeyboardButton(text="до 6000 ₽"),
            KeyboardButton(text="без ограничений")
        ],
        [
            KeyboardButton(text="◀️ В главное меню")
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

# Обработчики быстрых сценариев
@dp.message(F.text == "💧 Сухость")
async def scenario_dryness(message: Message):
    loading_msg = await message.answer("Подбираю уход для сухой кожи...")
    await loading_msg.delete()
    await handle_text(
        message,
        "Сухая кожа, шелушение, стянутость. Подбери базовый уход."
    )

@dp.message(F.text == "✨ Жирный блеск")
async def scenario_oily(message: Message):
    loading_msg = await message.answer("Подбираю уход для жирной кожи...")
    await loading_msg.delete()
    await handle_text(
        message,
        "Жирная кожа, жирный блеск в Т-зоне, расширенные поры. Подбери базовый уход."
    )

@dp.message(F.text == "🌿 Чувствительность")
async def scenario_sensitive(message: Message):
    loading_msg = await message.answer("Подбираю уход для чувствительной кожи...")
    await loading_msg.delete()
    await handle_text(
        message,
        "Чувствительная кожа, покраснение, раздражение. Подбери мягкий базовый уход."
    )

@dp.message(F.text == "😬 Акне")
async def scenario_acne(message: Message):
    loading_msg = await message.answer("Подбираю уход для кожи с акне...")
    await loading_msg.delete()
    await handle_text(
        message,
        "Кожа с акне и воспалениями, угри. Подбери базовый уход, чтобы не ухудшить."
    )

@dp.message(F.text == "☀️ SPF защита")
async def scenario_spf(message: Message):
    loading_msg = await message.answer("Подбираю средства с SPF...")
    await loading_msg.delete()
    await handle_text(
        message,
        "Ищу хороший крем с SPF для ежедневного использования. Подбери варианты."
    )

@dp.message(F.text == "📝 Другое")
async def scenario_other(message: Message):
    await message.answer(
        "Опиши, что беспокоит кожу:\n\n"
        "Например:\n"
        "«Комбинированная кожа, жирный блеск в Т-зоне, щеки сухие, хочу базовый уход до 3000 ₽»"
    )

@dp.message(F.text == "◀️ В главное меню")
async def back_to_main_menu(message: Message):
    await message.answer("Выбери действие:", reply_markup=main_menu)

# Обработчики выбора бюджета
budget_mapping = {
    "до 1000 ₽": "до 1000",
    "до 3000 ₽": "до 3000",
    "до 6000 ₽": "до 6000",
    "без ограничений": "без ограничений"
}

@dp.message(F.text == "до 1000 ₽")
async def budget_1000(message: Message):
    update_user_profile(message.from_user.id, budget="до 1000 ₽")
    await message.answer(
        "Сохранил твой бюджет: <b>до 1000 ₽</b> ✅\n\n"
        "Теперь напиши проблему кожи, и я подберу подходящие средства.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(F.text == "до 3000 ₽")
async def budget_3000(message: Message):
    update_user_profile(message.from_user.id, budget="до 3000 ₽")
    await message.answer(
        "Сохранил твой бюджет: <b>до 3000 ₽</b> ✅\n\n"
        "Теперь напиши проблему кожи, и я подберу подходящие средства.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(F.text == "до 6000 ₽")
async def budget_6000(message: Message):
    update_user_profile(message.from_user.id, budget="до 6000 ₽")
    await message.answer(
        "Сохранил твой бюджет: <b>до 6000 ₽</b> ✅\n\n"
        "Теперь напиши проблему кожи, и я подберу подходящие средства.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(F.text == "без ограничений")
async def budget_unlimited(message: Message):
    update_user_profile(message.from_user.id, budget="без ограничений")
    await message.answer(
        "Сохранил твой бюджет: <b>без ограничений</b> 👑\n\n"
        "Теперь напиши проблему кожи, и я подберу подходящие средства.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(F.text == "💄 Подобрать уход")
async def choose_care(message: Message):
    await message.answer(
        "Выбери сценарий или опиши свою проблему:\n\n"
        "💧 <b>Сухость</b> — шелушение, стянутость\n"
        "✨ <b>Жирный блеск</b> — жирная кожа, расширенные поры\n"
        "🌿 <b>Чувствительность</b> — покраснение, раздражение\n"
        "😬 <b>Акне</b> — угри и воспаления\n"
        "☀️ <b>SPF защита</b> — солнцезащита\n"
        "📝 <b>Другое</b> — напиши свой вопрос",
        parse_mode="HTML",
        reply_markup=scenarios_menu
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
        "Выбери максимальный бюджет на один товар:\n\n"
        "💰 <b>до 1000 ₽</b> — эконом\n"
        "💳 <b>до 3000 ₽</b> — стандарт\n"
        "💎 <b>до 6000 ₽</b> — премиум\n"
        "👑 <b>без ограничений</b> — люкс",
        parse_mode="HTML",
        reply_markup=budget_menu
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

SKIN_TYPE_PATTERN = re.compile(r"^(сухая|жирная|комбинированная|чувствительная)(?:\s+кожа)?$", re.IGNORECASE)

@dp.message(lambda message: bool(message.text and SKIN_TYPE_PATTERN.fullmatch(message.text.strip())))
async def set_skin_type(message: Message):
    raw_text = message.text.strip()
    skin_type = SKIN_TYPE_PATTERN.fullmatch(raw_text).group(1).lower()
    update_user_profile(message.from_user.id, skin_type=skin_type)

    await message.answer(
        f"Сохранил твой тип кожи: <b>{html.escape(skin_type)}</b> ✅\n\n"
        "Теперь напиши, что беспокоит кожу.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

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

        # Форматирование даты
        from datetime import datetime
        date_obj = datetime.fromisoformat(created_at)
        date_str = date_obj.strftime("%d.%m.%Y %H:%M")

        text += f"<b>{index}. {date_str}</b>\n"
        text += f"Запрос: <i>{html.escape(user_request)}</i>\n"

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
async def handle_text(message: Message, user_text: str | None = None):
    loading_msg = await message.answer("Подбираю базовый уход и ссылки на маркетплейсы...")

    try:
        text_to_process = user_text or message.text
        data = await ask_deepseek(text_to_process)

        
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
            user_request=text_to_process,
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

    except ValueError as e:
        try:
            await loading_msg.delete()
        except Exception:
            pass

        await message.answer(str(e))
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

@dp.message(F.text == "/admin_stats")
async def admin_stats(message: Message):
    # Проверка доступа
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return

    # Получение статистики
    total_users = get_total_users()
    total_recommendations = get_total_recommendations()
    feedback_stats = get_feedback_stats()
    product_feedback_stats = get_product_feedback_stats()
    top_products = get_product_stats(limit=5)

    # Формирование ответа
    text = "📊 <b>Статистика администратора</b>\n\n"

    text += f"<b>Пользователи:</b>\n👥 Всего: {total_users}\n\n"

    text += f"<b>Запросы к AI:</b>\n🤖 Всего рекомендаций: {total_recommendations}\n\n"

    text += f"<b>Оценки подборов:</b>\n"
    text += f"👍 Полезно: {feedback_stats['likes']}\n"
    text += f"👎 Не подошло: {feedback_stats['dislikes']}\n"
    text += f"⏳ Всего оценено: {feedback_stats['total']}\n\n"

    text += f"<b>Оценки товаров:</b>\n"
    text += f"👍 Подошло: {product_feedback_stats['likes']}\n"
    text += f"👎 Не подходит: {product_feedback_stats['dislikes']}\n"
    text += f"👤 Пользователей оценили товары: {product_feedback_stats['unique_users']}\n\n"

    if top_products:
        text += "<b>🏆 Топ-5 средств:</b>\n"
        for idx, (product_name, likes, dislikes) in enumerate(top_products, 1):
            total = (likes or 0) + (dislikes or 0)
            percent = round(((likes or 0) / total) * 100) if total > 0 else 0
            text += f"{idx}. {product_name}\n   {percent}% · 👍 {likes or 0} / 👎 {dislikes or 0}\n"

    await message.answer(text, parse_mode="HTML")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        skip_updates=True,
        allowed_updates=["message", "callback_query"]
    )


if __name__ == "__main__":
    asyncio.run(main())

