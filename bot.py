import html
import io
import os
import re
import asyncio
from urllib.parse import quote_plus, unquote, urljoin, urlparse

import httpx

try:
    from PIL import Image
except ImportError:
    Image = None

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
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
    save_recommendation,
    get_user_recommendations,
    save_feedback,
    save_product_feedback,
    get_product_stats,
    save_recommended_product,
    get_recommended_product_name,
    get_product_rating,
    get_total_users,
    get_total_recommendations,
    get_feedback_stats,
    get_product_feedback_stats,
    get_total_recommended_products,
    get_last_recommendation,
    save_favorite,
    get_favorites,
    delete_favorite
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

IMAGE_FETCH_TIMEOUT = 8
IMAGE_SEARCH_TIMEOUT = 8
IMAGE_CARD_TIMEOUT = 18
MAX_IMAGE_SEARCH_QUERIES = 4

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

result_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔄 Ещё подбор"),
            KeyboardButton(text="📜 Мои подборы")
        ],
        [
            KeyboardButton(text="💰 Бюджет"),
            KeyboardButton(text="🛒 Где искать")
        ],
        [
            KeyboardButton(text="🔖 В избранное"),
            KeyboardButton(text="📂 Избранное")
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
async def run_scenario(message: Message, loading_text: str, prompt: str):
    loading_msg = await message.answer(loading_text)

    try:
        await handle_text(
            message,
            prompt,
            loading_msg=loading_msg
        )
    except Exception as e:
        try:
            await loading_msg.delete()
        except Exception:
            pass

        await message.answer(
            "Не удалось обработать сценарий. Попробуй повторить запрос или напиши проблему иначе."
        )
        print(f"Scenario error: {e}")

@dp.message(F.text == "💧 Сухость")
async def scenario_dryness(message: Message):
    await run_scenario(
        message,
        "Подбираю уход для сухой кожи...",
        "Сухая кожа, шелушение, стянутость. Подбери базовый уход."
    )

@dp.message(F.text == "✨ Жирный блеск")
async def scenario_oily(message: Message):
    await run_scenario(
        message,
        "Подбираю уход для жирной кожи...",
        "Жирная кожа, жирный блеск в Т-зоне, расширенные поры. Подбери базовый уход."
    )

@dp.message(F.text == "🌿 Чувствительность")
async def scenario_sensitive(message: Message):
    await run_scenario(
        message,
        "Подбираю уход для чувствительной кожи...",
        "Чувствительная кожа, покраснение, раздражение. Подбери мягкий базовый уход."
    )

@dp.message(F.text == "😬 Акне")
async def scenario_acne(message: Message):
    await run_scenario(
        message,
        "Подбираю уход для кожи с акне...",
        "Кожа с акне и воспалениями, угри. Подбери базовый уход, чтобы не ухудшить."
    )

@dp.message(F.text == "☀️ SPF защита")
async def scenario_spf(message: Message):
    await run_scenario(
        message,
        "Подбираю средства с SPF...",
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

@dp.message(F.text == "🔄 Ещё подбор")
async def another_selection(message: Message):
    await message.answer(
        "Выбери сценарий или напиши свою проблему:",
        reply_markup=scenarios_menu
    )

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

        feedback_text = ""
        if feedback == "good":
            feedback_text = " — 👍 полезно"
        elif feedback == "bad":
            feedback_text = " — 👎 не подошло"

        text += f"<b>{index}. {date_str}</b>{feedback_text}\n"
        text += f"Запрос: <i>{html.escape(user_request)}</i>\n\n"

    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🔖 В избранное")
async def add_favorite(message: Message):
    last = get_last_recommendation(message.from_user.id)
    if not last:
        await message.answer("Нет последних рекомендаций для сохранения.")
        return

    fav_id = save_favorite(message.from_user.id, last["id"], title=None)
    await message.answer("Сохранил подбор в избранное ✅")


@dp.message(F.text == "📂 Избранное")
async def list_favorites(message: Message):
    rows = get_favorites(message.from_user.id)

    if not rows:
        await message.answer("У тебя пока нет избранного.")
        return

    for fav_id, rec_id, title, created_at, answer in rows:
        title_text = title or f"Избранное #{fav_id}"
        short = (answer or "")[:800]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data=f"fav_del:{fav_id}")]
        ])

        await message.answer(
            f"<b>{html.escape(title_text)}</b>\n\n{short}",
            parse_mode="HTML",
            reply_markup=keyboard
        )


