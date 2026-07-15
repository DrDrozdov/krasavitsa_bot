import asyncio
import html
import math
import re
from dataclasses import dataclass, field

from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)


MODE_LABELS = {
    "skin": "Кожа 💧",
    "hair": "Волосы 💇‍♀️",
    "perfume": "Парфюм 🌸",
}

MODE_ICONS = {
    "skin": "◌",
    "hair": "⌁",
    "perfume": "✦",
}


@dataclass(frozen=True)
class FlowOption:
    label: str
    value: str


@dataclass(frozen=True)
class FlowStep:
    key: str
    eyebrow: str
    title: str
    hint: str
    options: tuple[FlowOption, ...]


@dataclass
class FlowSession:
    mode: str
    step: int = 0
    answers: dict[str, FlowOption] = field(default_factory=dict)


FLOW_STEPS: dict[str, tuple[FlowStep, ...]] = {
    "skin": (
        FlowStep(
            "goal",
            "Шаг 1 из 4",
            "Что хочется изменить?",
            "Можно выбрать направление или пропустить вопрос.",
            (
                FlowOption("Базовый уход", "basic"),
                FlowOption("Сухость", "dry"),
                FlowOption("Жирный блеск", "oily"),
                FlowOption("Чувствительность", "sensitive"),
                FlowOption("Акне", "acne"),
                FlowOption("SPF", "spf"),
            ),
        ),
        FlowStep(
            "skin_type",
            "Шаг 2 из 4",
            "Как кожа ведёт себя обычно?",
            "Если не уверены — это нормально, выберите «Не знаю».",
            (
                FlowOption("Сухая", "dry"),
                FlowOption("Жирная", "oily"),
                FlowOption("Комбинированная", "combo"),
                FlowOption("Чувствительная", "sensitive"),
                FlowOption("Нормальная", "normal"),
                FlowOption("Не знаю", "unknown"),
            ),
        ),
        FlowStep(
            "sensitivity",
            "Шаг 3 из 4",
            "Есть важные ограничения?",
            "Так мы не предложим заведомо неподходящий актив или текстуру.",
            (
                FlowOption("Нет", "none"),
                FlowOption("Легко раздражается", "reactive"),
                FlowOption("Нарушен барьер", "barrier"),
                FlowOption("Не переношу отдушки", "fragrance_free"),
                FlowOption("Без кислот и ретиноидов", "no_actives"),
                FlowOption("Не знаю", "unknown"),
            ),
        ),
        FlowStep(
            "budget",
            "Шаг 4 из 4",
            "Комфортный бюджет на одно средство",
            "Бюджет помогает не показывать заведомо неподходящие варианты.",
            (
                FlowOption("до 1 500 ₽", "1500"),
                FlowOption("до 3 000 ₽", "3000"),
                FlowOption("до 6 000 ₽", "6000"),
                FlowOption("Без ограничений", "any"),
            ),
        ),
    ),
    "hair": (
        FlowStep(
            "focus",
            "Шаг 1 из 5",
            "На чём сосредоточиться?",
            "Кожу головы и длину оцениваем отдельно.",
            (
                FlowOption("Полный уход", "routine"),
                FlowOption("Кожа головы", "scalp"),
                FlowOption("Сухая длина", "dry_length"),
                FlowOption("Ломкость", "breakage"),
                FlowOption("Объём", "volume"),
                FlowOption("Термозащита", "heat"),
            ),
        ),
        FlowStep(
            "hair_type",
            "Шаг 2 из 5",
            "Какой у волос рисунок?",
            "Это помогает подобрать очищение, кондиционирование и стайлинг.",
            (
                FlowOption("Прямые", "straight"),
                FlowOption("Волнистые", "wavy"),
                FlowOption("Кудрявые", "curly"),
                FlowOption("Очень кудрявые", "coily"),
                FlowOption("Не важно", "any"),
                FlowOption("Не знаю", "unknown"),
            ),
        ),
        FlowStep(
            "scalp_type",
            "Шаг 3 из 5",
            "Как ведёт себя кожа головы?",
            "Кожу головы оцениваем отдельно от длины.",
            (
                FlowOption("Нормальная", "normal"),
                FlowOption("Быстро жирнится", "oily"),
                FlowOption("Сухая", "dry"),
                FlowOption("Чувствительная", "sensitive"),
                FlowOption("Есть шелушение", "flaking"),
                FlowOption("Не знаю", "unknown"),
            ),
        ),
        FlowStep(
            "hair_state",
            "Шаг 4 из 5",
            "Что происходило с длиной?",
            "Окрашивание и нагрев меняют требования к уходу.",
            (
                FlowOption("Натуральная", "natural"),
                FlowOption("Окрашенная", "colored"),
                FlowOption("Осветлённая", "bleached"),
                FlowOption("Повреждённая", "damaged"),
                FlowOption("Частая горячая укладка", "heat"),
                FlowOption("Не знаю", "unknown"),
            ),
        ),
        FlowStep(
            "budget",
            "Шаг 5 из 5",
            "Комфортный бюджет на одно средство",
            "Можно пропустить и посмотреть разные ценовые уровни.",
            (
                FlowOption("до 1 500 ₽", "1500"),
                FlowOption("до 3 000 ₽", "3000"),
                FlowOption("до 6 000 ₽", "6000"),
                FlowOption("Без ограничений", "any"),
            ),
        ),
    ),
    "perfume": (
        FlowStep(
            "audience",
            "Шаг 1 из 4",
            "Для кого аромат?",
            "Это мягкий ориентир, а не жёсткая граница.",
            (
                FlowOption("Женский", "female"),
                FlowOption("Мужской", "male"),
                FlowOption("Унисекс", "unisex"),
                FlowOption("Не важно", "any"),
            ),
        ),
        FlowStep(
            "character",
            "Шаг 2 из 4",
            "Какой характер хочется?",
            "Если пока непонятно — выберите «Хочу варианты».",
            (
                FlowOption("Чистый и свежий", "clean"),
                FlowOption("Цветочный", "floral"),
                FlowOption("Древесный", "woody"),
                FlowOption("Ванильный", "vanilla"),
                FlowOption("Тёплый и пряный", "spicy"),
                FlowOption("Хочу варианты", "explore"),
            ),
        ),
        FlowStep(
            "occasion",
            "Шаг 3 из 4",
            "Когда планируете носить?",
            "Для подарка можно ничего не знать — эксперт даст разные направления.",
            (
                FlowOption("Каждый день", "daily"),
                FlowOption("Офис", "office"),
                FlowOption("Вечер", "evening"),
                FlowOption("Свидание", "date"),
                FlowOption("В подарок", "gift"),
                FlowOption("Любой случай", "any"),
            ),
        ),
        FlowStep(
            "budget",
            "Шаг 4 из 4",
            "Бюджет на аромат",
            "Можно пропустить — тогда подбор покажет разные уровни.",
            (
                FlowOption("до 5 000 ₽", "5000"),
                FlowOption("до 10 000 ₽", "10000"),
                FlowOption("до 20 000 ₽", "20000"),
                FlowOption("Без ограничений", "any"),
            ),
        ),
    ),
}


