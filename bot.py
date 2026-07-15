import html
import io
import os
import re
import asyncio
from contextlib import suppress
from pathlib import Path
from urllib.parse import quote_plus, unquote, urljoin, urlparse

import httpx

try:
    from PIL import Image
except ImportError:
    Image = None

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    FSInputFile,
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from ai_client import BeautyServiceBusyError, ask_deepseek
from beauty_flow import (
    MODE_LABELS,
    animate_intro,
    animate_search,
    build_query,
    choose_option,
    flow_keyboard,
    flow_text,
    get_session,
    main_inline_keyboard,
    main_text,
    mode_inline_keyboard,
    mode_text,
    previous_step,
    result_inline_keyboard,
    safe_edit,
    saved_answers_context,
    saved_profile_keyboard,
    saved_profile_text,
    serialize_answers,
    skip_step,
    start_flow,
)

from database import (
    init_db,
    save_user,
    update_user_profile,
    get_user_profile,
    get_beauty_profile,
    get_user_beauty_state,
    save_beauty_profile,
    save_user_beauty_state,
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
WEBSITE_URL = "https://krasavitsa-ai.ru/"
BASE_DIR = Path(__file__).resolve().parent

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

ACTIVE_MODES: dict[int, str] = {}
MODE_ASSET_PATHS = {
    "skin": BASE_DIR / "assets" / "skin-packshot-v2.webp",
    "hair": BASE_DIR / "assets" / "hair-packshot-v2.webp",
    "perfume": BASE_DIR / "assets" / "perfume-packshot-v2.webp",
}
WELCOME_ASSET_PATH = BASE_DIR / "assets" / "welcome-v1.png"

IMAGE_FETCH_TIMEOUT = 4
IMAGE_SEARCH_TIMEOUT = 4
IMAGE_CARD_TIMEOUT = 5
MAX_IMAGE_SEARCH_QUERIES = 1


def website_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть сайт Красавицы", url=WEBSITE_URL)]
    ])


def build_website_note() -> str:
    return (
        "Если удобнее выбирать с экрана побольше, у «Красавицы» есть сайт — "
        f"{WEBSITE_URL}"
    )

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="💧 Кожа"),
            KeyboardButton(text="💇‍♀️ Волосы"),
            KeyboardButton(text="🌸 Парфюм"),
        ],
        [
            KeyboardButton(text="✨ Новый подбор"),
            KeyboardButton(text="👤 Мой профиль"),
        ],
        [
            KeyboardButton(text="📜 Мои подборы"),
            KeyboardButton(text="📂 Избранное"),
        ],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Опишите, что хотите подобрать…",
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
            KeyboardButton(text="🔖 В избранное"),
            KeyboardButton(text="📂 Избранное")
        ],
        [
            KeyboardButton(text="◀️ В главное меню")
        ],
    ],
    resize_keyboard=True
)

hair_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🫧 Жирные корни"), KeyboardButton(text="🎨 Окрашенная длина")],
        [KeyboardButton(text="➰ Кудри и пористость"), KeyboardButton(text="🔥 Термозащита")],
        [KeyboardButton(text="✍️ Свой запрос о волосах")],
        [KeyboardButton(text="◀️ В главное меню")],
    ],
    resize_keyboard=True,
)

perfume_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🫧 Чистый мускус"), KeyboardButton(text="🌿 Несладкая свежесть")],
        [KeyboardButton(text="🌙 Вечерний аромат"), KeyboardButton(text="🎁 Аромат в подарок")],
        [KeyboardButton(text="✍️ Свой запрос об аромате")],
        [KeyboardButton(text="◀️ В главное меню")],
    ],
    resize_keyboard=True,
)


def has_saved_beauty_profile(user_id: int) -> bool:
    return any(
        bool((get_beauty_profile(user_id, mode) or {}).get("answers"))
        for mode in MODE_LABELS
    )


def welcome_panel(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    if has_saved_beauty_profile(user_id):
        return (
            "<b>С возвращением</b>\n\nМожно использовать сохранённые параметры или начать новый подбор.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Использовать мой профиль", callback_data="onboarding:use")],
                [InlineKeyboardButton(text="Новый подбор", callback_data="onboarding:skip")],
            ]),
        )
    return (
        "<b>Сделать подбор точнее?</b>\n\nМожно один раз создать beauty-профиль — выбранные параметры сохранятся. Это необязательно.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Создать профиль", callback_data="onboarding:create")],
            [InlineKeyboardButton(text="Продолжить без профиля", callback_data="onboarding:skip")],
        ]),
    )

