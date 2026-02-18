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
ADMIN_IDS = [411379361]  # Список админов
CHAT_ID = -1001234567890

DATA_DIR = Path("data")
DATA_PROMO = DATA_DIR / "promocodes.json"
DATA_USERS = DATA_DIR / "users.json"
LOG_FILE = DATA_DIR / "bot.log"

PROMO_EXPIRATION_DAYS = 30  # Срок действия промокодов

tz = pytz.timezone("Europe/Moscow")

# ================= LOGGING =================

DATA_DIR.mkdir(exist_ok=True)

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

def remove_expired_promos():
    """Автоматическое удаление промокодов старше PROMO_EXPIRATION_DAYS"""
    promos = load(DATA_PROMO, [])
    now = datetime.now()
    new_promos = []
    for promo in promos:
        if isinstance(promo, dict):
            created = datetime.fromisoformat(promo.get("date"))
            if (now - created).days < PROMO_EXPIRATION_DAYS:
                new_promos.append(promo)
        else:
            new_promos.append(promo)
    save(DATA_PROMO, new_promos)

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
    kb.button(text="📜 Моя история промокодов", callback_data="history")
    kb.button(text="🛒 Пополнить баланс", url="http://hostilerust.gamestores.app/")
    kb.button(text="❓ Информация", callback_data="info")
    kb.adjust(2)
    return kb.as_markup()

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить промо", callback_data="a_add")
    kb.button(text="➖ Удалить промо", callback_data="a_del")
    kb.button(text="📋 Список промокодов", callback_data="a_list")
    kb.button(text="👥 Список пользователей", callback_data="a_users")
    kb.button(text="📊 Статистика", callback_data="a_stats")
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
            "first_name": m.from_user.first_name or "",
            "history": []  # сюда будем сохранять выданные промокоды
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
    remove_expired_promos()
    promos = load(DATA_PROMO, [])
    if not promos:
        return await cb.message.answer("❌ К сожалению, промокоды закончились 😢")

    promo_item = random.choice(promos)
    if isinstance(promo_item, dict):
        code = promo_item["code"]
    else:
        code = promo_item

    msg = (
        f"🎁 Ваш уникальный промокод:\n\n"
        f"<code>{code}</code>\n\n"
        "💡 Чтобы активировать его, перейдите на сайт:\n"
        "👉 http://hostilerust.gamestores.app/"
    )
    await cb.message.answer(msg, parse_mode="HTML")
    log.info(f"PROMO -> {cb.from_user.id} = {code}")

    users = load(DATA_USERS, {})
    user_id = str(cb.from_user.id)
    if user_id in users:
        if "history" not in users[user_id]:
            users[user_id]["history"] = []
        users[user_id]["history"].append(code)
        save(DATA_USERS, users)

@dp.callback_query(F.data == "history")
async def history(cb: CallbackQuery):
    users = load(DATA_USERS, {})
    user_id = str(cb.from_user.id)
    if user_id not in users or not users[user_id].get("history"):
        return await cb.message.answer("📜 У вас пока нет выданных промокодов")
    history_list = "\n".join([f"🎫 {p}" for p in users[user_id]["history"]])
    await cb.message.answer(f"📜 Ваша история промокодов:\n\n{history_list}")

@dp.callback_query(F.data == "info")
async def info(cb: CallbackQuery):
    text = (
        "❓ *Информация о промокодах и сервере*\n\n"
        "🎁 Промокоды:\n"
        "- Выдается через бота\n"
        "- Чтобы активировать, используйте на сайте: http://hostilerust.gamestores.app/\n\n"
        "💣 Вайпы:\n"
        "- Проходят каждый четверг в 12:00 МСК\n"
        "- Первый четверг месяца в 22:00 МСК\n\n"
        "⚠️ Правила сервера:\n"
        "- Не использовать читы\n"
        "- Уважать других игроков\n"
        "- Соблюдать общие правила Hostile Rust"
    )
    await cb.message.answer(text, parse_mode="Markdown")