SESSIONS: dict[int, FlowSession] = {}


def main_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💧 Кожа", callback_data="mode:skin"),
            InlineKeyboardButton(text="💇‍♀️ Волосы", callback_data="mode:hair"),
            InlineKeyboardButton(text="🌸 Парфюм", callback_data="mode:perfume"),
        ],
        [
            InlineKeyboardButton(text="✍️ Написать свой запрос", callback_data="free:text"),
            InlineKeyboardButton(text="🔁 Повторить подбор", callback_data="repeat:last"),
        ],
        [InlineKeyboardButton(text="✨ Сайт Красавицы", url="https://krasavitsa-ai.ru/")],
    ])


def mode_inline_keyboard(mode: str, has_saved_profile: bool = False) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="✍️ Рассказать своими словами", callback_data=f"direct:{mode}"),
        InlineKeyboardButton(text="✨ Подобрать по вопросам", callback_data=f"guide:{mode}"),
    ]]
    if has_saved_profile:
        rows.append([InlineKeyboardButton(text="💾 Мои сохранённые параметры", callback_data=f"saved:{mode}")])
    rows.append(
        [InlineKeyboardButton(text="← Главное меню", callback_data="menu:main")],
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def result_inline_keyboard(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♡ Сохранить подбор", callback_data="favorite:last")],
        [
            InlineKeyboardButton(text="💸 Найти дешевле", callback_data="refine:cheaper"),
            InlineKeyboardButton(text="✍️ Уточнить запрос", callback_data=f"direct:{mode}"),
        ],
        [
            InlineKeyboardButton(text="✨ Новый подбор", callback_data=f"mode:{mode}"),
            InlineKeyboardButton(text="💾 Мои параметры", callback_data=f"saved:{mode}"),
        ],
        [InlineKeyboardButton(text="← Главное меню", callback_data="menu:main")],
    ])