@dp.message(CommandStart())
async def start(message: Message):
    save_user(
        user_id=message.from_user.id,
        username=message.from_user.username
    )
    welcome_photo = FSInputFile(WELCOME_ASSET_PATH) if WELCOME_ASSET_PATH.is_file() else None
    panel_text, panel_keyboard = welcome_panel(message.from_user.id)
    await animate_intro(
        message,
        welcome_photo=welcome_photo,
        reply_keyboard=main_menu,
        panel_text=panel_text,
        panel_keyboard=panel_keyboard,
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = (
        "Чтобы подбор был точнее, укажи цель, важные ограничения и бюджет.\n\n"
        "💧 Кожа: тип, чувствительность, текущий уход и желаемая текстура.\n"
        "💇‍♀️ Волосы: отдельно кожа головы и длина, окрашивание, укладка.\n"
        "🌸 Парфюм: любимые и нежелательные ноты, повод, сезон и громкость.\n\n"
        "Если данных недостаточно, я задам один конкретный вопрос.\n\n"
        f"Ещё можно спокойно попробовать сайт: {WEBSITE_URL}"
    )

    await message.answer(text, reply_markup=website_keyboard())


@dp.message(Command("site"))
async def site_cmd(message: Message):
    await message.answer(
        build_website_note(),
        reply_markup=website_keyboard()
    )


async def show_mode_screen(message: Message, user_id: int, mode: str, edit: bool = False) -> None:
    ACTIVE_MODES[user_id] = mode
    save_user_beauty_state(user_id, mode)
    saved_profile = get_beauty_profile(user_id, mode) or {}
    keyboard = mode_inline_keyboard(mode, has_saved_profile=bool(saved_profile.get("answers")))
    if edit:
        await render_panel(message, mode_text(mode), keyboard)
    else:
        await message.answer(mode_text(mode), parse_mode="HTML", reply_markup=keyboard)


async def render_panel(
    message: Message,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> Message:
    if await safe_edit(message, text, keyboard):
        return message
    return await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


def load_flow_session(user_id: int, mode: str, preserve_saved: bool = True):
    saved = get_beauty_profile(user_id, mode) if preserve_saved else None
    return start_flow(user_id, mode, answers=(saved or {}).get("answers", {}))


def persist_flow_session(user_id: int, session) -> None:
    save_beauty_profile(
        user_id=user_id,
        mode=session.mode,
        answers=serialize_answers(session),
        current_step=session.step,
    )


def retry_keyboard(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Повторить запрос", callback_data="retry:last")],
        [
            InlineKeyboardButton(text="Изменить параметры", callback_data=f"saved:{mode}"),
            InlineKeyboardButton(text="Главное меню", callback_data="menu:main"),
        ],
    ])


def profile_modes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Кожа", callback_data="saved:skin"),
            InlineKeyboardButton(text="Волосы", callback_data="saved:hair"),
            InlineKeyboardButton(text="Парфюм", callback_data="saved:perfume"),
        ],
        [InlineKeyboardButton(text="Главное меню", callback_data="menu:main")],
    ])


@dp.message(Command("pick"))
async def pick_command(message: Message):
    save_user(user_id=message.from_user.id, username=message.from_user.username)
    await message.answer("Фирменное меню закреплено под строкой ввода.", reply_markup=main_menu)
    await message.answer(main_text(), parse_mode="HTML", reply_markup=main_inline_keyboard())


@dp.message(Command("skin"))
async def skin_command(message: Message):
    await show_mode_screen(message, message.from_user.id, "skin")


@dp.message(Command("hair"))
async def hair_command(message: Message):
    await show_mode_screen(message, message.from_user.id, "hair")


@dp.message(Command("perfume"))
async def perfume_command(message: Message):
    await show_mode_screen(message, message.from_user.id, "perfume")


@dp.message(Command("profile"))
async def profile_command(message: Message):
    await message.answer(
        "<b>Мои параметры</b>\n\nВыбери направление — покажу всё, что уже сохранено.",
        parse_mode="HTML",
        reply_markup=profile_modes_keyboard(),
    )


@dp.message(F.text == "👤 Мой профиль")
async def profile_keyboard_button(message: Message):
    await profile_command(message)


@dp.message(F.text == "✨ Новый подбор")
async def new_selection_keyboard_button(message: Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    await message.answer(main_text(), parse_mode="HTML", reply_markup=main_inline_keyboard())


@dp.callback_query(F.data == "onboarding:create")
async def callback_onboarding_create(callback: CallbackQuery):
    await callback.answer()
    if not callback.message:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Кожа", callback_data="guide:skin"),
            InlineKeyboardButton(text="Волосы", callback_data="guide:hair"),
            InlineKeyboardButton(text="Парфюм", callback_data="guide:perfume"),
        ],
        [InlineKeyboardButton(text="Продолжить без профиля", callback_data="onboarding:skip")],
    ])
    await render_panel(
        callback.message,
        "<b>Создание beauty-профиля</b>\n\nВыберите направление. Каждый ответ сохранится автоматически, а профиль всегда можно изменить.",
        keyboard,
    )


