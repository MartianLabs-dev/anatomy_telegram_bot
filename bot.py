import asyncio
import json
import random
import logging
import os
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import db

# Настройка логирования
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

with open('questions.json', 'r', encoding='utf-8') as f:
    QUESTIONS = json.load(f)

bot = Bot(token=BOT_TOKEN if BOT_TOKEN else "DUMMY_TOKEN")
dp = Dispatcher(storage=MemoryStorage())

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎫 Тянуть билет")],
        [KeyboardButton(text="📊 Моя статистика")]
    ],
    resize_keyboard=True
)

class TicketState(StatesGroup):
    answering = State()

def get_question_inline_kb(hint_used=False, answer_shown=False):
    kb = []
    if not answer_shown:
        if not hint_used:
            kb.append([InlineKeyboardButton(text="💡 Подсказка", callback_data="hint")])
        kb.append([InlineKeyboardButton(text="👁 Показать ответ", callback_data="show_answer")])
    else:
        kb.append([
            InlineKeyboardButton(text="✅ Знал", callback_data="ans_correct"),
            InlineKeyboardButton(text="❌ Ошибся", callback_data="ans_wrong")
        ])
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def send_next_question(message_or_call, state: FSMContext):
    data = await state.get_data()
    q_index = data['current_q_index']
    questions_list = data['questions_list']
    
    if q_index >= len(questions_list):
        correct_count = data['correct_in_ticket']
        is_ideal = (correct_count == len(questions_list))
        user_id = message_or_call.from_user.id
        
        await db.record_ticket_completion(user_id, is_ideal)
        
        text = f"🎉 <b>Билет завершен!</b>\n\nПравильных ответов: {correct_count} из {len(questions_list)}"
        if is_ideal:
            text += "\n🌟 Идеальный билет! Так держать!"
            
        if isinstance(message_or_call, CallbackQuery):
            await message_or_call.message.answer(text, parse_mode="HTML")
        else:
            await message_or_call.answer(text, parse_mode="HTML")
            
        await state.clear()
        return

    q_data = questions_list[q_index]
    text = f"<b>Вопрос {q_index + 1}/5</b>\n\n{q_data['question']}"
    
    await state.update_data(current_hint_used=False)
    kb = get_question_inline_kb()
    
    if isinstance(message_or_call, CallbackQuery):
        await message_or_call.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_call.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await db.register_user(message.from_user.id, message.from_user.username)
    welcome_text = (
        "Привет! Я бот для тренировки знаний по Анатомии и Биомеханике. 🏋️‍♂️\n"
        "В моей базе 200 вопросов.\n\n"
        "Жми <b>«🎫 Тянуть билет»</b> чтобы начать проверку (билет состоит из 5 случайных вопросов)."
    )
    await message.answer(welcome_text, reply_markup=main_kb, parse_mode="HTML")

@dp.message(F.text == "📊 Моя статистика")
async def show_stats(message: Message):
    stats = await db.get_user_stats(message.from_user.id)
    if not stats:
        await message.answer("Статистика пока пуста. Попробуй вытянуть билет!")
        return
        
    text = (
        "📊 <b>Твоя статистика:</b>\n\n"
        f"🎫 Пройдено билетов: {stats['total_tickets']}\n"
        f"🌟 Идеальных билетов (без ошибок): {stats['ideal_tickets']}\n\n"
        f"❓ Отвечено вопросов: {stats['total_questions']}\n"
        f"✅ Правильно: {stats['correct_answers']}\n"
        f"❌ Ошибок: {stats['incorrect_answers']}\n"
        f"💡 Использовано подсказок: {stats['hints_used']}"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🎫 Тянуть билет")
async def start_ticket(message: Message, state: FSMContext):
    ticket_questions = random.sample(QUESTIONS, 5)
    await state.set_state(TicketState.answering)
    await state.update_data(
        questions_list=ticket_questions,
        current_q_index=0,
        correct_in_ticket=0,
        current_hint_used=False
    )
    await message.answer("🎟 <b>Новый билет вытянут! Поехали:</b>", parse_mode="HTML")
    await send_next_question(message, state)

@dp.callback_query(TicketState.answering, F.data == "hint")
async def process_hint(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    q_data = data['questions_list'][data['current_q_index']]
    await state.update_data(current_hint_used=True)
    text = f"<b>Вопрос {data['current_q_index'] + 1}/5</b>\n\n{q_data['question']}\n\n<i>{q_data['hint']}</i>"
    kb = get_question_inline_kb(hint_used=True, answer_shown=False)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(TicketState.answering, F.data == "show_answer")
async def process_show_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    q_data = data['questions_list'][data['current_q_index']]
    hint_used = data['current_hint_used']
    text = f"<b>Вопрос {data['current_q_index'] + 1}/5</b>\n\n{q_data['question']}\n\n<b>Ответ:</b> {q_data['answer']}"
    kb = get_question_inline_kb(hint_used=hint_used, answer_shown=True)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(TicketState.answering, F.data.in_({"ans_correct", "ans_wrong"}))
async def process_answer_result(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_correct = (callback.data == "ans_correct")
    hint_used = data['current_hint_used']
    user_id = callback.from_user.id
    
    await db.record_question_result(user_id, is_correct, hint_used)
    
    correct_in_ticket = data['correct_in_ticket']
    if is_correct: correct_in_ticket += 1
        
    await state.update_data(current_q_index=data['current_q_index'] + 1, correct_in_ticket=correct_in_ticket)
    
    old_text = callback.message.html_text
    result_emoji = "✅" if is_correct else "❌"
    await callback.message.edit_text(f"{old_text}\n\n<i>Твой ответ: {result_emoji}</i>", parse_mode="HTML")
    await send_next_question(callback, state)
    await callback.answer()

# --- ФИКТИВНЫЙ ВЕБ-СЕРВЕР ДЛЯ ОБХОДА ПРАВИЛ RENDER ---
async def health_check(request):
    return web.Response(text="Bot is running smoothly!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render автоматически задает порт в переменной окружения PORT
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Dummy web server started on port {port}")

async def main():
    await db.init_db()
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN не найден. Остановка.")
        return
        
    # Запускаем фиктивный сервер, чтобы Render думал, что это веб-сайт
    await start_dummy_server()
    # Запускаем самого бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