def search_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ Остановить подбор", callback_data="search:cancel")],
    ])


def main_text() -> str:
    return (
        "✦ <b>Красавица рядом</b> 💗\n\n"
        "Бережно подберу уход за кожей и волосами или парфюм под ваше настроение. "
        "Можно ответить на несколько лёгких вопросов или просто написать всё своими словами.\n\n"
        "<b>С чего начнём?</b>"
    )


def mode_text(mode: str) -> str:
    descriptions = {
        "skin": "Соберём понятный базовый уход или найдём одно нужное средство — без лишних баночек 🌿",
        "hair": "Отдельно учтём кожу головы и длину, окрашивание, завиток и любимую укладку ✨",
        "perfume": "Найдём аромат по настроению, случаю и бюджету. Пол можно совсем не указывать 🌸",
    }
    return (
        f"{MODE_ICONS[mode]} <b>{MODE_LABELS[mode]}</b>\n\n"
        f"{descriptions[mode]}\n\n"
        "Хотите рассказать своими словами или пройти мягкий мини‑подбор?"
    )


def start_flow(user_id: int, mode: str, answers: dict[str, str] | None = None) -> FlowSession:
    session = FlowSession(mode=mode, answers=deserialize_answers(mode, answers or {}))
    SESSIONS[user_id] = session
    return session


def deserialize_answers(mode: str, values: dict[str, str]) -> dict[str, FlowOption]:
    restored = {}
    for step in FLOW_STEPS[mode]:
        value = str(values.get(step.key, ""))
        option = next((item for item in step.options if item.value == value), None)
        if option:
            restored[step.key] = option
    return restored


def serialize_answers(session: FlowSession) -> dict[str, str]:
    return {key: option.value for key, option in session.answers.items()}


def saved_answers_context(mode: str, values: dict[str, str]) -> str:
    answers = deserialize_answers(mode, values)
    labels = []
    for step in FLOW_STEPS[mode]:
        option = answers.get(step.key)
        if option:
            labels.append(f"{step.title}: {option.label}")
    return "; ".join(labels)


def get_session(user_id: int, mode: str | None = None) -> FlowSession | None:
    session = SESSIONS.get(user_id)
    if session and (mode is None or session.mode == mode):
        return session
    return None


def flow_text(session: FlowSession) -> str:
    step = FLOW_STEPS[session.mode][session.step]
    chosen = [option.label for option in session.answers.values()]
    context = f"\n\n💗 Уже учла: {' · '.join(chosen)}" if chosen else ""
    return (
        f"{MODE_ICONS[session.mode]} <b>{MODE_LABELS[session.mode]}</b>\n"
        f"<code>{step.eyebrow}</code>\n\n"
        f"<b>{step.title}</b>\n"
        f"{step.hint}{context}"
    )


