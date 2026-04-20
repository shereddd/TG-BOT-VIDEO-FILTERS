# часть 1: базовый каркас бота - загрузка токена из .env, проверка ffmpeg, простые обработчики 

import os
import subprocess
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("ошибка: токен не найден в .env файле")
    sys.exit(1)

def check_ffmpeg():
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print("ошибка: ffmpeg не найден или не работает")
            sys.exit(1)
    except FileNotFoundError:
        print("ошибка: ffmpeg не установлен. установите ffmpeg для работы бота")
        sys.exit(1)
    except Exception as e:
        print(f"ошибка при проверке ffmpeg: {e}")
        sys.exit(1)

check_ffmpeg()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне видео для обработки")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Видео получено, обрабатываю...")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.run_polling()

if __name__ == "__main__":
    main()
