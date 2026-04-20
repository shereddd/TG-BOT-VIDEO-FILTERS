# часть 9: добавлена полная логика обработки видео - скачивание, применение фильтра, отправка результата пользователю

import os
import subprocess
import sys
import tempfile
import time
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

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

def get_filter_sepia():
    return "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"

def get_filter_bw():
    return "hue=s=0"

def get_filter_sharpen():
    return "unsharp=5:5:1.0:5:5:0.0"

def get_filter_blur():
    return "boxblur=2:1"

def get_filter_vignette():
    return "vignette=PI/4"

def get_filter_invert():
    return "negate"

def get_filter_saturate():
    return "eq=saturation=1.5"

def get_filter_vhs():
    return "noise=alls=20:allf=t+u,curves=preset=lighter,eq=gamma=1.2"

def get_filter_oldfilm():
    return "noise=alls=30:allf=t+u,curves=preset=vintage,eq=gamma=0.8:contrast=1.2"

def get_filter_contrast():
    return "eq=contrast=1.5:brightness=0.05"

def get_filter_by_name(filter_name):
    filters_map = {
        "sepia": get_filter_sepia,
        "bw": get_filter_bw,
        "sharpen": get_filter_sharpen,
        "blur": get_filter_blur,
        "vignette": get_filter_vignette,
        "invert": get_filter_invert,
        "saturate": get_filter_saturate,
        "vhs": get_filter_vhs,
        "oldfilm": get_filter_oldfilm,
        "contrast": get_filter_contrast
    }
    return filters_map.get(filter_name, lambda: "")()

async def process_video(input_path, output_path, filter_string, filter_name):
    start_time = time.time()
    print(f"начало обработки: файл={input_path}, фильтр={filter_name}")
    
    try:
        cmd = [
            "ffmpeg", "-i", input_path,
            "-vf", filter_string,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            "-y", output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        duration = time.time() - start_time
        
        if result.returncode != 0:
            error_msg = result.stderr
            print(f"ошибка ffmpeg: {error_msg}")
            return False, f"ошибка обработки: {error_msg[:200]}"
        
        print(f"обработка завершена: длительность={duration:.2f}с, статус=успех")
        return True, duration
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"обработка прервана: длительность={duration:.2f}с, статус=таймаут")
        return False, "превышено время обработки (максимум 10 минут)"
    except Exception as e:
        duration = time.time() - start_time
        print(f"обработка завершена с ошибкой: длительность={duration:.2f}с, ошибка={str(e)}")
        return False, f"неожиданная ошибка: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне видео для обработки")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "справка по использованию бота:\n\n"
        "что делает бот:\n"
        "обрабатывает видео с помощью различных фильтров через ffmpeg\n\n"
        "как пользоваться:\n"
        "1. отправь видео (как обычное видео или документ)\n"
        "2. выбери фильтр из предложенных\n"
        "3. получи обработанное видео\n\n"
        "поддерживаемые форматы:\n"
        "mp4, avi, mov, mkv, webm\n\n"
        "как выбрать фильтр:\n"
        "после загрузки видео появится клавиатура с фильтрами\n"
        "нажми на нужный фильтр для обработки\n\n"
        "команды:\n"
        "/start - начать работу\n"
        "/help - показать эту справку"
    )
    await update.message.reply_text(help_text)

