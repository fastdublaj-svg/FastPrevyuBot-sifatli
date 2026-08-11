import asyncio
import logging
import os
import sqlite3
from html import escape
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Use an environment variable named BOT_TOKEN. Do NOT store the token directly in the repo.
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {7543852010, 418350122}
PRIMARY_ADMIN_USERNAME = "@Fast_gamer_uz"

PREVIEW_COST = 1000
REF_REWARD = 5

GAME_URL = "https://t.me/FastPrevyuBotShashkaGame.Replit.app"
GROUP_URL = "https://t.me/Fast_prevyu_bot?startgroup=true"
BOT_USERNAME = "Fast_Prevyu_Bot"

PROMO_CODES = {
    "FAST",
    "FAST_GAMER_UZ",
    "FAST_GAMER",
    "PREVYU",
    "FAST_PREVYU_BOT",
    "FAST_PREVYU",
    "FASTZO'R",
    "FASTGAOBUNABOL",
}

DB_PATH = "fastbot.sqlite3"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# ============================================================
# FSM states
# ============================================================

class UserStates(StatesGroup):
    waiting_preview = State()
    waiting_promo = State()


# ============================================================
# Database
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER NOT NULL DEFAULT 0,
            stars INTEGER NOT NULL DEFAULT 0,
            referred_by INTEGER,
            referred_rewarded INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promo_used (
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            used_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, code)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS preview_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id INTEGER PRIMARY KEY,
            rating INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS custom_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            row INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL DEFAULT 0,
            function TEXT,
            color TEXT
        )
    """)

    # Doimiy asosiy adminlar
    for admin_id in ADMIN_IDS:
        username = PRIMARY_ADMIN_USERNAME if admin_id == 7543852010 else ""
        cur.execute(
            "INSERT OR IGNORE INTO admins(user_id, username) VALUES (?, ?)",
            (admin_id, username),
        )

    conn.commit()
    conn.close()


def ensure_user(tg_user):
    conn = db()
    cur = conn.cursor()

    row = cur.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (tg_user.id,),
    ).fetchone()

    if not row:
        cur.execute(
            """
            INSERT INTO users(user_id, username, first_name)
            VALUES (?, ?, ?)
            """,
            (
                tg_user.id,
                tg_user.username or "",
                tg_user.first_name or "",
            ),
        )
    else:
        cur.execute(
            """
            UPDATE users
            SET username=?, first_name=?
            WHERE user_id=?
            """,
            (
                tg_user.username or "",
                tg_user.first_name or "",
                tg_user.id,
            ),
        )

    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = db()
    row = conn.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,),
    ).fetchone()
    conn.close()
    return row


def get_all_user_ids():
    conn = db()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [row["user_id"] for row in rows]


def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True

    conn = db()
    row = conn.execute(
        "SELECT 1 FROM admins WHERE user_id=?",
        (user_id,),
    ).fetchone()
    conn.close()

    return bool(row)


def add_balance(user_id: int, amount: int):
    conn = db()
    conn.execute(
        "UPDATE users SET balance=MAX(0, balance+?) WHERE user_id=?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


def set_balance(user_id: int, amount: int):
    conn = db()
    conn.execute(
        "UPDATE users SET balance=? WHERE user_id=?",
        (max(0, amount), user_id),
    )
    conn.commit()
    conn.close()


def deduct_balance(user_id: int, amount: int) -> bool:
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET balance=balance-?
        WHERE user_id=? AND balance>=?
        """,
        (amount, user_id, amount),
    )

    ok = cur.rowcount == 1
    conn.commit()
    conn.close()

    return ok


