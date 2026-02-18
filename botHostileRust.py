import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path

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

DATA_DIR = Path("data")
DATA_PROMO = DATA_DIR / "promocodes.json"
DATA_USERS = DATA_DIR / "users.json"
LOG_FILE = DATA_DIR / "bot.log"

tz = pytz.timezone("Europe/Moscow")

# ================= LOGGING =================

DATA_DIR.mkdir(exist_ok=True)  # создаём папку data, если нет

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
    if not path.exists():
        save(path, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ================= FSM =================

class AdminFSM(StatesGroup):
    addpromo = State()
    delpromo = State()
    broadcast = State()
    broadcast_confirm = State()

# ================= BOT =================

bot = Bot(TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ================= KEYBOARDS =================

def main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Получить промокод", callback_data="promo")
    kb.adjust(1)
    return kb.as_markup()

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить промо", callback_data="a_add")
    kb.button(text="➖ Удалить промо", callback_data="a_del")
    kb.button(text="📋 Список промокодов", callback_data="a_list")
    kb.button(text="👥 Список пользователей", callback_data="a_users")
    kb.button(text="📢 Рассылка", callback_data="a_bc")
    kb.adjust(2)
    return kb.as_markup()

# ================= USER =================

@dp.message(Command("start"))
async def start(m: Message):
    users = load(DATA_USERS, {})

    user_id = str(m.from_user.id)
    if user_id not in users:
        users[user_id] = {
            "username": m.from_user.username or "",
            "first_name": m.from_user.first_name or ""
        }
        save(DATA_USERS, users)
        log.info(f"🎉 NEW USER SUBSCRIBED {user_id}")

    welcome_text = (
        f"🔥 Привет, {m.from_user.first_name or 'Игрок'}!\n\n"
        "Добро пожаловать в *Hostile Rust*!\n"
        "Выбери действие ниже ⬇️"
    )
    await m.answer(welcome_text, reply_markup=main_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "promo")
async def promo(cb: CallbackQuery):
    promos = load(DATA_PROMO, [])
    if not promos:
        return await cb.message.answer("❌ К сожалению, промокоды закончились 😢")

    code = random.choice(promos)
    msg = (
        f"🎁 Ваш уникальный промокод:\n\n"
        f"<code>{code}</code>\n\n"
        "💡 Чтобы активировать его, перейдите на сайт:\n"
        "👉 http://hostilerust.gamestores.app/"
    )
    await cb.message.answer(msg, parse_mode="HTML")
    log.info(f"PROMO -> {cb.from_user.id} = {code}")

# ================= ADMIN =================

@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    await m.answer("👑 Админ панель", reply_markup=admin_kb())

@dp.callback_query(F.data == "a_add")
async def a_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFSM.addpromo)
    await cb.message.answer("✏️ Введите новый промокод:")

@dp.message(AdminFSM.addpromo)
async def addpromo(m: Message, state: FSMContext):
    promos = load(DATA_PROMO, [])
    if m.text in promos:
        return await m.answer("❌ Такой промокод уже существует")

    promos.append(m.text.strip())
    save(DATA_PROMO, promos)

    await state.clear()
    await m.answer("✅ Промокод успешно добавлен 🎉")
    log.info(f"ADMIN ADD PROMO {m.text}")

@dp.callback_query(F.data == "a_del")
async def a_del(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFSM.delpromo)
    await cb.message.answer("❌ Какой промокод удалить?")

@dp.message(AdminFSM.delpromo)
async def delpromo(m: Message, state: FSMContext):
    promos = load(DATA_PROMO, [])
    if m.text not in promos:
        return await m.answer("❌ Промокод не найден")

    promos.remove(m.text)
    save(DATA_PROMO, promos)

    await state.clear()
    await m.answer("🗑️ Промокод удалён")
    log.info(f"ADMIN DEL PROMO {m.text}")

@dp.callback_query(F.data == "a_list")
async def listpromo(cb: CallbackQuery):
    promos = load(DATA_PROMO, [])
    text = "\n".join([f"🎫 {p}" for p in promos]) if promos else "Пусто"
    await cb.message.answer(text)

@dp.callback_query(F.data == "a_users")
async def listusers(cb: CallbackQuery):
    users = load(DATA_USERS, {})
    text = "\n".join([f"👤 {v['first_name']} (@{v['username']})" for k,v in users.items()]) or "Пусто"
    await cb.message.answer(text)

# ================= BROADCAST =================

@dp.callback_query(F.data == "a_bc")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminFSM.broadcast)
    await cb.message.answer("✉️ Введите текст рассылки:")

@dp.message(AdminFSM.broadcast)
async def bc_text(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return

    await state.update_data(bc_text=m.text)

    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Отправить всем", callback_data="bc_send")
    kb.button(text="❌ Отменить рассылку", callback_data="bc_cancel")
    kb.adjust(2)

    await state.set_state(AdminFSM.broadcast_confirm)
    await m.answer(f"📢 Текст рассылки:\n\n{m.text}", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "bc_send")
async def bc_send(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()
    text = data.get("bc_text")
    users = load(DATA_USERS, {})

    sent = 0
    for u in users:
        try:
            await bot.send_message(u, text)
            sent += 1
        except:
            pass

    await state.clear()
    await cb.message.edit_text(f"✅ Рассылка завершена!\nОтправлено: {sent} пользователям")
    log.info(f"ADMIN BROADCAST -> {sent} users")

@dp.callback_query(F.data == "bc_cancel")
async def bc_cancel(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await cb.message.edit_text("❌ Рассылка отменена")

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