def validate_video(file_path):
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name", 
             "-show_entries", "stream=codec_name", "-of", "json", file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if probe.returncode != 0:
            return False, "не удалось проанализировать видео"
        
        import json
        data = json.loads(probe.stdout)
        
        duration = float(data.get("format", {}).get("duration", 0))
        if duration > 300:
            return False, f"видео слишком длинное ({duration:.1f} сек). максимум 5 минут"
        if duration < 1:
            return False, "видео слишком короткое (меньше 1 секунды)"
        
        format_name = data.get("format", {}).get("format_name", "")
        if not any(fmt in format_name for fmt in ["mp4", "avi", "mov", "matroska", "webm"]):
            return False, f"неподдерживаемый формат контейнера: {format_name}"
        
        streams = data.get("streams", [])
        video_codec = None
        for stream in streams:
            if stream.get("codec_type") == "video":
                video_codec = stream.get("codec_name")
                break
        
        if not video_codec:
            return False, "видео поток не найден"
        
        if video_codec not in ["h264", "h265", "vp8", "vp9", "mpeg4"]:
            return False, f"неподдерживаемый видеокодек: {video_codec}"
        
        return True, "ok"
    except subprocess.TimeoutExpired:
        return False, "превышено время ожидания при анализе видео"
    except Exception as e:
        return False, f"ошибка валидации: {str(e)}"

def get_filters_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("сепия", callback_data="filter_sepia"),
            InlineKeyboardButton("черно-белый", callback_data="filter_bw"),
            InlineKeyboardButton("резкость", callback_data="filter_sharpen")
        ],
        [
            InlineKeyboardButton("блюр", callback_data="filter_blur"),
            InlineKeyboardButton("виньетка", callback_data="filter_vignette"),
            InlineKeyboardButton("инверсия", callback_data="filter_invert")
        ],
        [
            InlineKeyboardButton("насыщенность", callback_data="filter_saturate"),
            InlineKeyboardButton("vhs", callback_data="filter_vhs"),
            InlineKeyboardButton("старая пленка", callback_data="filter_oldfilm")
        ],
        [
            InlineKeyboardButton("контраст", callback_data="filter_contrast")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        file = await context.bot.get_file(update.message.video.file_id)
        file_extension = update.message.video.mime_type.split("/")[-1] if update.message.video.mime_type else "mp4"
        file_id = update.message.video.file_id
    elif update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        file_name = update.message.document.file_name or "video"
        file_extension = file_name.split(".")[-1] if "." in file_name else "mp4"
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("Ошибка: не удалось получить файл")
        return
    
    if file_extension.lower() not in ["mp4", "avi", "mov", "mkv", "webm"]:
        await update.message.reply_text(f"Ошибка: неподдерживаемый формат файла ({file_extension}). Поддерживаются: mp4, avi, mov, mkv, webm")
        return
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_input:
        await file.download_to_drive(temp_input.name)
        is_valid, message = validate_video(temp_input.name)
        os.unlink(temp_input.name)
    
    if not is_valid:
        await update.message.reply_text(f"Ошибка валидации: {message}")
        return
    
    context.user_data["video_file_id"] = file_id
    context.user_data["video_extension"] = file_extension
    
    await update.message.reply_text("Видео получено! Выбери фильтр:", reply_markup=get_filters_keyboard())

async def filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if "video_file_id" not in context.user_data:
        await query.edit_message_text("Ошибка: видео не найдено. Отправь видео заново")
        return
    
    filter_name = query.data.replace("filter_", "")
    filter_string = get_filter_by_name(filter_name)
    
    if not filter_string:
        await query.edit_message_text(f"Ошибка: неизвестный фильтр {filter_name}")
        return
    
    await query.edit_message_text(f"Выбран фильтр: {filter_name}. Обработка начата...")
    
    file_id = context.user_data["video_file_id"]
    file_extension = context.user_data.get("video_extension", "mp4")
    
    file = await context.bot.get_file(file_id)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_input:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_output:
            await file.download_to_drive(temp_input.name)
            
            success, result = await process_video(temp_input.name, temp_output.name, filter_string, filter_name)
            
            os.unlink(temp_input.name)
            
            if success:
                await query.message.reply_video(video=open(temp_output.name, "rb"))
                os.unlink(temp_output.name)
                await query.edit_message_text(f"Готово! Фильтр '{filter_name}' применен. Время обработки: {result:.1f}с")
            else:
                os.unlink(temp_output.name)
                await query.edit_message_text(f"Ошибка обработки: {result}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(CallbackQueryHandler(filter_callback))
    app.run_polling()

if __name__ == "__main__":
    main()