def set_referrer_if_empty(user_id: int, referrer_id: int):
    conn = db()

    row = conn.execute(
        "SELECT referred_by FROM users WHERE user_id=?",
        (user_id,),
    ).fetchone()

    if row and row["referred_by"] is None and user_id != referrer_id:
        conn.execute(
            "UPDATE users SET referred_by=? WHERE user_id=?",
            (referrer_id, user_id),
        )
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def reward_referrer_if_needed(user_id: int):
    conn = db()

    row = conn.execute(
        """
        SELECT referred_by, referred_rewarded
        FROM users
        WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()

    if (
        not row
        or not row["referred_by"]
        or row["referred_rewarded"]
    ):
        conn.close()
        return None

    referrer_id = row["referred_by"]

    conn.execute(
        """
        UPDATE users
        SET balance=balance+?, referred_rewarded=1
        WHERE user_id=?
        """,
        (REF_REWARD, user_id),
    )

    conn.execute(
        "UPDATE users SET balance=balance+? WHERE user_id=?",
        (REF_REWARD, referrer_id),
    )

    conn.commit()
    conn.close()

    return referrer_id


# ============================================================
# Keyboards
# ============================================================

def main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()

    kb.add(
        KeyboardButton(text="⭐ Prevyu yasash ⭐")
    )

    kb.row(
        KeyboardButton(text="🎁 Promo kod 🎁"),
        KeyboardButton(text="💳 Balans to‘ldirish 💳"),
    )

    kb.row(
        KeyboardButton(text="🎮 O‘yinlar"),
        KeyboardButton(text="➕ Guruhga qo‘shish ➕"),
    )

    # Bu tugma faqat adminlarga ko'rinadi.
    if is_admin(user_id):
        kb.row(
            KeyboardButton(text="⛓️‍💥 Admin Sozlamalar ⚙️")
        )

    return kb.as_markup(resize_keyboard=True)


def games_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()

    kb.row(
        KeyboardButton(text="♟️ Shashka"),
        KeyboardButton(text="🎲 Minecraft"),
        KeyboardButton(text="🔘 Omad doirasi"),
    )

    kb.row(KeyboardButton(text="⬅️ Menyu"))

    return kb.as_markup(resize_keyboard=True)


def admin_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()

    kb.row(
        KeyboardButton(text="/users"),
        KeyboardButton(text="/Admin user"),
    )
    kb.row(
        KeyboardButton(text="/NewAdmins"),
        KeyboardButton(text="/DeleteAdmin"),
    )
    kb.row(
        KeyboardButton(text="/Rating"),
        KeyboardButton(text="/broadcast"),
    )
    kb.row(
        KeyboardButton(text="/Onemessage"),
        KeyboardButton(text="/Userprofile"),
    )
    kb.row(
        KeyboardButton(text="/UserUsername"),
        KeyboardButton(text="/Buttoneditor"),
    )
    kb.row(
        KeyboardButton(text="/ButtonsName"),
        KeyboardButton(text="/NewButton"),
    )
    kb.row(
        KeyboardButton(text="/ButtonColor"),
        KeyboardButton(text="/DaletButton"),
    )
    kb.row(
        KeyboardButton(text="/ButtonFunction"),
        KeyboardButton(text="/ButtonFunctionDalet"),
    )
    kb.row(
        KeyboardButton(text="/BalanceDeleteAll"),
        KeyboardButton(text="/BalanceDalete1"),
    )
    kb.row(
        KeyboardButton(text="/Balancing"),
        KeyboardButton(text="/AllHumansBalans1"),
    )
    kb.row(
        KeyboardButton(text="/NewWindowButton"),
        KeyboardButton(text="/IdendUser"),
    )
    kb.row(KeyboardButton(text="/RandomHuman"))
    kb.row(KeyboardButton(text="⬅️ Menyu"))

    return kb.as_markup(resize_keyboard=True)


# ============================================================
# Helpers
# ============================================================

def display_username(row) -> str:
    if row["username"]:
        return "@" + row["username"].lstrip("@")
    return row["first_name"] or str(row["user_id"])


def start_text(user_id: int) -> str:
    row = get_user(user_id)
    username = display_username(row)

    return (
        f"👋 💎 <b>Salom {escape(username)} 💎</b>\n\n"
        f"🔥 <b>@Fast_prevyu_bot ga xush kelibsiz</b> 🔥\n\n"
        f"⭐ <b>Iltimos menyudan foydalaning va "
        f"o‘z prevyuyingizni tayyorlang</b> ⭐"
    )


async def resolve_user(arg: str) -> Optional[int]:
    arg = arg.strip()

    if not arg:
        return None

    if arg.startswith("@"):
        username = arg[1:].lower()

        conn = db()
        row = conn.execute(
            "SELECT user_id FROM users WHERE lower(username)=?",
            (username,),
        ).fetchone()
        conn.close()

        return row["user_id"] if row else None

    try:
        return int(arg)
    except ValueError:
        return None


# ============================================================
# START
# ============================================================

@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    ensure_user(message.from_user)

    # /start REFERRER_ID
    if command.args:
        try:
            referrer_id = int(command.args.strip())

            if (
                referrer_id != message.from_user.id
                and get_user(referrer_id)
            ):
                set_referrer_if_empty(
                    message.from_user.id,
                    referrer_id,
                )

        except ValueError:
            pass

    # Referral mukofoti bir marta beriladi.
    rewarded = reward_referrer_if_needed(message.from_user.id)

    if rewarded:
        try:
            await bot.send_message(
                rewarded,
                "🎉 Sizning taklif havolangiz orqali yangi "
                "foydalanuvchi kirdi!\n"
                "💎 <b>+5 Balans</b> berildi.",
            )
        except Exception:
            pass

    await message.answer(
        start_text(message.from_user.id),
        reply_markup=main_keyboard(message.from_user.id),
    )

# (rest of file unchanged...)