# ================= ADMIN =================

def is_admin(user_id):
    return user_id in ADMIN_IDS

@dp.message(Command("admin"))
async def admin(m: Message):
    if not is_admin(m.from_user.id):
        return
    await m.answer("👑 Админ панель", reply_markup=admin_kb())

@dp.callback_query(F.data == "a_add")
async def a_add(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.set_state(AdminFSM.addpromo)
    await cb.message.answer("✏️ Введите новый промокод:")

@dp.message(AdminFSM.addpromo)
async def addpromo(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    promos = load(DATA_PROMO, [])
    new_item = {"code": m.text.strip(), "date": datetime.now().isoformat()}
    promos.append(new_item)
    save(DATA_PROMO, promos)
    await state.clear()
    await m.answer("✅ Промокод успешно добавлен 🎉")
    log.info(f"ADMIN ADD PROMO {m.text}")

@dp.callback_query(F.data == "a_del")
async def a_del(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.set_state(AdminFSM.delpromo)
    await cb.message.answer("❌ Какой промокод удалить?")

@dp.message(AdminFSM.delpromo)
async def delpromo(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    promos = load(DATA_PROMO, [])
    for p in promos:
        if p.get("code") == m.text.strip():
            promos.remove(p)
            save(DATA_PROMO, promos)
            await state.clear()
            await m.answer("🗑️ Промокод удалён")
            log.info(f"ADMIN DEL PROMO {m.text}")
            return
    await m.answer("❌ Промокод не найден")

@dp.callback_query(F.data == "a_list")
async def listpromo(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    promos = load(DATA_PROMO, [])
    text = "\n".join([f"🎫 {p['code']}" for p in promos]) if promos else "Пусто"
    await cb.message.answer(text)

@dp.callback_query(F.data == "a_users")
async def listusers(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    users = load(DATA_USERS, {})
    text = "\n".join([f"👤 {v['first_name']} (@{v['username']})" for v in users.values()]) or "Пусто"
    await cb.message.answer(text)

@dp.callback_query(F.data == "a_stats")
async def stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    users = load(DATA_USERS, {})
    promos = load(DATA_PROMO, [])
    total_users = len(users)
    total_promos = sum(len(u.get("history", [])) for u in users.values())
    most_active = max(users.items(), key=lambda x: len(x[1].get("history", [])))[1] if users else None
    active_text = f"{most_active['first_name']} (@{most_active['username']})" if most_active else "Нет"
    text = (
        f"📊 Статистика бота:\n\n"
        f"👥 Подписано пользователей: {total_users}\n"
        f"🎁 Всего выдано промокодов: {total_promos}\n"
        f"🏆 Самый активный игрок: {active_text}"
    )
    await cb.message.answer(text)

# ================= BROADCAST =================

@dp.callback_query(F.data == "a_bc")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.set_state(AdminFSM.broadcast)
    await cb.message.answer("✉️ Введите текст рассылки:")

@dp.message(AdminFSM.broadcast)
async def bc_text(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.update_data(bc_text=m.text)
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Отправить всем", callback_data="bc_send_all")
    kb.button(text="📤 Только новым игрокам", callback_data="bc_send_new")
    kb.button(text="❌ Отменить рассылку", callback_data="bc_cancel")
    kb.adjust(2)
    await state.set_state(AdminFSM.broadcast_confirm)
    await m.answer(f"📢 Текст рассылки:\n\n{m.text}", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("bc_send"))
async def bc_send(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    data = await state.get_data()
    text = data.get("bc_text")
    users = load(DATA_USERS, {})
    sent = 0
    if cb.data == "bc_send_new":
        targets = [u for u in users if not users[u].get("history")]
    else:
        targets = users.keys()
    for u in targets:
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
    if not is_admin(cb.from_user.id):
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
