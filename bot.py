from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.utils.callback_data import CallbackData
from aiogram.utils import executor
import sqlite3, datetime, os, logging

API_TOKEN = "7598191280:AAH8Fowm7Vj57XBkrxsHsoPfku__3MqcrAQ"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ... (init_db точно так же)

cb = CallbackData("act", "action", "project", "job")

@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Новый проект", "📋 Мои проекты")
    await msg.answer("Добро пожаловать в мотомастерскую!", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "➕ Новый проект")
async def new_project_start(msg: types.Message, state: FSMContext):
    await msg.answer("Введите имя клиента и данные мотоцикла через запятую, например:\nИванов, Harley 2021")
    await state.set_state("WAIT_PROJECT")

@dp.message_handler(state="WAIT_PROJECT", content_types=types.Text)
async def new_project_save(msg: types.Message, state: FSMContext):
    # (код как выше)
    await state.finish()

@dp.message_handler(lambda m: m.text == "📋 Мои проекты", state="*")
async def list_projects(msg: types.Message):
    # ваш существующий код вывода проектов

@dp.callback_query_handler(cb.filter(action="add_job"))
async def callback_add_job(cbq: types.CallbackQuery, callback_data: dict, state: FSMContext):
    # (код как выше)

@dp.message_handler(state=lambda s: s and s.startswith("JOB_"), content_types=types.Text)
async def state_save_job(msg: types.Message, state: FSMContext):
    # (код как выше)

# ... остальные хендлеры

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
