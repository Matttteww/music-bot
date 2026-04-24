"""Клавиатуры бота (ReplyKeyboard — виджеты под клавиатурой)."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


# Тексты кнопок для фильтрации
BTN_VOTE = "🎵 Голосовать"
BTN_UPLOAD = "📤 Загрузить трек"
BTN_PROFILE = "👤 Профиль"
BTN_RATINGS = "🏆 Рейтинги"
BTN_KING = "👑 Царь SC"
BTN_TOP_TRACKS = "🎵 ТОП треков"
BTN_TOP_ARTISTS = "👤 ТОП исполнителей"
BTN_TRACKS_DAY = "🔥 Треки дня"
BTN_TRACKS_RISING = "📈 Растущие"
BTN_TRACKS_WORST = "💀 Худшие"
BTN_FAVORITES = "❤️ Избранные треки"
BTN_FAVORITE_ADD = "❤️ В избранное"
BTN_FAVORITE_REMOVE = "💔 Убрать из избранного"
BTN_BACK = "◀️ Назад"
BTN_MAIN_MENU = "◀️ Главное меню"
BTN_CHANGE_NICK = "✏️ Поменять ник"
BTN_REPLACE_TRACK = "🔄 Заменить трек"
BTN_DELETE_TRACK = "🗑 Удалить трек"
BTN_CANCEL = "❌ Отмена"
BTN_STOP_VOTE = "◀️ Стоп"
BTN_REPORT = "🚩 Пожаловаться"
BTN_REPORT_1 = "1) Неподобающий контент"
BTN_REPORT_2 = "2) Оскорбительный контент"
BTN_REPORT_3 = "3) Реклама запрещёнки"
BTN_REPORT_4 = "4) Другая причина"
BTN_REPORT_CANCEL = "◀️ Отмена"

# Стрим-очередь
BTN_STREAM_ADD = "🎙 Закинуть трек на стрим"
BTN_STREAM_EVALS = "📺 Оценки с стримов"
BTN_REFERRAL = "🎁 Рефералы"
BTN_ROLE_LISTENER = "🎧 Я слушатель"
BTN_ROLE_ARTIST = "🎤 Я артист"
BTN_ROLE_STREAMER = "📡 Я стример"
BTN_LISTENER_START = "🔥 Начать оценку"
BTN_LISTENER_NEXT = "▶️ Следующий трек"
BTN_LISTENER_TOURNAMENT = "🏆 Турнир"
BTN_LISTENER_FAV_AFTER_RATE = "⭐ В избранное"
BTN_ARTIST_PROMOTE = "🚀 Продвинуть трек"
BTN_ARTIST_MY_TRACKS = "📊 Мои треки"
BTN_STREAM_FREE = "🟢 Бесплатно (ограничено)"
BTN_STREAM_PREMIUM = "💎 Premium"
BTN_STREAM_PRO = "🔥 Pro"
BTN_STREAM_START_SESSION = "▶️ Начать стрим-сессию"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню: сетка 2×3, кнопки одной ширины."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=BTN_VOTE),
        KeyboardButton(text=BTN_UPLOAD),
    )
    builder.row(
        KeyboardButton(text=BTN_PROFILE),
        KeyboardButton(text=BTN_RATINGS),
    )
    builder.row(
        KeyboardButton(text=BTN_KING),
        KeyboardButton(text=BTN_REFERRAL),
    )
    return builder.as_markup(resize_keyboard=True)


def role_menu_keyboard() -> ReplyKeyboardMarkup:
    """Выбор роли на старте."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_ROLE_LISTENER))
    builder.row(KeyboardButton(text=BTN_ROLE_ARTIST))
    builder.row(KeyboardButton(text=BTN_ROLE_STREAMER))
    builder.row(KeyboardButton(text=BTN_MAIN_MENU))
    return builder.as_markup(resize_keyboard=True)


def listener_intro_keyboard() -> ReplyKeyboardMarkup:
    """Первый экран слушателя."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_LISTENER_START))
    builder.row(KeyboardButton(text=BTN_MAIN_MENU))
    return builder.as_markup(resize_keyboard=True)


def listener_post_rating_keyboard() -> ReplyKeyboardMarkup:
    """Кнопки после принятой оценки."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=BTN_LISTENER_NEXT),
        KeyboardButton(text=BTN_LISTENER_FAV_AFTER_RATE),
    )
    builder.row(KeyboardButton(text=BTN_LISTENER_TOURNAMENT))
    builder.row(KeyboardButton(text=BTN_MAIN_MENU))
    return builder.as_markup(resize_keyboard=True)


