import asyncpg
import os
import logging

DATABASE_URL = os.getenv("DATABASE_URL")
pool = None

async def init_db():
    global pool
    if not DATABASE_URL:
        logging.error("ВНИМАНИЕ: DATABASE_URL не установлен. Бот не сможет сохранять статистику.")
        return
    
    # Создаем пул подключений к PostgreSQL
    pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with pool.acquire() as conn:
        # В PostgreSQL PRIMARY KEY для ID Telegram должен быть BIGINT
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                total_tickets INTEGER DEFAULT 0,
                ideal_tickets INTEGER DEFAULT 0,
                total_questions INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                incorrect_answers INTEGER DEFAULT 0,
                hints_used INTEGER DEFAULT 0
            )
        ''')
        logging.info("База данных PostgreSQL успешно инициализирована.")

async def get_user_stats(user_id):
    if not pool: return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT total_tickets, ideal_tickets, total_questions, correct_answers, incorrect_answers, hints_used FROM users WHERE user_id = $1', user_id)
        if row:
            return dict(row)
        return None

async def register_user(user_id, username):
    if not pool: return
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        ''', user_id, username)

async def record_question_result(user_id, is_correct, hint_used):
    if not pool: return
    async with pool.acquire() as conn:
        if is_correct:
            await conn.execute('UPDATE users SET total_questions = total_questions + 1, correct_answers = correct_answers + 1 WHERE user_id = $1', user_id)
        else:
            await conn.execute('UPDATE users SET total_questions = total_questions + 1, incorrect_answers = incorrect_answers + 1 WHERE user_id = $1', user_id)
            
        if hint_used:
            await conn.execute('UPDATE users SET hints_used = hints_used + 1 WHERE user_id = $1', user_id)

async def record_ticket_completion(user_id, is_ideal):
    if not pool: return
    async with pool.acquire() as conn:
        if is_ideal:
            await conn.execute('UPDATE users SET total_tickets = total_tickets + 1, ideal_tickets = ideal_tickets + 1 WHERE user_id = $1', user_id)
        else:
            await conn.execute('UPDATE users SET total_tickets = total_tickets + 1 WHERE user_id = $1', user_id)
