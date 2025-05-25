import logging
import sqlite3, datetime, os

from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.callback_data import CallbackData

# ====== Ваш токен от BotFather ======
API_TOKEN = "7598191280:AAH8Fowm7Vj57XBkrxsHsoPfku__3MqcrAQ"
# ====================================

# Логи уровня INFO
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчер
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Папка для хранения фото
os.makedirs("uploads", exist_ok=True)

# CallbackData для inline-кнопок: act:action:project:job
cb = CallbackData("act", "action", "project", "job")


# Инициализация БД
def init_db():
    conn = sqlite3.connect("data.sqlite")
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY,
        client TEXT,
        moto TEXT,
        photo TEXT,
        created TEXT
      )
    ''')
    c.execute('''
      CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY,
        project_id INTEGER,
        desc TEXT,
        cost INTEGER,
        done INTEGER
      )
    ''')
    c.execute('''
      CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY,
        job_id INTEGER,
        amount INTEGER,
        paid_at TEXT
      )
    ''')
    conn.commit()
    conn.close()

init_db()


# Хэндлеры бота

@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Новый проект", "📋 Мои проекты")
    await msg.answer("Добро пожаловать в мотомастерскую!", reply_markup=kb)


@dp.message_handler(lambda m: m.text == "➕ Новый проект")
async def new_project_start(msg: types.Message):
    await msg.answer(
        "Введите имя клиента и данные мотоцикла через запятую, например:\n"
        "Иванов, Harley-Sportster 2021"
    )
    await dp.current_state(chat=msg.chat.id, user=msg.from_user.id).set_state("WAIT_PROJECT")


@dp.message_handler(lambda m: dp.current_state(chat=m.chat.id, user=m.from_user.id).is_state("WAIT_PROJECT"))
async def new_project_save(msg: types.Message):
    parts = msg.text.split(",", 1)
    if len(parts) != 2:
        return await msg.answer("Неправильный формат. Попробуйте ещё раз:\nИмя клиента, Мотоцикл")
    client, moto = parts[0].strip(), parts[1].strip()

    conn = sqlite3.connect("data.sqlite")
    c = conn.cursor()
    c.execute(
        "INSERT INTO projects(client,moto,created) VALUES(?,?,?)",
        (client, moto, datetime.datetime.now().isoformat())
    )
    pid = c.lastrowid
    conn.commit()
    conn.close()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Новый проект", "📋 Мои проекты")
    await msg.answer(f"Проект #{pid} создан: {client} — {moto}", reply_markup=kb)
    await dp.current_state(chat=msg.chat.id, user=msg.from_user.id).reset_state()


@dp.message_handler(lambda m: m.text == "📋 Мои проекты")
async def list_projects(msg: types.Message):
    conn = sqlite3.connect("data.sqlite")
    rows = conn.cursor().execute("SELECT id, client, moto FROM projects").fetchall()
    conn.close()

    if not rows:
        return await msg.answer("Проектов ещё нет, создайте первый через «➕ Новый проект»")

    kb = InlineKeyboardMarkup(row_width=1)
    for pid, client, moto in rows:
        kb.insert(
            InlineKeyboardButton(
                f"#{pid}: {client} — {moto}",
                callback_data=cb.new(action="view", project=pid, job=0)
            )
        )
    await msg.answer("Выберите проект:", reply_markup=kb)


@dp.callback_query_handler(cb.filter(action="view"))
async def callback_view(cbq: types.CallbackQuery, callback_data: dict):
    pid = int(callback_data["project"])
    conn = sqlite3.connect("data.sqlite")
    cur = conn.cursor()
    proj = cur.execute(
        "SELECT client, moto FROM projects WHERE id=?", (pid,)
    ).fetchone()
    jobs = cur.execute(
        "SELECT id, desc, cost, done FROM jobs WHERE project_id=?", (pid,)
    ).fetchall()
    conn.close()

    text = f"Проект #{pid}: {proj[0]} — {proj[1]}\n\nРаботы:\n"
    if jobs:
        for j in jobs:
            status = "✅" if j[3] else "❌"
            text += f"- #{j[0]} {j[1]} ({j[2]}₽) {status}\n"
    else:
        text += "— пока нет работ\n"

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            "➕ Добавить работу",
            callback_data=cb.new(action="add_job", project=pid, job=0)
        ),
        InlineKeyboardButton(
            "📌 Статус оплат",
            callback_data=cb.new(action="pay_status", project=pid, job=0)
        )
    )
    await cbq.message.edit_text(text, reply_markup=kb)
    await cbq.answer()


# Добавьте по аналогии хэндлеры для других действий при необходимости


# Запуск бота
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
