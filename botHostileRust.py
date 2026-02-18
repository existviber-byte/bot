import asyncio
import json
import random
import logging
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

# ================= CONFIG =================

TOKEN = "8042067501:AAGfCGdiFbggUTMZZ7i49XKAA_EUmFNHVgg"
ADMIN_ID = 411379361
CHAT_ID = -1001234567890

DATA_PROMO = "data/promocodes.json"
DATA_USERS = "data/users.json"
LOG_FILE = "data/bot.log"

tz = pytz.timezone("Europe/Moscow")

# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

log = logging.getLogger("bot")

# ================= UTILS =================

def load(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def valid_steam(steamid: str):
    return re.fullmatch(r"7656119\d{10}", steamid)

# ================= FSM =================

class AdminFSM(StatesGroup):
    addpromo = State()
    delpromo = State()
    delsteam = State()
    broadcast = State()

# ================= BOT =================

bot = Bot(TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ================= KEYBOARDS =================

def main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Промокод", callback_data="promo")
    kb.button(text="🔗 Привязать Steam", callback_data="steam")
    kb.adjust(1)
    return kb.as_markup()

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить промо", callback_data="a_add")
    kb.button(text="➖ Удалить промо", callback_data="a_del")
    kb.button(text="📋 Список", callback_data="a_list")
    kb.button(text="👥 Пользователи", callback_data="a_users")
    kb.button(text="❌ Удалить Steam", callback_data="a_delsteam")
    kb.button(text="📢 Рассылка", callback_data="a_bc")
    kb.adjust(2)
    return kb.as_markup()

# ================= USER =================

@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("🔥 Hostile Rust\n\nВыбери действие:", reply_markup=main_kb())

@dp.callback_query(F.data == "promo")
async def promo(cb: CallbackQuery):
    promos = load(DATA_PROMO, [])
    if not promos:
        return await cb.message.answer("Промокоды закончились")

    code = random.choice(promos)
    await cb.message.answer(f"🎁 Твой промокод:\n<code>{code}</code>", parse_mode="HTML")
    log.info(f"PROMO -> {cb.from_user.id} = {code}")

@dp.callback_query(F.data == "steam")
async def steam(cb: CallbackQuery):
    await cb.message.answer("Отправь SteamID:")
    await dp.fsm.set_state(cb.from_user.id, AdminFSM.delsteam)

@dp.message(AdminFSM.delsteam)
async def steam_save(m: Message, state: FSMContext):
    steam = m.text.strip()

    if not valid_steam(steam):
        return await m.answer("❌ Неверный SteamID")

    users = load(DATA_USERS, {})

    if str(m.from_user.id) in users:
        return await m.answer("Steam уже привязан")

    users[str(m.from_user.id)] = steam
    save(DATA_USERS, users)

    await state.clear()
    await m.answer("✅ SteamID привязан")
    log.info(f"STEAM LINK {m.from_user.id} -> {steam}")

# ================= ADMIN =================

@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    await m.answer("👑 Админ панель", reply_markup=admin_kb())

@dp.callback_query(F.data == "a_add")
async def a_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFSM.addpromo)
    await cb.message.answer("Введи промокод:")

@dp.message(AdminFSM.addpromo)
async def addpromo(m: Message, state: FSMContext):
    promos = load(DATA_PROMO, [])

    if m.text in promos:
        return await m.answer("Уже существует")

    promos.append(m.text.strip())
    save(DATA_PROMO, promos)

    await state.clear()
    await m.answer("✅ Добавлено")
    log.info(f"ADMIN ADD PROMO {m.text}")

@dp.callback_query(F.data == "a_del")
async def a_del(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFSM.delpromo)
    await cb.message.answer("Какой промокод удалить?")

@dp.message(AdminFSM.delpromo)
async def delpromo(m: Message, state: FSMContext):
    promos = load(DATA_PROMO, [])

    if m.text not in promos:
        return await m.answer("Не найден")

    promos.remove(m.text)
    save(DATA_PROMO, promos)

    await state.clear()
    await m.answer("Удалено")
    log.info(f"ADMIN DEL PROMO {m.text}")

@dp.callback_query(F.data == "a_list")
async def listpromo(cb: CallbackQuery):
    promos = load(DATA_PROMO, [])
    await cb.message.answer("\n".join(promos) or "Пусто")

@dp.callback_query(F.data == "a_users")
async def listusers(cb: CallbackQuery):
    users = load(DATA_USERS, {})
    text = "\n".join([f"{k} → {v}" for k,v in users.items()])
    await cb.message.answer(text or "Пусто")

@dp.callback_query(F.data == "a_bc")
async def bc(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFSM.broadcast)
    await cb.message.answer("Текст рассылки:")

@dp.message(AdminFSM.broadcast)
async def broadcast(m: Message, state: FSMContext):
    users = load(DATA_USERS, {})
    for u in users:
        try:
            await bot.send_message(u, m.text)
        except:
            pass

    await state.clear()
    await m.answer("📢 Рассылка завершена")
    log.info("ADMIN BROADCAST")

# ================= WIPE =================

async def wipe_notify():
    await bot.send_message(CHAT_ID, "💣 ВАЙП HOSTILE RUST!")

def schedule():
    now = datetime.now(tz)
    for i in range(60):
        d = now + timedelta(days=i)
        if d.weekday() == 3:
            hour = 22 if d.day <= 7 else 12
            scheduler.add_job(wipe_notify, "date",
                run_date=tz.localize(datetime(d.year,d.month,d.day,hour)))

# ================= START =================

async def main():
    schedule()
    scheduler.start()
    log.info("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

