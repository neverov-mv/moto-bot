import logging
import sqlite3
import datetime
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils import executor
from aiogram.utils.callback_data import CallbackData
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# ====== Ваш токен ======
API_TOKEN = "7598191280:AAH8Fowm7Vj57XBkrxsHsoPfku__3MqcrAQ"
# =======================

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и хранилища FSM
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# CallbackData для inline-кнопок
cb = CallbackData("act", "action", "project", "job")

# FSM-состояния
class ProjectForm(StatesGroup):
    waiting_for_project = State()

class JobForm(StatesGroup):
    waiting_for_job = State()

# Папка для фото (если понадобится)
os.makedirs("uploads", exist_ok=True)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("data.sqlite")
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY,
        client TEXT,
        moto TEXT,
        created TEXT
      )
    ''')
    c.execute('''
      CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY,
        project_id INTEGER,
        description TEXT,
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

# /start — главное меню
@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Новый проект", "📋 Мои проекты")
    await msg.answer("Добро пожаловать в мотомастерскую!", reply_markup=kb)

# Начало создания проекта
@dp.message_handler(lambda m: m.text == "➕ Новый проект", state="*")
async def new_project_start(msg: types.Message):
    await msg.answer(
        "Введите имя клиента и данные мотоцикла через запятую:\n"
        "Пример: Иванов, Harley-Sportster 2021"
    )
    await ProjectForm.waiting_for_project.set()

# Сохранение проекта
@dp.message_handler(state=ProjectForm.waiting_for_project, content_types=["text"])
async def new_project_save(msg: types.Message, state: FSMContext):
    parts = msg.text.split(",", 1)
    if len(parts) != 2:
        return await msg.answer(
            "Неверный формат. Попробуйте ещё раз:\nИмя клиента, Мотоцикл"
        )
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
    await msg.answer(f"✅ Проект #{pid} создан: {client} — {moto}", reply_markup=kb)
    await state.finish()

# Список проектов
@dp.message_handler(lambda m: m.text == "📋 Мои проекты", state="*")
async def list_projects(msg: types.Message):
    conn = sqlite3.connect("data.sqlite")
    rows = conn.cursor().execute("SELECT id, client, moto FROM projects").fetchall()
    conn.close()

    if not rows:
        return await msg.answer("Проектов ещё нет — создайте первый через «➕ Новый проект»")

    kb = InlineKeyboardMarkup(row_width=1)
    for pid, client, moto in rows:
        kb.insert(
            InlineKeyboardButton(
                f"#{pid}: {client} — {moto}",
                callback_data=cb.new(action="view", project=pid, job=0)
            )
        )
    await msg.answer("Выберите проект:", reply_markup=kb)

# Просмотр проекта и работ + кнопки оплаты
@dp.callback_query_handler(cb.filter(action="view"))
async def callback_view_project(cbq: types.CallbackQuery, callback_data: dict):
    pid = int(callback_data["project"])
    conn = sqlite3.connect("data.sqlite")
    cur = conn.cursor()
    proj = cur.execute("SELECT client, moto FROM projects WHERE id=?", (pid,)).fetchone()
    jobs = cur.execute(
        "SELECT id, description, cost, done FROM jobs WHERE project_id=?", (pid,)
    ).fetchall()
    conn.close()

    text = f"📋 Проект #{pid}: {proj[0]} — {proj[1]}\n\n🛠 Работы:\n"
    if jobs:
        for j in jobs:
            status = "✅" if j[3] else "❌"
            text += f"- #{j[0]} {j[1]} ({j[2]}₽) {status}\n"
    else:
        text += "— нет работ\n"

    kb = InlineKeyboardMarkup(row_width=1)
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
    # Кнопка оплаты для каждой работы
    for job_id, desc, cost, done in jobs:
        kb.insert(
            InlineKeyboardButton(
                f"💸 Оплатить #{job_id} ({desc})",
                callback_data=cb.new(action="mark_paid", project=pid, job=job_id)
            )
        )

    await cbq.message.edit_text(text, reply_markup=kb)
    await cbq.answer()

# Начало добавления работы
@dp.callback_query_handler(cb.filter(action="add_job"))
async def callback_add_job(cbq: types.CallbackQuery, callback_data: dict, state: FSMContext):
    pid = int(callback_data["project"])
    await state.update_data(project_id=pid)
    await cbq.message.answer(
        "Введите описание работы и стоимость через запятую:\n"
        "Пример: Покраска бака, 15000"
    )
    await JobForm.waiting_for_job.set()
    await cbq.answer()

# Сохранение работы
@dp.message_handler(state=JobForm.waiting_for_job, content_types=["text"])
async def state_save_job(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("project_id")

    parts = msg.text.split(",", 1)
    if len(parts) != 2:
        return await msg.answer("Неверный формат. Попробуйте:\nНазвание работы, цена")
    desc, cost = parts[0].strip(), int(parts[1].strip())

    conn = sqlite3.connect("data.sqlite")
    c = conn.cursor()
    c.execute(
        "INSERT INTO jobs(project_id,description,cost,done) VALUES(?,?,?,0)",
        (pid, desc, cost)
    )
    conn.commit()
    conn.close()

    await msg.answer(f"✅ Работа добавлена к проекту #{pid}")
    await state.finish()

# Статус оплат
@dp.callback_query_handler(cb.filter(action="pay_status"))
async def callback_pay_status(cbq: types.CallbackQuery, callback_data: dict):
    pid = int(callback_data["project"])
    conn = sqlite3.connect("data.sqlite")
    rows = conn.cursor().execute(
        "SELECT j.id, j.description, j.cost, IFNULL(SUM(p.amount),0) "
        "FROM jobs j LEFT JOIN payments p ON j.id=p.job_id "
        "WHERE j.project_id=? GROUP BY j.id",
        (pid,)
    ).fetchall()
    conn.close()

    text = f"💰 Статус оплат по проекту #{pid}:\n"
    for j in rows:
        paid = j[3]
        text += f"- #{j[0]} {j[1]}: {paid}/{j[2]}₽\n"
    await cbq.message.answer(text)
    await cbq.answer()

# Хендлер оплаты работы
@dp.callback_query_handler(cb.filter(action="mark_paid"))
async def callback_mark_paid(cbq: types.CallbackQuery, callback_data: dict):
    job_id = int(callback_data["job"])
    # Узнаём стоимость работы
    conn = sqlite3.connect("data.sqlite")
    cur = conn.cursor()
    row = cur.execute("SELECT cost FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        await cbq.answer("Работа не найдена.", show_alert=True)
        conn.close()
        return
    cost = row[0]
    # Создаём платёж
    cur.execute(
        "INSERT INTO payments(job_id, amount, paid_at) VALUES(?,?,?)",
        (job_id, cost, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    await cbq.answer(f"💰 Работа #{job_id} оплачена: {cost}₽", show_alert=True)
    # Перерисуем меню проекта
    await callback_view_project(cbq, {"action":"view", "project": callback_data["project"], "job":"0"})

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