@dp.callback_query(F.data == "onboarding:use")
async def callback_onboarding_use(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await render_panel(
            callback.message,
            "<b>Мои параметры</b>\n\nВыберите сохранённое направление.",
            profile_modes_keyboard(),
        )


@dp.callback_query(F.data == "onboarding:skip")
async def callback_onboarding_skip(callback: CallbackQuery):
    await callback.answer("Профиль можно создать позже")
    if callback.message:
        await render_panel(callback.message, main_text(), main_inline_keyboard())


@dp.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await render_panel(callback.message, main_text(), main_inline_keyboard())


@dp.callback_query(F.data == "free:text")
async def callback_free_text(callback: CallbackQuery):
    await callback.answer("Можно писать своими словами")
    if callback.message:
        await render_panel(
            callback.message,
            "⌨️ <b>Свободный запрос</b>\n\nНапишите, что хочется подобрать. Я сама определю направление и задам только действительно важный вопрос.",
            InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="menu:main")]]),
        )


@dp.callback_query(F.data.startswith("mode:"))
async def callback_mode(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    if mode not in MODE_LABELS or not callback.message:
        await callback.answer("Направление недоступно", show_alert=True)
        return
    await callback.answer()
    await show_mode_screen(callback.message, callback.from_user.id, mode, edit=True)


@dp.callback_query(F.data.startswith("guide:"))
async def callback_guide(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    if mode not in MODE_LABELS or not callback.message:
        await callback.answer("Не удалось открыть сценарий", show_alert=True)
        return
    session = load_flow_session(callback.from_user.id, mode, preserve_saved=True)
    session.step = 0
    persist_flow_session(callback.from_user.id, session)
    ACTIVE_MODES[callback.from_user.id] = mode
    await callback.answer()
    await render_panel(callback.message, flow_text(session), flow_keyboard(session))


async def run_callback_search(callback: CallbackQuery, mode: str, query: str) -> None:
    if not callback.message:
        return
    ACTIVE_MODES[callback.from_user.id] = mode
    save_user_beauty_state(callback.from_user.id, mode, query)
    status_message = await render_panel(callback.message, f"{MODE_LABELS[mode]}\n\nНачинаю персональный подбор…")
    await perform_search(
        message=status_message,
        requester_id=callback.from_user.id,
        requester_username=callback.from_user.username,
        text_to_process=query,
        mode=mode,
        status_message=status_message,
    )


@dp.callback_query(F.data.startswith("direct:"))
async def callback_direct(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    if mode not in MODE_LABELS:
        await callback.answer("Направление недоступно", show_alert=True)
        return
    await callback.answer("Начинаю подбор")
    await run_callback_search(callback, mode, build_query(None, mode, exploratory=True))


@dp.callback_query(F.data.startswith("flow:"))
async def callback_flow_option(callback: CallbackQuery):
    parts = (callback.data or "").split(":", 3)
    if len(parts) != 4 or parts[1] not in MODE_LABELS or not callback.message:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    mode, step_text, value = parts[1], parts[2], parts[3]
    try:
        step_index = int(step_text)
    except ValueError:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    session, complete = choose_option(callback.from_user.id, mode, step_index, value)
    persist_flow_session(callback.from_user.id, session)
    await callback.answer("Выбрано")
    if complete:
        await run_callback_search(callback, mode, build_query(session, mode))
        return
    await render_panel(callback.message, flow_text(session), flow_keyboard(session))


@dp.callback_query(F.data.startswith("skip:"))
async def callback_skip_step(callback: CallbackQuery):
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3 or parts[1] not in MODE_LABELS or not callback.message:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    mode = parts[1]
    try:
        step_index = int(parts[2])
    except ValueError:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    session, complete = skip_step(callback.from_user.id, mode, step_index)
    persist_flow_session(callback.from_user.id, session)
    await callback.answer("Пропущено")
    if complete:
        await run_callback_search(callback, mode, build_query(session, mode, exploratory=True))
        return
    await render_panel(callback.message, flow_text(session), flow_keyboard(session))


@dp.callback_query(F.data.startswith("back:"))
async def callback_previous_step(callback: CallbackQuery):
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3 or parts[1] not in MODE_LABELS or not callback.message:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    try:
        step_index = int(parts[2])
    except ValueError:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    session = previous_step(callback.from_user.id, parts[1], step_index)
    persist_flow_session(callback.from_user.id, session)
    await callback.answer()
    await render_panel(callback.message, flow_text(session), flow_keyboard(session))


@dp.callback_query(F.data.startswith("finish:"))
async def callback_finish_flow(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    if mode not in MODE_LABELS:
        await callback.answer("Направление недоступно", show_alert=True)
        return
    session = get_session(callback.from_user.id, mode)
    if session:
        persist_flow_session(callback.from_user.id, session)
    await callback.answer("Собираю варианты")
    await run_callback_search(callback, mode, build_query(session, mode, exploratory=True))


@dp.callback_query(F.data.startswith("saved:"))
async def callback_saved_profile(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    if mode not in MODE_LABELS or not callback.message:
        await callback.answer("Профиль недоступен", show_alert=True)
        return
    session = load_flow_session(callback.from_user.id, mode, preserve_saved=True)
    await callback.answer()
    await render_panel(
        callback.message,
        saved_profile_text(session),
        saved_profile_keyboard(mode, bool(session.answers)),
    )


@dp.callback_query(F.data.startswith("edit_saved:"))
async def callback_edit_saved_profile(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    if mode not in MODE_LABELS or not callback.message:
        await callback.answer("Профиль недоступен", show_alert=True)
        return
    session = load_flow_session(callback.from_user.id, mode, preserve_saved=True)
    session.step = 0
    persist_flow_session(callback.from_user.id, session)
    await callback.answer()
    await render_panel(callback.message, flow_text(session), flow_keyboard(session))


@dp.callback_query(F.data.startswith("use_saved:"))
async def callback_use_saved_profile(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    if mode not in MODE_LABELS or not callback.message:
        await callback.answer("Профиль недоступен", show_alert=True)
        return
    session = load_flow_session(callback.from_user.id, mode, preserve_saved=True)
    if not session.answers:
        await callback.answer("Сначала выбери параметры", show_alert=True)
        return
    await callback.answer("Использую сохранённые параметры")
    await run_callback_search(callback, mode, build_query(session, mode))


@dp.callback_query(F.data.in_({"repeat:last", "retry:last"}))
async def callback_repeat_last(callback: CallbackQuery):
    if not callback.message:
        await callback.answer()
        return
    state = get_user_beauty_state(callback.from_user.id) or {}
    mode = state.get("last_query_mode") or state.get("active_mode")
    query = str(state.get("last_query") or "").strip()
    if mode not in MODE_LABELS or not query:
        await callback.answer("Сохранённого запроса пока нет", show_alert=True)
        return
    await callback.answer("Повторяю последний подбор")
    await run_callback_search(callback, mode, query)


@dp.message(F.text == "💧 Кожа")
async def choose_skin_mode(message: Message):
    await show_mode_screen(message, message.from_user.id, "skin")


@dp.message(F.text == "💇‍♀️ Волосы")
async def choose_hair_mode(message: Message):
    await show_mode_screen(message, message.from_user.id, "hair")


@dp.message(F.text == "🌸 Парфюм")
async def choose_perfume_mode(message: Message):
    await show_mode_screen(message, message.from_user.id, "perfume")

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


@dp.message(F.text == "🫧 Жирные корни")
async def scenario_oily_scalp(message: Message):
    ACTIVE_MODES[message.from_user.id] = "hair"
    await run_scenario(message, "Проверяю уход для кожи головы и длины…", "Кожа головы быстро жирнится, длина не обязательно жирная. Подбери деликатный базовый уход и уточни недостающие данные.")


@dp.message(F.text == "🎨 Окрашенная длина")
async def scenario_colored_hair(message: Message):
    ACTIVE_MODES[message.from_user.id] = "hair"
    await run_scenario(message, "Проверяю уход для окрашенной длины…", "Окрашенные волосы, нужна защита длины от сухости и ломкости. Подбери базовый уход без лечебных обещаний.")


@dp.message(F.text == "➰ Кудри и пористость")
async def scenario_curly_hair(message: Message):
    ACTIVE_MODES[message.from_user.id] = "hair"
    await run_scenario(message, "Собираю уход для завитка…", "Кудрявые пористые волосы, хочу выраженный завиток без тяжёлого перегруза. Подбери базовые категории и средства.")


@dp.message(F.text == "🔥 Термозащита")
async def scenario_heat_protection(message: Message):
    ACTIVE_MODES[message.from_user.id] = "hair"
    await run_scenario(message, "Проверяю термозащиту…", "Регулярно использую горячую укладку. Нужна термозащита и поддерживающий уход для длины.")


@dp.message(F.text.in_({"✍️ Свой запрос о волосах", "✍️ Свой запрос об аромате"}))
async def scenario_custom_mode(message: Message):
    mode = "hair" if "волос" in message.text.lower() else "perfume"
    ACTIVE_MODES[message.from_user.id] = mode
    await message.answer("Опиши запрос свободно. Чем точнее предпочтения, ограничения и бюджет, тем надёжнее подбор.")


@dp.message(F.text == "🫧 Чистый мускус")
async def scenario_clean_musk(message: Message):
    ACTIVE_MODES[message.from_user.id] = "perfume"
    await run_scenario(message, "Ищу проверенные чистые мускусы…", "Хочу чистый мягкий мускусный аромат без выраженной сладости. Нужен вариант на каждый день.")


@dp.message(F.text == "🌿 Несладкая свежесть")
async def scenario_fresh_perfume(message: Message):
    ACTIVE_MODES[message.from_user.id] = "perfume"
    await run_scenario(message, "Ищу несладкую свежесть…", "Хочу свежий несладкий аромат без резкой бытовой или акватической ноты.")


@dp.message(F.text == "🌙 Вечерний аромат")
async def scenario_evening_perfume(message: Message):
    ACTIVE_MODES[message.from_user.id] = "perfume"
    await run_scenario(message, "Собираю вечернее направление…", "Нужен выразительный вечерний аромат. Сначала учти желаемые ноты, сезон, громкость и бюджет.")


@dp.message(F.text == "🎁 Аромат в подарок")
async def scenario_gift_perfume(message: Message):
    ACTIVE_MODES[message.from_user.id] = "perfume"
    await run_scenario(message, "Проверяю варианты для подарка…", "Ищу аромат в подарок. Нужен осторожный подбор с вопросом о любимых нотах, возраст не используй как жёсткий фильтр.")

@dp.message(F.text == "📝 Другое")
async def scenario_other(message: Message):
    await message.answer(
        "Опиши, что беспокоит кожу:\n\n"
        "Например:\n"
        "«Комбинированная кожа, жирный блеск в Т-зоне, щеки сухие, хочу базовый уход до 3000 ₽»"
    )

@dp.message(F.text == "◀️ В главное меню")
async def back_to_main_menu(message: Message):
    await message.answer(main_text(), parse_mode="HTML", reply_markup=main_inline_keyboard())

@dp.message(F.text == "🔄 Ещё подбор")
async def another_selection(message: Message):
    await message.answer(main_text(), parse_mode="HTML", reply_markup=main_inline_keyboard())

@dp.message(F.text == "до 1000 ₽")
async def budget_1000(message: Message):
    update_user_profile(message.from_user.id, budget="до 1000 ₽")
    await message.answer(
        "Сохранил твой бюджет: <b>до 1000 ₽</b> ✅\n\n"
        "Теперь выбери направление и опиши задачу — бюджет будет учтён.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(F.text == "до 3000 ₽")
async def budget_3000(message: Message):
    update_user_profile(message.from_user.id, budget="до 3000 ₽")
    await message.answer(
        "Сохранил твой бюджет: <b>до 3000 ₽</b> ✅\n\n"
        "Теперь выбери направление и опиши задачу — бюджет будет учтён.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(F.text == "до 6000 ₽")
async def budget_6000(message: Message):
    update_user_profile(message.from_user.id, budget="до 6000 ₽")
    await message.answer(
        "Сохранил твой бюджет: <b>до 6000 ₽</b> ✅\n\n"
        "Теперь выбери направление и опиши задачу — бюджет будет учтён.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(F.text == "без ограничений")
async def budget_unlimited(message: Message):
    update_user_profile(message.from_user.id, budget="без ограничений")
    await message.answer(
        "Сохранил твой бюджет: <b>без ограничений</b> 👑\n\n"
        "Теперь выбери направление и опиши задачу — бюджет будет учтён.",
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
        "Я показываю кнопку только тогда, когда удалось подтвердить отдельную карточку конкретного товара.\n\n"
        "Общие страницы поиска и категории намеренно не выдаются: если точную карточку подтвердить нельзя, ссылки в результате не будет.\n\n"
        f"А ещё можно открыть сайт проекта: {WEBSITE_URL}",
        reply_markup=website_keyboard()
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


@dp.message(Command("admin_stats"))
async def admin_stats_command(message: Message):
    await admin_stats(message)


COSMETIC_REQUEST_KEYWORDS = {
    "акне",
    "антиоксидант",
    "блеск",
    "бюджет",
    "воспал",
    "гель",
    "гидрофил",
    "дермат",
    "жирн",
    "защит",
    "кожа",
    "кожи",
    "комед",
    "комбинир",
    "космет",
    "крем",
    "лосьон",
    "маска",
    "морщ",
    "очищ",
    "пенк",
    "пилинг",
    "покрас",
    "пор",
    "прыщ",
    "раздраж",
    "ретин",
    "салицил",
    "себум",
    "серум",
    "сияни",
    "солнц",
    "средств",
    "сыворот",
    "сух",
    "тоник",
    "тонер",
    "увлаж",
    "угр",
    "уход",
    "шелуш",
    "волос",
    "кожа головы",
    "шампун",
    "кондиционер",
    "порист",
    "кудр",
    "окраш",
    "ломк",
    "термозащит",
    "аромат",
    "парфюм",
    "духи",
    "нота",
    "шлейф",
    "мускус",
    "ваниль",
    "древес",
    "цитрус",
    "spf",
    "uv",
}

NON_COSMETIC_SHORT_PHRASES = {
    "как дела",
    "как ты",
    "привет",
    "здравствуй",
    "здравствуйте",
    "добрый день",
    "доброе утро",
    "добрый вечер",
    "спасибо",
    "ок",
    "хорошо",
}

THANKS_PHRASES = {
    "спасибо",
    "спасиб",
    "спс",
    "благодарю",
    "мерси",
    "thanks",
    "thank you",
}

NON_COSMETIC_PATTERNS = [
    re.compile(r"\bхочу\s+в\s+[а-яёa-z-]+", re.IGNORECASE),
    re.compile(r"\bпоеду\s+в\s+[а-яёa-z-]+", re.IGNORECASE),
    re.compile(r"\bкуда\s+сходить\b", re.IGNORECASE),
    re.compile(r"\bчто\s+посмотреть\b", re.IGNORECASE),
]


def normalize_user_request_text(text: str) -> str:
    text = str(text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s+.-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_cosmetic_request(text: str) -> bool:
    normalized = normalize_user_request_text(text)
    if not normalized:
        return False

    if normalized in NON_COSMETIC_SHORT_PHRASES:
        return False

    if any(pattern.search(normalized) for pattern in NON_COSMETIC_PATTERNS):
        return False

    return any(keyword in normalized for keyword in COSMETIC_REQUEST_KEYWORDS)


def is_thanks_message(text: str) -> bool:
    normalized = normalize_user_request_text(text)
    return normalized in THANKS_PHRASES


def build_thanks_reply() -> str:
    return "Рада помочь 🙂 Если захочешь ещё подбор — просто напиши, что ищем."


def build_offtopic_reply() -> str:
    return (
        "Я специализируюсь на косметике: коже, волосах и ароматах 🙂\n\n"
        "Выбери направление кнопкой или опиши beauty-задачу, ограничения и бюджет — я аккуратно помогу.\n\n"
        f"Если удобнее в браузере, сайт тоже рядом: {WEBSITE_URL}"
    )


def detect_mode(text: str) -> str | None:
    normalized = normalize_user_request_text(text)
    perfume_words = ("аромат", "парфюм", "духи", "нота", "шлейф", "мускус", "ваниль", "цитрус")
    hair_words = ("волос", "кожа головы", "шампун", "кондиционер", "кудр", "порист", "окраш", "термозащит")
    skin_words = ("кожа", "лицо", "крем", "сыворот", "очищ", "акне", "spf")
    if any(word in normalized for word in perfume_words):
        return "perfume"
    if any(word in normalized for word in hair_words):
        return "hair"
    if any(word in normalized for word in skin_words):
        return "skin"
    return None


async def perform_search(
    message: Message,
    requester_id: int,
    requester_username: str | None,
    text_to_process: str,
    mode: str,
    status_message: Message | None = None,
) -> None:
    save_user(user_id=requester_id, username=requester_username)
    ACTIVE_MODES[requester_id] = mode
    save_user_beauty_state(requester_id, mode, text_to_process)
    if status_message is None:
        status_message = await message.answer(f"Проверяю запрос: {MODE_LABELS[mode].lower()}…")
    animation_done = asyncio.Event()
    animation_task = asyncio.create_task(animate_search(status_message, mode, animation_done))
    try:
        saved_profile = get_user_profile(requester_id) or {}
        profile_notes = []
        if saved_profile.get("budget"):
            profile_notes.append(f"Сохранённый бюджет на один товар: {saved_profile['budget']}")
        if mode == "skin" and saved_profile.get("skin_type"):
            profile_notes.append(f"Сохранённый тип кожи: {saved_profile['skin_type']}")
        beauty_profile = get_beauty_profile(requester_id, mode) or {}
        beauty_context = saved_answers_context(mode, beauty_profile.get("answers", {}))
        if beauty_context:
            profile_notes.append(
                "Сохранённый beauty-профиль: " + beauty_context
                + ". Если текущий запрос отличается, приоритет у текущего запроса."
            )
        ai_request = text_to_process
        if profile_notes:
            ai_request += "\n\nКонтекст профиля, который тоже нужно учесть:\n" + "\n".join(profile_notes)
        data = await ask_deepseek(ai_request, mode=mode)
        summary = _as_bot_text(data.get("summary"))
        follow_up = _as_bot_text(data.get("followUpQuestion"))
        products = data.get("products") if isinstance(data.get("products"), list) else []

        animation_done.set()
        animation_task.cancel()
        with suppress(asyncio.CancelledError):
            await animation_task
        if data.get("status") != "complete" or not products:
            reply = f"<b>{html_text(MODE_LABELS[mode])}</b>\n\n{html_text(summary)}"
            if follow_up:
                reply += f"\n\n<b>Уточни:</b> {html_text(follow_up)}"
            saved_profile = get_beauty_profile(requester_id, mode) or {}
            await render_panel(
                status_message,
                reply,
                mode_inline_keyboard(mode, has_saved_profile=bool(saved_profile.get("answers"))),
            )
            return

        answer = f"✨ <b>Красавица · {html_text(MODE_LABELS[mode])}</b>\n\n"
        answer += f"<b>Что учла:</b>\n{html_text(summary)}\n\n"
        answer += "<b>Проверенные варианты:</b>\n"
        for product in products[:4]:
            if not isinstance(product, dict):
                continue
            name = _as_bot_text(product.get("name"))
            category = _as_bot_text(product.get("category"))
            score = max(0, min(100, int(product.get("matchScore") or 0)))
            answer += f"• <b>{html_text(name)}</b> · {score}%\n"
            if category:
                answer += f"  {html_text(category)}\n"
        answer += "\nПроцент — соответствие твоему запросу, а не рейтинг магазина."

        await render_panel(status_message, answer, result_inline_keyboard(mode))
        rec_id = save_recommendation(user_id=requester_id, user_request=text_to_process, answer=answer)
        feedback_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="👍 Полезно", callback_data=f"feedback_good:{rec_id}"),
            InlineKeyboardButton(text="👎 Не подошло", callback_data=f"feedback_bad:{rec_id}"),
        ]])
        product_card_tasks = []
        for product in products[:4]:
            if not isinstance(product, dict):
                continue
            product_name = _as_bot_text(product.get("name"))
            if not product_name:
                continue
            product_category = _as_bot_text(product.get("category"))
            product_reason = _as_bot_text(product.get("reason"))
            product_usage = _as_bot_text(product.get("usage"))
            tradeoffs = product.get("tradeoffs") if isinstance(product.get("tradeoffs"), list) else []
            score = max(0, min(100, int(product.get("matchScore") or 0)))
            link_items = product.get("marketplaces") if isinstance(product.get("marketplaces"), list) else []
            links = {
                _as_bot_text(item.get("label")): _as_bot_text(item.get("href"))
                for item in link_items
                if isinstance(item, dict) and is_http_url(_as_bot_text(item.get("href")))
            }
            product_id = save_recommended_product(user_id=requester_id, product_name=product_name)
            link_buttons = [InlineKeyboardButton(text=label, url=url) for label, url in list(links.items())[:4]]
            buttons = [link_buttons[index:index + 2] for index in range(0, len(link_buttons), 2)]
            buttons.append([
                InlineKeyboardButton(text="👍 Подходит", callback_data=f"product_good:{product_id}"),
                InlineKeyboardButton(text="👎 Не подходит", callback_data=f"product_bad:{product_id}"),
            ])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            image_url = next(iter(links.values()), "")
            caption = build_product_caption(
                product_name=product_name,
                product_category=product_category,
                match_score=score,
                why=product_reason,
                usage=product_usage,
                tradeoffs=tradeoffs,
            )
            product_card_tasks.append(asyncio.create_task(prepare_product_card(
                product_name=product_name,
                image_url=image_url,
                caption=caption,
                keyboard=keyboard,
                market_links=links,
                mode=mode,
            )))

        for task in asyncio.as_completed(product_card_tasks):
            await send_prepared_product_card(message, await task)
        await message.answer("Оцени подбор — так «Красавица» станет точнее.", reply_markup=feedback_keyboard)

    except BeautyServiceBusyError:
        await render_panel(
            status_message,
            "⏳ <b>Сервис подбора занят</b>\n\nПараметры уже сохранены. Нажми «Повторить запрос» через минуту — заполнять анкету заново не потребуется.",
            retry_keyboard(mode),
        )
    except ValueError:
        saved_profile = get_beauty_profile(requester_id, mode) or {}
        await render_panel(
            status_message,
            "Не получилось завершить проверку источников. Параметры сохранены — можно повторить подбор или изменить ответы.",
            mode_inline_keyboard(mode, has_saved_profile=bool(saved_profile.get("answers"))),
        )
    except Exception as error:
        await render_panel(
            status_message,
            "Не получилось завершить проверку. Попробуй ещё раз или уточни запрос.",
            retry_keyboard(mode),
        )
        print(error)
    finally:
        animation_done.set()
        if not animation_task.done():
            animation_task.cancel()
        with suppress(asyncio.CancelledError):
            await animation_task


@dp.message(F.text)
async def handle_text(message: Message, user_text: str | None = None, loading_msg: Message | None = None):
    text_to_process = (user_text or message.text or "").strip()
    user_id = message.from_user.id
    if user_text is None and text_to_process.startswith("/"):
        await message.answer(main_text(), parse_mode="HTML", reply_markup=main_inline_keyboard())
        return
    if user_text is None and is_thanks_message(text_to_process):
        await message.answer(build_thanks_reply(), reply_markup=main_inline_keyboard())
        return
    if user_text is None and user_id not in ACTIVE_MODES and not is_cosmetic_request(text_to_process):
        await message.answer(build_offtopic_reply(), reply_markup=main_inline_keyboard())
        return

    saved_state = get_user_beauty_state(user_id) or {}
    mode = (
        detect_mode(text_to_process)
        or ACTIVE_MODES.get(user_id)
        or saved_state.get("active_mode")
        or "skin"
    )
    await perform_search(
        message=message,
        requester_id=user_id,
        requester_username=message.from_user.username,
        text_to_process=text_to_process,
        mode=mode,
        status_message=loading_msg,
    )


def _as_bot_text(value, limit: int = 700) -> str:
    return str(value or "").strip()[:limit]


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
    # Exact source image first. Broad image search is intentionally excluded from
    # the critical path: it was slow and could attach a visually similar product.
    image_file, resolved_image_url = await fetch_exact_product_image(image_url, product_name)
    if not image_file:
        image_file, resolved_image_url = await find_product_image_from_marketplaces(
            product_name,
            market_links,
        )
    return image_file, resolved_image_url


def load_mode_fallback_image(mode: str, product_name: str) -> BufferedInputFile | None:
    asset_path = MODE_ASSET_PATHS.get(mode)
    if not asset_path or not asset_path.is_file():
        return None
    try:
        return _prepare_telegram_photo(asset_path.read_bytes(), "image/webp", product_name)
    except OSError:
        return None


async def prepare_product_card(
    product_name: str,
    image_url: str,
    caption: str,
    keyboard: InlineKeyboardMarkup,
    market_links: dict | None = None,
    mode: str = "skin",
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

    if image_file is None:
        image_file = load_mode_fallback_image(mode, product_name)
        resolved_image_url = f"local:{mode}"

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
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
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
    mode: str = "skin",
) -> None:
    card = await prepare_product_card(
        product_name=product_name,
        image_url=image_url,
        caption=caption,
        keyboard=keyboard,
        market_links=market_links,
        mode=mode,
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


def build_product_caption(
    product_name: str,
    product_category: str,
    match_score: int,
    why: str,
    usage: str = "",
    tradeoffs: list | None = None,
) -> str:
    emoji = get_category_emoji(product_category)
    category_text = html_text(product_category or "Средство")
    product_text = html_text(product_name)
    title = f"{emoji} <b>{category_text}</b>\n<code>{product_text}</code>"
    caption = f"{title}\n\n🎯 <b>Соответствие запросу:</b> {max(0, min(100, match_score))}%"
    if why:
        caption += f"\n\n{html_text(why)}"
    if usage:
        caption += f"\n\n<b>Как использовать или тестировать:</b>\n{html_text(usage)}"
    clean_tradeoffs = [html_text(item) for item in (tradeoffs or []) if str(item or "").strip()]
    if clean_tradeoffs:
        caption += f"\n\n<b>Важно:</b> {(' · '.join(clean_tradeoffs))}"
    caption += "\n\nСсылки ниже ведут только на проверенные отдельные карточки."

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
    await bot.set_my_description(
        description=(
            "Красавица — персональный beauty-помощник. Подбираю уход за кожей и волосами, "
            "а также парфюм. Профиль можно сохранить, использовать повторно или пропустить."
        ),
        language_code="ru",
    )
    await bot.set_my_short_description(
        short_description="Кожа · волосы · парфюм — подбор с сохранённым профилем",
        language_code="ru",
    )
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть Красавицу"),
        BotCommand(command="pick", description="Начать новый подбор"),
        BotCommand(command="skin", description="Подбор ухода за кожей"),
        BotCommand(command="hair", description="Подбор ухода за волосами"),
        BotCommand(command="perfume", description="Подбор парфюма"),
        BotCommand(command="profile", description="Мои сохранённые параметры"),
        BotCommand(command="help", description="Как получить точный результат"),
        BotCommand(command="site", description="Открыть сайт"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query"]
    )


if __name__ == "__main__":
    asyncio.run(main())

