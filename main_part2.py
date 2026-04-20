# часть 2: добавлена обработка видео и документов - определение формата файла, базовая проверка расширения

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
    if update.message.video:
        file = await context.bot.get_file(update.message.video.file_id)
        file_extension = update.message.video.mime_type.split("/")[-1] if update.message.video.mime_type else "mp4"
    elif update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        file_name = update.message.document.file_name or "video"
        file_extension = file_name.split(".")[-1] if "." in file_name else "mp4"
    else:
        await update.message.reply_text("Ошибка: не удалось получить файл")
        return
    
    if file_extension.lower() not in ["mp4", "avi", "mov", "mkv", "webm"]:
        await update.message.reply_text(f"Ошибка: неподдерживаемый формат файла ({file_extension}). Поддерживаются: mp4, avi, mov, mkv, webm")
        return
    
    await update.message.reply_text("Видео получено, обрабатываю...")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.run_polling()

if __name__ == "__main__":
    main()
