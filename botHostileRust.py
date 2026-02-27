import a2s
import aiosqlite
from aiogram.types import InlineKeyboardButton
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
from database import Database

db = Database()

# ================= CONFIG =================

import os

TOKEN = os.getenv("BOTIK_TOKEN")
ADMIN_IDS = [411379361]  # Список админов
CHAT_ID = -1001234567890

DATA_DIR = Path("data")
DATA_PROMO = DATA_DIR / "promocodes.json"
LOG_FILE = DATA_DIR / "bot.log"
DATA_TICKETS = DATA_DIR / "tickets.json"
TICKET_COOLDOWN_MINUTES = 10
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
    
async def get_server_status(ip: str, port: int):
    loop = asyncio.get_running_loop()

    try:
        info = await loop.run_in_executor(
            None,
            lambda: a2s.info((ip, port), timeout=3)
        )

        return {
            "online": True,
            "players": info.player_count,
            "max": info.max_players
        }

    except Exception as e:
        log.error(f"A2S error {ip}:{port} -> {e}")
        return {"online": False}


        
def schedule():
    wipe = next_wipe()

    scheduler.add_job(
        wipe_notify,
        "date",
        run_date=wipe
    )

    scheduler.add_job(
        wipe_warning,
        "date",
        run_date=wipe - timedelta(hours=1)
    )
# ================= FSM =================

class AdminFSM(StatesGroup):
    addpromo = State()
    delpromo = State()
    broadcast = State()
    broadcast_confirm = State()
    ticket_answer = State()

class TicketFSM(StatesGroup):
    waiting_question = State()
# ================= BOT =================

