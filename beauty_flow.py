import asyncio
from dataclasses import dataclass, field

from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)


MODE_LABELS = {
    "skin": "Кожа",
    "hair": "Волосы",
    "perfume": "Парфюм",
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
            "Шаг 1 из 3",
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
            "Шаг 2 из 3",
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
            "budget",
            "Шаг 3 из 3",
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
            "Шаг 1 из 3",
            "На чём сосредоточиться?",
            "Кожу головы и длину оцениваем отдельно.",
            (
                FlowOption("Кожа головы", "scalp"),
                FlowOption("Сухая длина", "dry_length"),
                FlowOption("Ломкость", "breakage"),
                FlowOption("Кудри", "curls"),
                FlowOption("Окрашивание", "colored"),
                FlowOption("Термозащита", "heat"),
            ),
        ),
        FlowStep(
            "profile",
            "Шаг 2 из 3",
            "Какой сценарий ближе?",
            "Можно выбрать общий вариант — эксперт сам обозначит ограничения.",
            (
                FlowOption("Жирные корни", "oily_roots"),
                FlowOption("Чувствительная кожа", "sensitive_scalp"),
                FlowOption("Тонкие волосы", "fine"),
                FlowOption("Пористые волосы", "porous"),
                FlowOption("После осветления", "bleached"),
                FlowOption("Не знаю", "unknown"),
            ),
        ),
        FlowStep(
            "budget",
            "Шаг 3 из 3",
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
            InlineKeyboardButton(text="Кожа", callback_data="mode:skin"),
            InlineKeyboardButton(text="Волосы", callback_data="mode:hair"),
        ],
        [InlineKeyboardButton(text="Парфюм", callback_data="mode:perfume")],
        [InlineKeyboardButton(text="Просто написать запрос", callback_data="free:text")],
        [InlineKeyboardButton(text="Открыть сайт", url="https://krasavitsa-ai.ru/")],
    ])


def mode_inline_keyboard(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подобрать сразу", callback_data=f"direct:{mode}")],
        [InlineKeyboardButton(text="Настроить подбор", callback_data=f"guide:{mode}")],
        [InlineKeyboardButton(text="Главное меню", callback_data="menu:main")],
    ])


def result_inline_keyboard(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ещё подбор", callback_data=f"mode:{mode}")],
        [InlineKeyboardButton(text="Сменить направление", callback_data="menu:main")],
    ])


def main_text() -> str:
    return (
        "✦ <b>Красавица</b>\n\n"
        "Персональный подбор для кожи, волос и парфюмерии.\n"
        "Можно пройти короткий сценарий или сразу написать запрос своими словами.\n\n"
        "<b>Что подбираем?</b>"
    )


def mode_text(mode: str) -> str:
    descriptions = {
        "skin": "Соберём базовый уход, отдельное средство или понятный сценарий без лишних банок.",
        "hair": "Разделим потребности кожи головы и длины, учтём окрашивание, завиток и укладку.",
        "perfume": "Подберём аромат по характеру, случаю и бюджету — пол можно не указывать.",
    }
    return (
        f"{MODE_ICONS[mode]} <b>{MODE_LABELS[mode]}</b>\n\n"
        f"{descriptions[mode]}\n\n"
        "Начать сразу или ответить на несколько коротких вопросов?"
    )


def start_flow(user_id: int, mode: str) -> FlowSession:
    session = FlowSession(mode=mode)
    SESSIONS[user_id] = session
    return session


def get_session(user_id: int, mode: str | None = None) -> FlowSession | None:
    session = SESSIONS.get(user_id)
    if session and (mode is None or session.mode == mode):
        return session
    return None


def flow_text(session: FlowSession) -> str:
    step = FLOW_STEPS[session.mode][session.step]
    chosen = [option.label for option in session.answers.values()]
    context = f"\n\nУже выбрано: {' · '.join(chosen)}" if chosen else ""
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
                text=option.label,
                callback_data=f"flow:{session.mode}:{session.step}:{option.value}",
            )
            for option in options[index:index + 2]
        ])
    rows.append([
        InlineKeyboardButton(text="Пропустить", callback_data=f"skip:{session.mode}:{session.step}"),
        InlineKeyboardButton(text="Подобрать сейчас", callback_data=f"finish:{session.mode}"),
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
    if option:
        session.answers[step.key] = option
    session.step += 1
    complete = session.step >= len(FLOW_STEPS[mode])
    if complete:
        session.step = len(FLOW_STEPS[mode]) - 1
    return session, complete


def skip_step(user_id: int, mode: str, step_index: int) -> tuple[FlowSession, bool]:
    session = get_session(user_id, mode) or start_flow(user_id, mode)
    session.step = max(0, min(step_index + 1, len(FLOW_STEPS[mode]) - 1))
    complete = step_index + 1 >= len(FLOW_STEPS[mode])
    return session, complete


def previous_step(user_id: int, mode: str, step_index: int) -> FlowSession:
    session = get_session(user_id, mode) or start_flow(user_id, mode)
    session.step = max(0, step_index - 1)
    current_key = FLOW_STEPS[mode][session.step].key
    session.answers.pop(current_key, None)
    return session


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


async def safe_edit(message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramRetryAfter as error:
        await asyncio.sleep(min(float(error.retry_after), 1.5))
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
        except TelegramBadRequest:
            pass
    except TelegramBadRequest:
        pass


async def animate_intro(message: Message) -> Message:
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    card = await message.answer("Краса…", reply_markup=ReplyKeyboardRemove())
    await asyncio.sleep(0.24)
    await safe_edit(card, "✦ <b>Красавица</b>\nПодбор становится личным…")
    await asyncio.sleep(0.34)
    await safe_edit(card, main_text(), main_inline_keyboard())
    return card


SEARCH_PHASES = {
    "skin": ("Читаю состояние кожи", "Сверяю ограничения", "Проверяю средства", "Собираю карточки"),
    "hair": ("Разделяю кожу головы и длину", "Сверяю ограничения", "Проверяю средства", "Собираю карточки"),
    "perfume": ("Собираю ароматный профиль", "Сравниваю направления", "Проверяю ароматы", "Собираю карточки"),
}


async def animate_search(status_message: Message, mode: str, done: asyncio.Event) -> None:
    phases = SEARCH_PHASES[mode]
    tick = 0
    while not done.is_set():
        phase_index = min(tick, len(phases) - 1)
        dots = "·" * ((tick % 3) + 1)
        filled = "●" * (phase_index + 1)
        empty = "○" * (len(phases) - phase_index - 1)
        text = (
            f"{MODE_ICONS[mode]} <b>{MODE_LABELS[mode]}</b>\n\n"
            f"{phases[phase_index]}{dots}\n"
            f"<code>{filled}{empty}</code>"
        )
        await status_message.bot.send_chat_action(chat_id=status_message.chat.id, action=ChatAction.TYPING)
        await safe_edit(status_message, text)
        tick += 1
        try:
            await asyncio.wait_for(done.wait(), timeout=1.8)
        except asyncio.TimeoutError:
            continue


def all_callback_data() -> list[str]:
    values = ["menu:main", "free:text"]
    for mode, steps in FLOW_STEPS.items():
        values.extend((f"mode:{mode}", f"direct:{mode}", f"guide:{mode}", f"finish:{mode}"))
        for index, step in enumerate(steps):
            values.extend(f"flow:{mode}:{index}:{option.value}" for option in step.options)
            values.extend((f"skip:{mode}:{index}", f"back:{mode}:{index}"))
    return values