@dp.callback_query(F.data.startswith("fav_del:"))
async def fav_delete(callback: CallbackQuery):
    fav_id = int(callback.data.split(":" )[1])
    delete_favorite(fav_id)

    try:
        await callback.message.edit_text("Удалено из избранного.")
    except Exception:
        pass

    await callback.answer()

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
async def handle_text(message: Message, user_text: str | None = None, loading_msg: Message | None = None):
    if loading_msg is None:
        loading_msg = await message.answer("Подбираю базовый уход и ссылки на маркетплейсы...")

    try:
        text_to_process = user_text or message.text
        data = await ask_deepseek(text_to_process)

        summary = data.get("summary", "")
        morning = data.get("morning", [])
        evening = data.get("evening", [])
        recommended_products = data.get("recommended_products", [])
        search_queries = data.get("search_queries", [])
        avoid = data.get("avoid", [])
        warning = data.get("warning", "")

        answer = "💄 <b>Красавица подобрала базовый уход</b>\n\n"
        answer += f"<b>Что понял по запросу:</b>\n{html_text(summary)}\n\n"

        answer += "<b>Утро:</b>\n"
        for item in morning:
            answer += f"• {html_text(item)}\n"

        answer += "\n<b>Вечер:</b>\n"
        for item in evening:
            answer += f"• {html_text(item)}\n"

        if recommended_products:
            answer += "\n<b>Конкретные варианты:</b>\n"

            for product in recommended_products[:5]:
                name = product.get("name", "")
                category = product.get("category", "")
                why = product.get("why", "")

                answer += f"• <b>{html_text(name)}</b>\n"

                if category:
                    answer += f"  {html_text(category)}\n"

                if why:
                    answer += f"  {html_text(why)}\n"

        answer += "\n<b>Что искать:</b>\n"
        for item in search_queries:
            answer += f"• {html_text(item)}\n"

        if avoid:
            answer += "\n<b>Чего лучше избегать:</b>\n"
            for item in avoid:
                answer += f"• {html_text(item)}\n"

        if warning:
            answer += f"\n<b>Важно:</b>\n{html_text(warning)}"

        await loading_msg.delete()

        sent_answer = await message.answer(
            answer,
            parse_mode="HTML",
            reply_markup=result_menu
        )

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
            product_card_tasks = []

            for index, product in enumerate(recommended_products[:5], start=1):
                product_name = product.get("name", "").strip()
                product_category = product.get("category", "").strip()
                product_price = product.get("price_range", "").strip()
                product_why = product.get("why", "").strip()
                product_image = product.get("image_url", "").strip()

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

                image_url = get_product_image_url(product_image, product_category)
                caption = build_product_caption(
                    product_name=product_name,
                    product_category=product_category,
                    price_range=product_price,
                    why=product_why
                )

                product_card_tasks.append(asyncio.create_task(
                    prepare_product_card(
                        product_name=product_name,
                        image_url=image_url,
                        caption=caption,
                        keyboard=keyboard,
                        market_links=links,
                    )
                ))

            for task in asyncio.as_completed(product_card_tasks):
                card = await task
                await send_prepared_product_card(message, card)

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
                f"🔎 <b>Искать:</b> {html_text(main_query)}",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

            await message.answer(
                "Выбери следующий шаг:",
                reply_markup=result_menu
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


def html_text(value) -> str:
    return html.escape(str(value or ""), quote=False)


def trim_text(value, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def is_http_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_product_text(value: str) -> str:
    text = str(value or "").lower()
    replacements = {
        "ё": "е",
        "spf50+": "spf 50",
        "spf30": "spf 30",
        "spf50": "spf 50",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _product_tokens(product_name: str) -> list[str]:
    stop_words = {
        "cream",
        "крем",
        "средство",
        "очищающее",
        "солнцезащитный",
        "spf",
        "with",
        "для",
        "the",
        "and",
        "face",
    }
    tokens = _normalize_product_text(product_name).split()
    return [
        token
        for token in tokens
        if len(token) >= 3 and token not in stop_words
    ]


def _context_matches_product(product_name: str, context: str) -> bool:
    tokens = _product_tokens(product_name)
    if not tokens:
        return False

    normalized_context = _normalize_product_text(context)
    if not normalized_context:
        return False

    brand_token = tokens[0]
    if brand_token not in normalized_context:
        return False

    meaningful_tokens = tokens[1:] or tokens
    numeric_tokens = [token for token in tokens if token.isdigit() and len(token) >= 3]
    if any(token not in normalized_context for token in numeric_tokens):
        return False

    distinctive_tokens = [
        token
        for token in meaningful_tokens
        if len(token) >= 5 and not token.isdigit()
    ]
    if len(distinctive_tokens) >= 2:
        distinctive_matches = sum(
            1 for token in distinctive_tokens
            if token in normalized_context
        )
        if distinctive_matches < 2:
            return False

    matched = sum(1 for token in meaningful_tokens if token in normalized_context)
    required = 1 if len(tokens) <= 3 else max(2, len(meaningful_tokens) // 2)
    return matched >= required


def _extract_meta_image_url(page_url: str, page_html: str) -> str:
    patterns = [
        r'<meta[^>]+(?:property|name)=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image:secure_url["\']',
        r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
        r'<meta[^>]+(?:property|name)=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']twitter:image(?::src)?["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']image_src["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, re.IGNORECASE)
        if match:
            return urljoin(page_url, html.unescape(match.group(1).strip()))

    return ""


def _strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")


def _extract_candidate_image_urls(
    page_url: str,
    page_html: str,
    product_name: str = "",
    strict_match: bool = False,
) -> list[str]:
    candidates = []
    meta_image_url = _extract_meta_image_url(page_url, page_html)
    if meta_image_url:
        meta_context = page_html[:3000]
        candidates.append((meta_image_url, meta_context))

    tag_pattern = r"<(?:img|source)\b[^>]*>"

    for match in re.finditer(tag_pattern, page_html, re.IGNORECASE):
        tag = match.group(0)
        values = []
        for attr in ("src", "data-src", "data-original", "srcset"):
            attr_match = re.search(rf'\b{attr}=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if attr_match:
                values.append(html.unescape(attr_match.group(1).strip()))

        tag_text_parts = []
        for attr in ("alt", "title", "aria-label"):
            attr_match = re.search(rf'\b{attr}=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if attr_match:
                tag_text_parts.append(html.unescape(attr_match.group(1).strip()))

        context_start = max(0, match.start() - 900)
        context_end = min(len(page_html), match.end() + 900)
        surrounding_context = page_html[context_start:context_end]
        readable_context = _strip_html_tags(
            f"{' '.join(tag_text_parts)} {tag} {surrounding_context}"
        )

        for value in values:
            if " " in value or "," in value:
                srcset_parts = [part.strip().split(" ")[0] for part in value.split(",")]
                candidates.extend((part, readable_context) for part in srcset_parts)
            else:
                candidates.append((value, readable_context))

    result = []
    seen = set()
    for candidate, context in candidates:
        absolute_url = urljoin(page_url, candidate.strip())
        combined_context = f"{context} {absolute_url}"
        if strict_match and not _context_matches_product(product_name, combined_context):
            continue
        if _looks_like_product_image_url(absolute_url) and absolute_url not in seen:
            result.append(absolute_url)
            seen.add(absolute_url)

    return result


def _looks_like_product_image_url(image_url: str) -> bool:
    if not is_http_url(image_url):
        return False

    parsed = urlparse(image_url)
    path = unquote(parsed.path.lower())
    full_url = unquote(image_url.lower())
    bad_markers = [
        "logo",
        "sprite",
        "icon",
        "favicon",
        "avatar",
        "banner",
        "placeholder",
        "no-image",
        "no_image",
        "loader",
        "pixel",
        "counter",
    ]

    if any(marker in full_url for marker in bad_markers):
        return False
    if path.endswith(".svg"):
        return False

    return any(
        marker in path
        for marker in (".jpg", ".jpeg", ".png", ".webp", ".avif")
    ) or any(
        marker in full_url
        for marker in ("image", "img", "photo", "picture", "product", "cdn")
    )


def _image_filename(product_name: str, content_type: str) -> str:
    extension_by_type = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    extension = extension_by_type.get(content_type.split(";")[0].strip().lower(), "jpg")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", product_name or "product").strip("_")
    return f"{safe_name[:40] or 'product'}.{extension}"


def _prepare_telegram_photo(image_bytes: bytes, content_type: str, product_name: str) -> BufferedInputFile | None:
    content_type = content_type.split(";")[0].strip().lower()
    if content_type in {"image/jpeg", "image/jpg", "image/png"}:
        return BufferedInputFile(
            image_bytes,
            filename=_image_filename(product_name, content_type),
        )

    if content_type == "image/svg+xml":
        return None

    if Image is None:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", product_name or "product").strip("_")
        return BufferedInputFile(
            output.getvalue(),
            filename=f"{safe_name[:40] or 'product'}.jpg",
        )
    except Exception:
        return None


async def fetch_exact_product_image(
    image_url: str,
    product_name: str,
    depth: int = 0,
    strict_match: bool = False,
) -> tuple[BufferedInputFile | None, str]:
    if not is_http_url(image_url):
        return None, ""
    if depth > 2:
        return None, ""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    async with httpx.AsyncClient(
        timeout=IMAGE_FETCH_TIMEOUT,
        follow_redirects=True,
        headers=headers,
        verify=False,
    ) as client:
        try:
            response = await client.get(image_url)
            response.raise_for_status()
        except httpx.RequestError:
            return None, ""
        except httpx.HTTPStatusError:
            return None, ""

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        source_url = str(response.url)

        if content_type.startswith("image/"):
            image_bytes = response.content
            if not image_bytes:
                return None, ""
            image_file = _prepare_telegram_photo(image_bytes, content_type, product_name)
            if not image_file:
                return None, ""
            return (
                image_file,
                source_url,
            )

        if "html" not in content_type:
            return None, ""

        page_html = response.text
        candidate_urls = _extract_candidate_image_urls(
            source_url,
            page_html,
            product_name=product_name,
            strict_match=True,
        )
        for candidate_url in candidate_urls[:8]:
            if candidate_url == image_url:
                continue
            image_file, resolved_url = await fetch_exact_product_image(
                candidate_url,
                product_name,
                depth=depth + 1,
                strict_match=False,
            )
            if image_file:
                return image_file, resolved_url

        return None, ""


async def find_product_image_from_marketplaces(
    product_name: str,
    market_links: dict | None,
) -> tuple[BufferedInputFile | None, str]:
    if not market_links:
        return None, ""

    for source_url in market_links.values():
        image_file, resolved_url = await fetch_exact_product_image(source_url, product_name)
        if image_file:
            return image_file, resolved_url

    return None, ""


def _extract_duckduckgo_vqd(page_html: str) -> str:
    patterns = [
        r'vqd=["\']([^"\']+)["\']',
        r"vqd=([^&'\"]+)",
        r"vqd\s*:\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html)
        if match:
            return html.unescape(match.group(1))
    return ""


def _decode_search_text(value: str) -> str:
    value = html.unescape(str(value or ""))
    try:
        value = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda match: chr(int(match.group(1), 16)),
            value,
        )
    except Exception:
        pass
    return value.replace("\\/", "/")


def _remove_search_query_noise(context: str) -> str:
    context = re.sub(r"([?&]|&amp;)(text|q|query)=[^&\"'\s]+", " ", context, flags=re.IGNORECASE)
    context = re.sub(r"\b(text|q|query)=[^&\"'\s]+", " ", context, flags=re.IGNORECASE)
    return context


def _extract_yandex_image_candidates(page_html: str) -> list[tuple[str, str]]:
    candidates = []
    for match in re.finditer(r"&quot;(?:origUrl|img_url)&quot;:&quot;(.*?)&quot;", page_html):
        raw_url = _decode_search_text(match.group(1))
        if not is_http_url(raw_url):
            continue

        context_start = max(0, match.start() - 1800)
        context_end = min(len(page_html), match.end() + 1800)
        context = _remove_search_query_noise(
            _decode_search_text(page_html[context_start:context_end])
        )
        candidates.append((raw_url, context))

    seen = set()
    result = []
    for image_url, context in candidates:
        if image_url in seen:
            continue
        seen.add(image_url)
        result.append((image_url, context))
    return result


async def _search_yandex_product_image_query(
    product_name: str,
    query: str,
) -> tuple[BufferedInputFile | None, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,*/*",
    }

    try:
        async with httpx.AsyncClient(
            timeout=IMAGE_SEARCH_TIMEOUT,
            follow_redirects=True,
            headers=headers,
            verify=False,
        ) as client:
            response = await client.get(
                "https://yandex.ru/images/search",
                params={"text": query},
            )
            response.raise_for_status()
            page_html = response.text
    except Exception:
        return None, ""

    for image_url, context in _extract_yandex_image_candidates(page_html)[:20]:
        if not _context_matches_product(product_name, f"{context} {image_url}"):
            continue
        image_file, resolved_url = await fetch_exact_product_image(image_url, product_name)
        if image_file:
            return image_file, resolved_url

    return None, ""


def _duckduckgo_result_matches_product(product_name: str, result: dict) -> bool:
    context_parts = [
        result.get("title", ""),
        result.get("url", ""),
        result.get("source", ""),
        result.get("image", ""),
    ]
    return _context_matches_product(product_name, " ".join(context_parts))


def _product_image_search_queries(product_name: str) -> list[str]:
    base = str(product_name or "").strip()
    if not base:
        return []

    return [
        f'"{base}"',
        f'"{base}" official product image',
        f'"{base}" фото товара',
        f'"{base}" купить фото',
        f'"{base}" site:ozon.ru',
        f'"{base}" site:goldapple.ru',
        f'"{base}" site:market.yandex.ru',
        f'"{base}" site:wildberries.ru',
    ]


async def _search_product_image_online_query(
    product_name: str,
    query: str,
) -> tuple[BufferedInputFile | None, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json,*/*",
    }

    try:
        async with httpx.AsyncClient(
            timeout=IMAGE_SEARCH_TIMEOUT,
            follow_redirects=True,
            headers=headers,
            verify=False,
        ) as client:
            search_url = (
                "https://duckduckgo.com/?q="
                f"{quote_plus(query)}&iar=images&iax=images&ia=images"
            )
            search_response = await client.get(search_url)
            search_response.raise_for_status()
            vqd = _extract_duckduckgo_vqd(search_response.text)
            if not vqd:
                return None, ""

            images_response = await client.get(
                "https://duckduckgo.com/i.js",
                params={
                    "l": "ru-ru",
                    "o": "json",
                    "q": query,
                    "vqd": vqd,
                    "f": ",,,",
                    "p": "1",
                },
                headers={**headers, "Referer": search_url},
            )
            images_response.raise_for_status()
            data = images_response.json()
    except Exception:
        return None, ""

    results = data.get("results", [])
    if not isinstance(results, list):
        return None, ""

    candidates = [
        result for result in results
        if isinstance(result, dict) and _duckduckgo_result_matches_product(product_name, result)
    ]

    for result in candidates[:12]:
        image_url = result.get("image") or result.get("thumbnail")
        if not image_url:
            continue
        image_file, resolved_url = await fetch_exact_product_image(image_url, product_name)
        if image_file:
            return image_file, resolved_url

    return None, ""


async def search_product_image_online(product_name: str) -> tuple[BufferedInputFile | None, str]:
    for query in _product_image_search_queries(product_name)[:MAX_IMAGE_SEARCH_QUERIES]:
        image_file, resolved_url = await _search_yandex_product_image_query(
            product_name,
            query,
        )
        if image_file:
            return image_file, resolved_url

        image_file, resolved_url = await _search_product_image_online_query(
            product_name,
            query,
        )
        if image_file:
            return image_file, resolved_url

    return None, ""


async def resolve_product_card_image(
    image_url: str,
    product_name: str,
    market_links: dict | None = None,
) -> tuple[BufferedInputFile | None, str]:
    image_file, resolved_image_url = await fetch_exact_product_image(image_url, product_name)
    if not image_file:
        image_file, resolved_image_url = await find_product_image_from_marketplaces(
            product_name,
            market_links,
        )
    if not image_file:
        image_file, resolved_image_url = await search_product_image_online(product_name)

    return image_file, resolved_image_url


async def prepare_product_card(
    product_name: str,
    image_url: str,
    caption: str,
    keyboard: InlineKeyboardMarkup,
    market_links: dict | None = None,
) -> dict:
    image_file = None
    resolved_image_url = ""

    try:
        image_file, resolved_image_url = await asyncio.wait_for(
            resolve_product_card_image(
                image_url=image_url,
                product_name=product_name,
                market_links=market_links,
            ),
            timeout=IMAGE_CARD_TIMEOUT,
        )
    except Exception:
        pass

    return {
        "caption": caption,
        "image_file": image_file,
        "keyboard": keyboard,
        "product_name": product_name,
        "resolved_image_url": resolved_image_url,
    }


async def send_prepared_product_card(message: Message, card: dict) -> None:
    image_file = card.get("image_file")
    caption = card["caption"]
    keyboard = card["keyboard"]

    if image_file:
        try:
            await message.answer_photo(
                photo=image_file,
                caption=trim_text(caption, 1024),
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    await message.answer(
        trim_text(caption, 4096),
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def send_product_card(
    message: Message,
    image_url: str,
    caption: str,
    keyboard: InlineKeyboardMarkup,
    product_name: str,
    market_links: dict | None = None,
) -> None:
    card = await prepare_product_card(
        product_name=product_name,
        image_url=image_url,
        caption=caption,
        keyboard=keyboard,
        market_links=market_links,
    )
    await send_prepared_product_card(message, card)


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


def get_category_placeholder_image(category: str) -> str:
    if not category:
        return "https://via.placeholder.com/800x800.png?text=Beauty+Product"

    category = category.lower()
    if "крем" in category:
        return "https://via.placeholder.com/800x800.png?text=Face+Cream"
    if "сыворот" in category:
        return "https://via.placeholder.com/800x800.png?text=Serum"
    if "гель" in category or "пенк" in category or "очищ" in category:
        return "https://via.placeholder.com/800x800.png?text=Cleanser"
    if "маск" in category:
        return "https://via.placeholder.com/800x800.png?text=Mask"
    if "spf" in category or "солнц" in category:
        return "https://via.placeholder.com/800x800.png?text=SPF"

    return "https://via.placeholder.com/800x800.png?text=Beauty+Product"


def get_product_image_url(image_url: str, category: str) -> str:
    if image_url and image_url.lower().startswith("http"):
        return image_url
    return ""


def normalize_price_range(price_range: str) -> str:
    price = str(price_range or "").strip()
    price = re.sub(r"\s*(?:-|–|—)\s*", " – ", price)
    price = re.sub(r"\s+", " ", price).strip()
    return price


def format_price_range(price_range: str) -> str:
    if not price_range:
        return "💵 <b>Цена:</b> ориентировочно"

    price = normalize_price_range(price_range)
    if not price:
        return "💵 <b>Цена:</b> ориентировочно"

    return f"💵 <b>Цена:</b> <code>{html_text(price)}</code>"


def build_product_caption(product_name: str, product_category: str, price_range: str, why: str) -> str:
    emoji = get_category_emoji(product_category)
    category_text = html_text(product_category or "Средство")
    product_text = html_text(product_name)
    title = f"{emoji} <b>{category_text}</b>\n<code>{product_text}</code>"
    price_text = format_price_range(price_range)

    caption = f"{title}\n\n{price_text}"
    if why:
        caption += f"\n\n{html_text(why)}"

    return caption

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
    total_recommended_products = get_total_recommended_products()
    feedback_stats = get_feedback_stats()
    product_feedback_stats = get_product_feedback_stats()
    top_products = get_product_stats(limit=5)

    # Формирование ответа
    text = "📊 <b>Статистика администратора</b>\n\n"

    text += f"<b>Пользователи:</b>\n👥 Всего: {total_users}\n\n"
    text += f"<b>Активных пользователей:</b>\n👤 С рекомендациями: {min(total_users, total_recommendations or 0)}\n\n"

    text += f"<b>Запросы к AI:</b>\n🤖 Всего рекомендаций: {total_recommendations}\n"
    text += f"🛍️ Всего товаров сохранено: {total_recommended_products}\n\n"

    text += f"<b>Оценки подборов:</b>\n"
    text += f"👍 Полезно: {feedback_stats['likes']}\n"
    text += f"👎 Не подошло: {feedback_stats['dislikes']}\n"
    text += f"⏳ Всего оценено: {feedback_stats['total']}\n"
    if feedback_stats['total'] > 0:
        like_rate = round((feedback_stats['likes'] / feedback_stats['total']) * 100)
        text += f" ({like_rate}% положительных)\n"
    text += "\n"

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