bot = Bot(TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ================= KEYBOARDS =================
def main_text(first_name="Игрок"):
    return (
        f"🔥 *Приветствуем тебя, {first_name}!*\n\n"
        "📢 Ты попал в информационного бота серверов *Hostile Rust*!\n"
        "⬇️ Выбери действие ниже ⬇️"
    )

def main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Получить промокод", callback_data="promo")
    kb.button(text="📜 Моя история промокодов", callback_data="history")
    kb.button(text="🛒 Пополнить баланс", url="http://hostilerust.gamestores.app/")
    kb.button(text="❓ Информация", callback_data="info")
    kb.button(text="🎮 Онлайн серверов", callback_data="servers")
    kb.button(text="⏳ До вайпа", callback_data="wipe")
    kb.button(text="🔗 Оповещения о рейде", callback_data="link_raid")
    kb.button(text="📝 Задать вопрос", callback_data="ask_question")
    kb.button(text="📋 IP серверов", callback_data="ips")
    kb.adjust(2)
    return kb.as_markup()

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить промо", callback_data="a_add")
    kb.button(text="➖ Удалить промо", callback_data="a_del")
    kb.button(text="📋 Список промокодов", callback_data="a_list")
    kb.button(text="👥 Список пользователей", callback_data="a_users")
    kb.button(text="📊 Статистика", callback_data="a_stats")
    kb.button(text="📩 Все вопросы", callback_data="a_tickets")
    kb.button(text="📢 Рассылка", callback_data="a_bc")
    kb.button(text="⬅ Назад в меню", callback_data="admin_exit")
    kb.adjust(2)
    return kb.as_markup()

# ================= USER =================
def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()

@dp.message(Command("start"))
async def start(m: Message):
    # Добавляем пользователя в БД
    await db.add_user(m.from_user.id, m.from_user.username or "", m.from_user.first_name or "")
    log.info(f"🎉 NEW USER SUBSCRIBED {m.from_user.id}")

    welcome_text = (
        f"🔥 *Приветствуем тебя, {m.from_user.first_name or 'Игрок'}!*\n\n"
        "📢 Ты попал в информационного бота серверов *Hostile Rust*!\n"
        "⬇️ Выбери действие ниже ⬇️"
    )
    photo_url = "https://i.postimg.cc/4NjwLkNY/IMG-3850.png"  # ссылка на фото

    await bot.send_photo(
        chat_id=m.chat.id,
        photo=photo_url,
        caption=welcome_text,
        parse_mode="Markdown",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    await cb.answer()

    await cb.message.edit_caption(
        caption=main_text(cb.from_user.first_name or "Игрок"),
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )
    
@dp.callback_query(F.data == "promo")
async def promo(cb: CallbackQuery):
    """Выдача уникального промокода пользователю и сохранение истории в БД"""
    # Проверяем последний выданный промокод
    last = await db.get_last_promo(cb.from_user.id)
    if last:
        last_dt = datetime.fromisoformat(last)
        if datetime.now() - last_dt < timedelta(hours=24):
            return await cb.message.answer("⏳ Вы уже получали промокод сегодня.")

    # Удаляем просроченные промокоды из JSON
    remove_expired_promos()
    promos = load(DATA_PROMO, [])
    if not promos:
        return await cb.message.answer("❌ К сожалению, промокоды закончились 😢")

    # Выбираем случайный промокод
    promo_item = random.choice(promos)
    code = promo_item["code"] if isinstance(promo_item, dict) else promo_item

    # Сообщение пользователю
    msg = (
        f"🎁 Ваш уникальный промокод:\n\n"
        f"<code>{code}</code>\n\n"
        "💡 Чтобы активировать его, перейдите на сайт:\n"
        "👉 http://hostilerust.gamestores.app/"
    )
    await cb.message.edit_caption(
        caption=msg,
        reply_markup=back_kb(),
        parse_mode="HTML"
    )

    # Логируем в консоль
    log.info(f"PROMO -> {cb.from_user.id} = {code}")

    # Обновляем время последнего промо и сохраняем в историю
    await db.update_last_promo(cb.from_user.id)
    await db.add_promo_history(cb.from_user.id, code)

@dp.callback_query(F.data == "history")
async def history(cb: CallbackQuery):
    history = await db.get_user_history(cb.from_user.id)
    if not history:
        return await cb.message.answer("📜 У вас пока нет выданных промокодов")

    history_list = "\n".join([f"🎫 {p[0]} ({p[1]})" for p in history])
    await cb.message.edit_caption(
        caption=f"📜 Ваша история промокодов:\n\n{history_list}",
        reply_markup=back_kb(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "info")
async def info(cb: CallbackQuery):
    text = (
        "❓ <b>Информация о промокодах и сервере</b>\n\n"
        "✏️ Наши соц.сети:\n"
        "✏️ DISCORD: https://discord.gg/D6Rn6aXDhX\n"
        "✏️ Группа ВК: https://vk.com/hostile_rust\n\n"
        "🎁 Промокоды:\n"
        "- Выдаются через бота\n"
        "- Чтобы активировать его, зайдите на сайт и авторизуйтесь через Steam: http://hostilerust.gamestores.app/\n\n"
        "💣 Вайпы:\n"
        "- Проходят каждый четверг в 12:00 МСК\n"
        "- Первый четверг месяца в 22:00 МСК\n\n"
        "⚠️ Правила сервера:\n"
        "- Не использовать читы/макросы и прочие гадости\n"
        "- Уважать других игроков\n"
        "- Соблюдать общие правила серверов *Hostile Rust*"
    )

    await cb.message.edit_caption(
    caption=text,
    reply_markup=back_kb(),
    parse_mode="HTML"
)

@dp.callback_query(F.data == "link_raid")
async def link_raid(cb: CallbackQuery):

    tg_id = cb.from_user.id

    text = (
        "🔗 <b>Привязка рейд-уведомлений</b>\n\n"
        "1️⃣ Зайдите на сервер Hostile Rust и введите /link\n"
        "2️⃣ Введите ваш код в окно плагина:\n\n"
        f"<code>{tg_id}</code>\n\n"
        "3️⃣ После подтверждения вы будете получать\n"
        "уведомления о разрушении вашей базы в Telegram."
    )

    await cb.message.edit_caption(
    caption=text,
    reply_markup=back_kb(),
    parse_mode="HTML"
)   
    
@dp.callback_query(F.data == "ask_question")
async def ask_question(cb: CallbackQuery, state: FSMContext):
    users = load(DATA_USERS, {})
    uid = str(cb.from_user.id)

    last_ticket = users.get(uid, {}).get("last_ticket")

    if last_ticket:
        last_ticket = datetime.fromisoformat(last_ticket)
        if datetime.now() - last_ticket < timedelta(minutes=TICKET_COOLDOWN_MINUTES):
            return await cb.message.answer(
                f"⏳ Вы можете создавать вопрос только раз в {TICKET_COOLDOWN_MINUTES} минут."
            )

    await state.set_state(TicketFSM.waiting_question)
    await cb.message.answer("✏️ Напишите подробно ваш вопрос:")

async def auto_online_log():
    x5 = await get_server_status("37.230.137.6", 20601)
    x100 = await get_server_status("46.174.50.248", 20641)
    log.info(f"AUTO ONLINE x5={x5} x100={x100}")
    
async def wipe_notify():
    users = load(DATA_USERS, {})
    for uid in users:
        try:
            await bot.send_message(uid, "💣 ВАЙП серверов Hostile Rust!")
        except:
            pass

# ================= ADMIN =================

def is_admin(user_id):
    return user_id in ADMIN_IDS

@dp.message(Command("admin"))
async def admin(m: Message):
    if not is_admin(m.from_user.id):
        return

    await m.answer(
        "👑 <b>Админ панель Hostile Rust by Derso</b>\n\nВыберите действие:",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )
@dp.callback_query(F.data == "a_add")
async def a_add(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.set_state(AdminFSM.addpromo)
    await cb.message.edit_text("✏️ Введите новый промокод:")

@dp.callback_query(F.data == "admin_exit")
async def admin_exit(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    await cb.message.edit_text(
        main_text(cb.from_user.first_name or "Игрок"),
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )    
    
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
async def a_del(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    promos = load(DATA_PROMO, [])

    if not promos:
        return await cb.message.edit_text("📄 Список промокодов пуст")

    kb = InlineKeyboardBuilder()

    now = datetime.now()

    for p in promos:
        if isinstance(p, dict):
            code = p["code"]
            created = datetime.fromisoformat(p["date"])
            days_left = PROMO_EXPIRATION_DAYS - (now - created).days
            text = f"{code} | осталось {days_left} дн."
        else:
            code = p
            text = code

        kb.button(
            text=f"🗑 {text}",
            callback_data=f"delpromo_confirm_{code}"
        )

    kb.button(text="⬅ Назад", callback_data="admin_back")

    kb.adjust(1)

    await cb.message.answer(
        "❌ Выберите промокод для удаления:",
        reply_markup=kb.as_markup()
    )
@dp.callback_query(F.data.startswith("delpromo_confirm_"))
async def confirm_delete_promo(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    code = cb.data.replace("delpromo_confirm_", "")

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить", callback_data=f"delpromo_yes_{code}")
    kb.button(text="❌ Отмена", callback_data="a_del")
    kb.adjust(1)

    await cb.message.edit_text(
        f"⚠️ Вы уверены что хотите удалить промокод:\n\n🎫 {code} ?",
        reply_markup=kb.as_markup()
    )
@dp.callback_query(F.data.startswith("delpromo_yes_"))
async def delete_promo(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    code_to_delete = cb.data.replace("delpromo_yes_", "")

    promos = load(DATA_PROMO, [])
    new_promos = []

    deleted = False

    for p in promos:
        code = p["code"] if isinstance(p, dict) else p
        if code == code_to_delete:
            deleted = True
            continue
        new_promos.append(p)

    if deleted:
        save(DATA_PROMO, new_promos)
        log.info(f"ADMIN DEL PROMO {code_to_delete}")

        await cb.message.edit_text(
            f"🗑 Промокод {code_to_delete} успешно удалён ✅",
            reply_markup=admin_kb()
        )
    else:
        await cb.answer("❌ Промокод не найден", show_alert=True)
@dp.callback_query(F.data == "admin_back")
async def admin_back(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "👑 Админ панель by Derso",
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data == "a_list")
async def listpromo(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    promos = load(DATA_PROMO, [])
    if not promos:
        await cb.message.edit_text(
    f"📋 <b>Список промокодов:</b>\n\n{text}",
    reply_markup=admin_kb(),
    parse_mode="HTML"
)
        return

    text_list = []
    for p in promos:
        if isinstance(p, dict) and "code" in p:
            text_list.append(f"🎫 {p['code']}")
        elif isinstance(p, str):
            text_list.append(f"🎫 {p}")
    text = "\n".join(text_list) if text_list else "📄 Список промокодов пуст"
    await cb.message.answer(text)

@dp.message(TicketFSM.waiting_question)
async def save_question(m: Message, state: FSMContext):
    # Проверяем лимит тикетов за X минут
    last = await db.get_last_promo(m.from_user.id)  # Можно сделать отдельное поле last_ticket
    # для простоты оставим проверку через last_promo или добавим last_ticket в users

    await db.add_ticket(m.from_user.id, m.from_user.username or "", m.from_user.first_name or "", m.text)
    await state.clear()
    await m.answer("✅ Ваш вопрос отправлен администрации *Hostile Rust*! Ожидайте ответа.")

    # уведомление админам
    tickets = await db.get_open_tickets()
    ticket_id = tickets[-1][0]  # последний добавленный
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Ответить", callback_data=f"ticket_answer_{ticket_id}")
    kb.adjust(1)

    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"📩 Новый вопрос под номером #{ticket_id}\n\n"
            f"👤 @{m.from_user.username}\n"
            f"👤 {m.from_user.first_name}\n"
            f"📝 {m.text}",
            reply_markup=kb.as_markup()
        )

@dp.callback_query(F.data == "a_tickets")
async def list_tickets(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    tickets = await db.get_open_tickets()
    if not tickets:
        return await cb.message.edit_text("📭 Нет активных вопросов", reply_markup=admin_kb())

    text = "📩 <b>Активные вопросы:</b>\n\n"
    for t in tickets:
        text += f"#{t[0]} | @{t[2]}\n{t[4]}\n\n"

    await cb.message.edit_text(text, reply_markup=admin_kb(), parse_mode="HTML")
        
@dp.callback_query(F.data.startswith("ticket_answer_"))
async def ticket_answer_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return

    ticket_id = int(cb.data.split("_")[-1])

    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AdminFSM.ticket_answer)

    await cb.message.answer(f"✏️ Введите ответ на вопрос. Номер:#{ticket_id}:")
    
@dp.message(AdminFSM.ticket_answer)
async def ticket_answer_send(m: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    # Получаем тикет из БД
    tickets = await db.get_open_tickets()
    ticket = next((t for t in tickets if t[0] == ticket_id), None)

    if not ticket:
        return await m.answer("❌ Вопрос не найден или уже закрыт")

    try:
        await bot.send_message(ticket[1], f"📩 Ответ на ваш вопрос #{ticket_id}:\n\n{m.text}")
    except:
        pass

    await db.answer_ticket(ticket_id)
    await state.clear()
    await m.answer("✅ Ответ отправлен игроку")

@dp.callback_query(F.data == "a_users")
async def listusers(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    async with aiosqlite.connect(db.path) as conn:
        cursor = await conn.execute("SELECT first_name, username FROM users")
        users = await cursor.fetchall()

    text = "\n".join([f"👤 {u[0]} (@{u[1]})" for u in users]) or "Пусто"
    await cb.message.edit_text(
        f"👥 <b>Пользователи:</b>\n\n{text}",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "a_stats")
async def stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return

    total_users = await db.count_users()
    total_promos = await db.count_total_promos()

    async with aiosqlite.connect(db.path) as conn:
        cursor = await conn.execute("""
            SELECT u.first_name, u.username, COUNT(p.id) as promo_count
            FROM users u
            LEFT JOIN promo_history p ON u.telegram_id = p.telegram_id
            GROUP BY u.telegram_id
            ORDER BY promo_count DESC
            LIMIT 1
        """)
        most_active = await cursor.fetchone()

    active_text = f"{most_active[0]} (@{most_active[1]})" if most_active else "Нет"

    text = (
        f"📊 Статистика бота:\n\n"
        f"👥 Подписано всего пользователей: {total_users}\n"
        f"🎁 Всего выдано промокодов: {total_promos}\n"
        f"🏆 Самый активный игрок: {active_text}"
    )
    await cb.message.edit_text(
        text,
        reply_markup=admin_kb()
    )

# ================= BROADCAST =================

@dp.callback_query(F.data == "servers")
async def servers(cb: CallbackQuery):

    x5, x100 = await asyncio.gather(
        get_server_status("37.230.137.6", 20601),
        get_server_status("46.174.50.248", 20641)
    )

    def fmt(name, data):
        if not data["online"]:
            return f"🔴 {name}: оффлайн"
        return f"🟢 {name}: {data['players']}/{data['max']}"

    text = (
        "🎮 *Статус серверов Hostile Rust*\n\n"
        f"{fmt('x5', x5)}\n"
        f"{fmt('x100', x100)}"
    )

    await cb.message.edit_caption(
    caption=text,
    reply_markup=back_kb(),
    parse_mode="Markdown"
)


    
@dp.callback_query(F.data == "ips")
async def ips(cb: CallbackQuery):

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📋 Скопировать Hostile x5",
        switch_inline_query_current_chat="connect 37.230.137.6:20600"
    )

    kb.button(
        text="📋 Скопировать Hostile x100",
        switch_inline_query_current_chat="connect 46.174.50.248:20640"
    )

    # КНОПКА НАЗАД
    kb.button(text="⬅️ Назад", callback_data="back_main")

    kb.adjust(1)

    await cb.message.edit_caption(
        caption=(
            "📜 *IP серверов Hostile Rust*\n\n"
            "Нажми кнопку — команда появится в поле ввода.\n"
            "Дальше просто скопируй и вставь в консоли игры 👇"
        ),
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )

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

    if cb.data == "bc_send_new":
        targets = await db.get_users_without_promos()
    else:
        targets = await db.get_all_user_ids()

    sent = 0
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

def next_wipe():
    now = datetime.now(tz)

    for i in range(14):
        d = now + timedelta(days=i)
        if d.weekday() == 3:
            hour = 22 if d.day <= 7 else 12
            wipe = tz.localize(datetime(d.year, d.month, d.day, hour))
            if wipe > now:
                return wipe

@dp.callback_query(F.data == "wipe")
async def wipe_timer(cb: CallbackQuery):
    wipe = next_wipe()
    now = datetime.now(tz)

    diff = wipe - now

    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60

    text = (
        "💣 *До следующего вайп на серверах Hostile Rust*\n\n"
        f"⏳ Осталось:\n"
        f"🗓 {days} дн\n"
        f"🕒 {hours} ч\n"
        f"⏱ {minutes} мин"
    )

    await cb.message.edit_caption(
    caption=text,
    reply_markup=back_kb(),
    parse_mode="Markdown"
)
    
async def wipe_notify():
    users = await db.get_all_user_ids()
    for uid in users:
        try:
            await bot.send_message(uid, "💣 ВАЙП СЕРВЕРОВ HOSTILE RUST!")
        except:
            pass

async def wipe_warning():
    users = await db.get_all_user_ids()
    for uid in users:
        try:
            await bot.send_message(uid, "⚠️ Через 1 час вайп серверов Hostile Rust!")
        except:
            pass
# ================= START =================

async def main():
    await db.init()  # Инициализация БД
    schedule()
    scheduler.start()
    scheduler.add_job(auto_online_log, "interval", minutes=5)
    log.info("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


