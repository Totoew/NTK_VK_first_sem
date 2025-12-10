import os
import json
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram._utils.types import ReplyMarkup
from typing import List, Dict, Optional
import random
import asyncio
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def load_questions(file_path: str) -> List[Dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content.endswith(','):
                content = content[:-1]
            if not content.startswith('['):
                content = f'[{content}]'
            questions = json.loads(content)

        validated_questions = []
        for q in questions:
            if not all(key in q for key in ['question', 'answers']):
                continue
            correct_answers = [a for a in q['answers'] if a.get('correct')]
            if len(correct_answers) != 1:
                continue
            validated_questions.append({
                "question": q["question"],
                "answers": [a["text"] for a in q["answers"]],
                "correct": correct_answers[0]["text"]
            })

        return validated_questions
    except Exception as e:
        print(f"Ошибка при загрузке файла {file_path}: {e}")
        return []

# Загружаем все наборы вопросов
FILE_QUESTIONS = {
    "inzh": load_questions("./data/inzh.json"),
    "med": load_questions("./data/med.json"),
    "ottp": load_questions("./data/ottp.json"),
    "vizh": load_questions("./data/vizh.json"),
    "vtop": load_questions("./data/vtop.json"),
    "all": load_questions("./data/all.json")
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Рандомные вопросы", callback_data="mode_random")],
        [InlineKeyboardButton("По порядку", callback_data="mode_sequential")]
    ]
    await update.message.reply_text(
        "📚 Выберите режим вопросов:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mode"] = query.data.split("_")[1]
    await query.edit_message_text(
        "🔍 Теперь выберите набор вопросов:\n"
        "/inzh - Инженерная подготовка\n"
        "/med - Медицинская подготовка\n"
        "/ottp - Общая тактика. Тактическая подготовка\n"
        "/vizh - Основы выживания\n"
        "/vtop - Военная топография\n"
        "/all - Все вопросы"
    )

async def select_set(update: Update, context: ContextTypes.DEFAULT_TYPE, set_key: str):
    if not FILE_QUESTIONS[set_key]:
        await update.message.reply_text("❌ Вопросы из этого набора не загружены.")
        return

    context.user_data.update({
        "selected_questions": FILE_QUESTIONS[set_key],
        "current_set": set_key,
        "current_index": 0,
        "correct_answers": 0,
        "wrong_answers": [],
        "total_questions": len(FILE_QUESTIONS[set_key])
    })

    await update.message.reply_text(
        f"✅ Набор «{set_key.upper()}» выбран. Введите /quiz чтобы начать!\n"
        f"Режим: {'рандомный' if context.user_data.get('mode') == 'random' else 'по порядку'}"
    )

async def send_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = context.user_data.get("selected_questions")
    if not questions:
        await (update.message or update.callback_query.message).reply_text("❗️ Сначала выберите набор: /inzh /med /ottp /vizh /vtop /all")
        return

    mode = context.user_data.get("mode", "random")

    if mode == "sequential":
        index = context.user_data["current_index"]
        if index >= len(questions):
            await show_stats(update, context)
            return
        question_data = questions[index]
        context.user_data["current_index"] = index + 1
    else:
        question_data = random.choice(questions)

    context.user_data["current_question"] = question_data

    answers_text = "\n".join(
        [f"{i + 1}. {ans}" for i, ans in enumerate(question_data["answers"])]
    )

    buttons = [
        InlineKeyboardButton(text=str(i + 1), callback_data=f"ans_{i}")
        for i in range(len(question_data["answers"]))
    ]

    await (update.message or update.callback_query.message).reply_text(
        text=f"❓ {question_data['question']}\n\n{answers_text}",
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    question_data = context.user_data.get("current_question")
    if not question_data:
        await query.edit_message_text("❌ Вопрос не найден.")
        return

    answer_idx = int(query.data.split('_')[1])
    selected = question_data["answers"][answer_idx]
    correct = question_data["correct"]

    if selected == correct:
        context.user_data["correct_answers"] += 1
        await query.edit_message_text(f"{query.message.text}\n\n✅ Правильно! {selected}")
    else:
        question_number = context.user_data.get("current_index", 1)
        context.user_data["wrong_answers"].append(question_number)
        await query.edit_message_text(
            f"{query.message.text}\n\n❌ Неверно! Ваш ответ: {selected}\n"
            f"Правильный ответ: {correct}"
        )

    await send_quiz(update, context)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = (
        f"📊 Статистика по теме {context.user_data['current_set'].upper()}:\n"
        f"✅ Правильных ответов: {context.user_data['correct_answers']}/{context.user_data['total_questions']}\n"
    )

    if context.user_data["wrong_answers"]:
        stats += f"❌ Ошибки в вопросах: {', '.join(map(str, context.user_data['wrong_answers']))}\n"

    stats += "Введите /quiz чтобы начать заново или выберите другой набор."
    await (update.message or update.callback_query.message).reply_text(stats)
    context.user_data.clear()

def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        raise ValueError("Не найден токен бота в переменных окружения!")
        
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", send_quiz))
    app.add_handler(CommandHandler("inzh", lambda u, c: select_set(u, c, "inzh")))
    app.add_handler(CommandHandler("med", lambda u, c: select_set(u, c, "med")))
    app.add_handler(CommandHandler("ottp", lambda u, c: select_set(u, c, "ottp")))
    app.add_handler(CommandHandler("vizh", lambda u, c: select_set(u, c, "vizh")))
    app.add_handler(CommandHandler("vtop", lambda u, c: select_set(u, c, "vtop")))
    app.add_handler(CommandHandler("all", lambda u, c: select_set(u, c, "all")))
    app.add_handler(CallbackQueryHandler(select_mode, pattern="^mode_"))
    app.add_handler(CallbackQueryHandler(check_answer, pattern="^ans_"))

    """Настраивает меню команд в интерфейсе"""
    commands = [
        ("start", "Для выбора режима: по порядку, рандомные вопросы"),
    ]
    
    from telegram import BotCommand
    bot_commands = [BotCommand(command, description) for command, description in commands]
    
    async def set_commands(app):
        await app.bot.set_my_commands(bot_commands)
    
    # Устанавливаем команды при запуске
    app.post_init = set_commands

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()