def artist_intro_keyboard() -> ReplyKeyboardMarkup:
    """Первый экран артиста."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_UPLOAD))
    builder.row(
        KeyboardButton(text=BTN_ARTIST_MY_TRACKS),
        KeyboardButton(text=BTN_ARTIST_PROMOTE),
    )
    builder.row(KeyboardButton(text=BTN_MAIN_MENU))
    return builder.as_markup(resize_keyboard=True)


def streamer_intro_keyboard() -> ReplyKeyboardMarkup:
    """Первый экран стримера с тарифами."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_STREAM_FREE))
    builder.row(KeyboardButton(text=BTN_STREAM_PREMIUM))
    builder.row(KeyboardButton(text=BTN_STREAM_PRO))
    builder.row(KeyboardButton(text=BTN_STREAM_START_SESSION))
    builder.row(KeyboardButton(text=BTN_MAIN_MENU))
    return builder.as_markup(resize_keyboard=True)


def ratings_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню рейтингов."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=BTN_TOP_TRACKS),
        KeyboardButton(text=BTN_TOP_ARTISTS),
    )
    builder.row(
        KeyboardButton(text=BTN_TRACKS_DAY),
        KeyboardButton(text=BTN_TRACKS_RISING),
    )
    builder.row(KeyboardButton(text=BTN_TRACKS_WORST))
    builder.row(KeyboardButton(text=BTN_FAVORITES))
    builder.row(KeyboardButton(text=BTN_BACK))
    return builder.as_markup(resize_keyboard=True)


def rating_keyboard(in_favorites: bool = False) -> ReplyKeyboardMarkup:
    """Кнопки оценки 1–10, лайк, пожаловаться и выход."""
    builder = ReplyKeyboardBuilder()
    for i in range(1, 11):
        builder.add(KeyboardButton(text=str(i)))
    builder.adjust(5, 5)
    builder.row(
        KeyboardButton(text=BTN_FAVORITE_REMOVE if in_favorites else BTN_FAVORITE_ADD),
    )
    builder.row(KeyboardButton(text=BTN_REPORT))
    builder.row(KeyboardButton(text=BTN_STOP_VOTE))
    return builder.as_markup(resize_keyboard=True)


def back_to_main_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка назад в главное меню."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_MAIN_MENU))
    return builder.as_markup(resize_keyboard=True)


def back_to_ratings_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка назад в меню рейтингов."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_BACK))
    return builder.as_markup(resize_keyboard=True)


def profile_keyboard(changes_left: int, has_tracks: bool = True) -> ReplyKeyboardMarkup:
    """Клавиатура профиля."""
    builder = ReplyKeyboardBuilder()
    buttons: list[KeyboardButton] = []
    if changes_left > 0:
        buttons.append(KeyboardButton(text=BTN_CHANGE_NICK))
    if has_tracks:
        buttons.append(KeyboardButton(text=BTN_REPLACE_TRACK))
        buttons.append(KeyboardButton(text=BTN_DELETE_TRACK))
    buttons.append(KeyboardButton(text=BTN_STREAM_ADD))
    buttons.append(KeyboardButton(text=BTN_STREAM_EVALS))
    buttons.append(KeyboardButton(text=BTN_MAIN_MENU))

    for b in buttons:
        builder.add(b)
    # 2 колонки как в главном меню -> одинаковый размер кнопок.
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def report_reason_keyboard() -> ReplyKeyboardMarkup:
    """Кнопки причины жалобы: 4 причины + отмена."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_REPORT_1))
    builder.row(KeyboardButton(text=BTN_REPORT_2))
    builder.row(KeyboardButton(text=BTN_REPORT_3))
    builder.row(KeyboardButton(text=BTN_REPORT_4))
    builder.row(KeyboardButton(text=BTN_REPORT_CANCEL))
    return builder.as_markup(resize_keyboard=True)


def report_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Только отмена (для «другая причина»)."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_REPORT_CANCEL))
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с отменой (для загрузки)."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=BTN_CANCEL))
    return builder.as_markup(resize_keyboard=True)
