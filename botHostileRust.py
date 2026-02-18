import json
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz

TOKEN = "7773566553:AAFxAVcGHnQk5SUQVY4EfgQDMxoVtWjnUo8"
ADMIN_ID = 411379361
CHAT_ID = -1001234567890

bot = Bot(TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()
tz = pytz.timezone("Europe/Moscow")

state = {}

def load(name):
    try:
        with open(f"data/{name}.json","r") as f:
            return json.load(f)
    except:
        return []

def save(name,data):
    with open(f"data/{name}.json","w") as f:
        json.dump(data,f,indent=2)

# ---------- USER ----------

@dp.message_handler(commands=["start"])
async def start(m):
    await m.answer("🔥 Hostile Rust\n/promo\n/steam STEAMID")

@dp.message_handler(commands=["promo"])
async def promo(m):
    promos = load("promocodes")
    if not promos:
        return await m.answer("Промокоды закончились")

    code = random.choice(promos)
    await m.answer(f"🎁 {code}")

@dp.message_handler(commands=["steam"])
async def steam(m):
    args = m.text.split()
    if len(args)!=2:
        return await m.answer("/steam 7656119XXXX")

    users = load("users")
    users.append({"tg":m.from_user.id,"steam":args[1]})
    save("users",users)

    await m.answer("✅ SteamID привязан")

# ---------- ADMIN PANEL ----------

def admin_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить","➖ Удалить")
    kb.add("📋 Все промо","🧹 Очистить")
    kb.add("👥 Пользователи","❌ Удалить Steam")
    kb.add("📢 Рассылка","⬅ Назад")
    return kb

@dp.message_handler(commands=["admin"])
async def admin(m):
    if m.from_user.id!=ADMIN_ID: return
    await m.answer("Админ панель",reply_markup=admin_kb())

@dp.message_handler(lambda m: m.text=="➕ Добавить")
async def add(m):
    state[m.from_user.id]="add"
    await m.answer("Отправь промокод")

@dp.message_handler(lambda m: m.text=="➖ Удалить")
async def rem(m):
    state[m.from_user.id]="del"
    await m.answer("Напиши промокод")

@dp.message_handler(lambda m: m.text=="📋 Все промо")
async def listpromo(m):
    await m.answer("\n".join(load("promocodes")) or "Пусто")

@dp.message_handler(lambda m: m.text=="🧹 Очистить")
async def clear(m):
    save("promocodes",[])
    await m.answer("Очищено")

@dp.message_handler(lambda m: m.text=="👥 Пользователи")
async def users(m):
    text=""
    for u in load("users"):
        text+=f'{u["tg"]} → {u["steam"]}\n'
    await m.answer(text or "Пусто")

@dp.message_handler(lambda m: m.text=="❌ Удалить Steam")
async def delsteam(m):
    state[m.from_user.id]="delsteam"
    await m.answer("Отправь TG ID")

@dp.message_handler(lambda m: m.text=="📢 Рассылка")
async def broadcast(m):
    state[m.from_user.id]="bc"
    await m.answer("Текст рассылки")

@dp.message_handler(lambda m: m.text=="⬅ Назад")
async def back(m):
    state.clear()
    await m.answer("Ок")

# ---------- STATE HANDLER ----------

@dp.message_handler()
async def handler(m):
    uid=m.from_user.id
    if uid not in state: return

    promos=load("promocodes")
    users=load("users")

    if state[uid]=="add":
        promos.append(m.text)
        save("promocodes",promos)
        await m.answer("Добавлено")

    elif state[uid]=="del":
        if m.text in promos:
            promos.remove(m.text)
            save("promocodes",promos)
            await m.answer("Удалено")

    elif state[uid]=="delsteam":
        users=[u for u in users if str(u["tg"])!=m.text]
        save("users",users)
        await m.answer("Удалено")

    elif state[uid]=="bc":
        for u in users:
            try:
                await bot.send_message(u["tg"],m.text)
            except: pass
        await m.answer("Рассылка завершена")

    state.pop(uid)

# ---------- WIPE ----------

async def wipe():
    await bot.send_message(CHAT_ID,"💣 ВАЙП HOSTILE RUST!")

def schedule():
    now=datetime.now(tz)
    for i in range(60):
        d=now+timedelta(days=i)
        if d.weekday()==3:
            hour=22 if d.day<=7 else 12
            scheduler.add_job(wipe,"date",
                run_date=tz.localize(datetime(d.year,d.month,d.day,hour)))

async def startup(dp):
    schedule()
    scheduler.start()
    print("Started")

executor.start_polling(dp,on_startup=startup)