def flow_keyboard(session: FlowSession) -> InlineKeyboardMarkup:
    step = FLOW_STEPS[session.mode][session.step]
    rows = []
    options = list(step.options)
    for index in range(0, len(options), 2):
        rows.append([
            InlineKeyboardButton(
                text=f"✓ {option.label}" if session.answers.get(step.key) == option else option.label,
                callback_data=f"flow:{session.mode}:{session.step}:{option.value}",
            )
            for option in options[index:index + 2]
        ])
    rows.append([
        InlineKeyboardButton(text="Пропустить", callback_data=f"skip:{session.mode}:{session.step}"),
        InlineKeyboardButton(text="Уже можно подбирать ✨", callback_data=f"finish:{session.mode}"),
    ])
    rows.append([
        InlineKeyboardButton(
            text="Назад",
            callback_data=f"back:{session.mode}:{session.step}" if session.step else f"mode:{session.mode}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choose_option(user_id: int, mode: str, step_index: int, value: str) -> tuple[FlowSession, bool]:
    session = get_session(user_id, mode) or start_flow(user_id, mode)
    session.step = max(0, min(step_index, len(FLOW_STEPS[mode]) - 1))
    step = FLOW_STEPS[mode][session.step]
    option = next((item for item in step.options if item.value == value), None)
    if option is None:
        return session, False
    session.answers[step.key] = option
    session.step += 1
    complete = session.step >= len(FLOW_STEPS[mode])
    if complete:
        session.step = len(FLOW_STEPS[mode]) - 1
    return session, complete


def skip_step(user_id: int, mode: str, step_index: int) -> tuple[FlowSession, bool]:
    session = get_session(user_id, mode) or start_flow(user_id, mode)
    current_index = max(0, min(step_index, len(FLOW_STEPS[mode]) - 1))
    session.answers.pop(FLOW_STEPS[mode][current_index].key, None)
    session.step = max(0, min(step_index + 1, len(FLOW_STEPS[mode]) - 1))
    complete = step_index + 1 >= len(FLOW_STEPS[mode])
    return session, complete


def previous_step(user_id: int, mode: str, step_index: int) -> FlowSession:
    session = get_session(user_id, mode) or start_flow(user_id, mode)
    session.step = max(0, step_index - 1)
    return session


def saved_profile_text(session: FlowSession) -> str:
    selected = []
    for step in FLOW_STEPS[session.mode]:
        option = session.answers.get(step.key)
        if option:
            selected.append(f"• <b>{step.title}</b> — {option.label}")
    details = "\n".join(selected) if selected else "Параметры пока не сохранены."
    return f"{MODE_ICONS[session.mode]} <b>{MODE_LABELS[session.mode]} · мои параметры</b>\n\n{details}"


def saved_profile_keyboard(mode: str, has_answers: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_answers:
        rows.append([InlineKeyboardButton(text="Подобрать по этим параметрам", callback_data=f"use_saved:{mode}")])
    rows.append([InlineKeyboardButton(text="Изменить ответы", callback_data=f"edit_saved:{mode}")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"mode:{mode}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_query(session: FlowSession | None, mode: str, exploratory: bool = False) -> str:
    labels = [] if session is None else [
        f"{FLOW_STEPS[mode][index].title}: {session.answers[step.key].label}"
        for index, step in enumerate(FLOW_STEPS[mode])
        if step.key in session.answers
    ]
    base = {
        "skin": "Подбери уход за кожей и конкретные косметические средства.",
        "hair": "Подбери уход за волосами и кожей головы и конкретные косметические средства.",
        "perfume": "Подбери конкретные ароматы.",
    }[mode]
    if labels:
        base += " Параметры: " + "; ".join(labels) + "."
    if exploratory or not labels:
        base += (
            " Это осознанный ознакомительный подбор: пользователь пока не знает точных предпочтений. "
            "Не блокируй результат лишними уточнениями; покажи несколько разных безопасных направлений "
            "и честно объясни различия и ограничения."
        )
    return base


async def safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    max_retry_wait: float = 3.0,
) -> bool:
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
        return True
    except TelegramRetryAfter as error:
        retry_after = float(error.retry_after)
        if retry_after > max_retry_wait:
            return False
        await asyncio.sleep(retry_after + 0.1)
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
            return True
        except (TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter):
            return False
    except (TelegramBadRequest, TelegramNetworkError):
        return False


def visible_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


async def typewriter_edit(
    message: Message,
    final_text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Imitate streaming without exceeding Telegram edit-rate limits."""
    plain = visible_text(final_text)
    if len(plain) < 24:
        await safe_edit(message, final_text, reply_markup)
        return
    steps = max(6, min(14, math.ceil(len(plain) / 34)))
    chunk = max(1, math.ceil(len(plain) / steps))
    for end in range(chunk, len(plain) + chunk, chunk):
        prefix = plain[: min(end, len(plain))]
        cursor = "" if len(prefix) >= len(plain) else " ▍"
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        await safe_edit(message, f"{html.escape(prefix)}{cursor}")
        if len(prefix) < len(plain):
            await asyncio.sleep(0.11)
    await safe_edit(message, final_text, reply_markup)


async def animate_intro(
    message: Message,
    welcome_photo=None,
    reply_keyboard=None,
    panel_text: str | None = None,
    panel_keyboard: InlineKeyboardMarkup | None = None,
) -> Message:
    welcome_caption = panel_text or (
        "✦ <b>Красавица — ваша ИИ‑помощница</b> 💗\n\n"
        "Бережно подбираю уход за кожей и волосами, а ещё ароматы — с учётом бюджета, привычек и важных ограничений."
    )
    try:
        cleanup = await message.answer("Обновляю меню…", reply_markup=ReplyKeyboardRemove())
        try:
            await cleanup.delete()
        except (AttributeError, TelegramBadRequest, TelegramNetworkError):
            pass
    except (TelegramBadRequest, TelegramNetworkError):
        pass
    welcome_card = None
    if welcome_photo is not None:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
        try:
            welcome_card = await message.answer_photo(
                photo=welcome_photo,
                caption=welcome_caption,
                parse_mode="HTML",
                reply_markup=panel_keyboard or main_inline_keyboard(),
            )
        except TelegramRetryAfter as error:
            if float(error.retry_after) <= 3.0:
                await asyncio.sleep(float(error.retry_after) + 0.1)
                try:
                    welcome_card = await message.answer_photo(
                        photo=welcome_photo,
                        caption=welcome_caption,
                        parse_mode="HTML",
                        reply_markup=panel_keyboard or main_inline_keyboard(),
                    )
                except (TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter):
                    pass
        except (TelegramBadRequest, TelegramNetworkError):
            pass
    if welcome_card is None:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        welcome_card = await message.answer(
            welcome_caption,
            parse_mode="HTML",
            reply_markup=panel_keyboard or main_inline_keyboard(),
        )
    return welcome_card


SEARCH_PHASES = {
    "skin": ("Бережно разбираю потребности кожи", "Учитываю бюджет и ограничения", "Сверяю средства и цены", "Собираю красивые карточки"),
    "hair": ("Разделяю потребности корней и длины", "Учитываю бюджет и привычки", "Сверяю средства и цены", "Собираю красивые карточки"),
    "perfume": ("Собираю настроение аромата", "Сравниваю ноты и характер", "Сверяю ароматы и цены", "Собираю красивые карточки"),
}

SEARCH_HINTS = (
    "Сначала хочу действительно понять вас 💗",
    "Убираю всё, что точно не подойдёт.",
    "Оставляю только прямые карточки товаров.",
    "Картинки и цены уже почти готовы ✨",
)


async def animate_search(
    status_message: Message,
    mode: str,
    done: asyncio.Event,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    phases = SEARCH_PHASES[mode]
    tick = 0
    while not done.is_set():
        phase_index = min(tick, len(phases) - 1)
        text = (
            "✦ <b>Красавица подбирает</b> ···\n\n"
            f"{phases[phase_index]}\n"
            f"<i>{SEARCH_HINTS[phase_index]}</i>\n\n"
            f"<code>{'●' * (phase_index + 1)}{'○' * (len(phases) - phase_index - 1)}</code>"
        )
        await status_message.bot.send_chat_action(chat_id=status_message.chat.id, action=ChatAction.TYPING)
        await safe_edit(status_message, text, keyboard)
        tick += 1
        try:
            await asyncio.wait_for(done.wait(), timeout=1.8)
        except asyncio.TimeoutError:
            continue


def all_callback_data() -> list[str]:
    values = ["menu:main", "free:text", "repeat:last", "retry:last", "refine:cheaper", "search:cancel", "favorite:last"]
    for mode, steps in FLOW_STEPS.items():
        values.extend((
            f"mode:{mode}", f"direct:{mode}", f"guide:{mode}", f"finish:{mode}",
            f"saved:{mode}", f"use_saved:{mode}", f"edit_saved:{mode}",
        ))
        for index, step in enumerate(steps):
            values.extend(f"flow:{mode}:{index}:{option.value}" for option in step.options)
            values.extend((f"skip:{mode}:{index}", f"back:{mode}:{index}"))
    return values
