import os
import logging
import openai
import uuid
import pydub
import telegram
import gtts
from telegram.ext import filters
import re

AUDIOS_DIR = "audios"
OPENAI_TOKEN = os.getenv("OPENAI_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def create_dir_if_not_exists(dir):
    if (not os.path.exists(dir)):
        os.mkdir(dir)

def generate_unique_name():
    uuid_value = uuid.uuid4()
    return f"{str(uuid_value)}"

def convert_speech_to_text(audio_filepath):
    with open(audio_filepath, "rb") as audio:
        transcript = openai.Audio.transcribe("whisper-1", audio)
        return transcript["text"]

async def download_voice_as_ogg(voice):
    voice_file = await voice.get_file()
    ogg_filepath = os.path.join(AUDIOS_DIR, f"{generate_unique_name()}.ogg")
    await voice_file.download_to_drive(ogg_filepath)
    return ogg_filepath

def convert_ogg_to_mp3(ogg_filepath):
    mp3_filepath = os.path.join(AUDIOS_DIR, f"{generate_unique_name()}.mp3")
    audio = pydub.AudioSegment.from_file(ogg_filepath, format="ogg")
    audio.export(mp3_filepath, format="mp3")
    return mp3_filepath

def generate_response(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": text}
        ]
    )
    answer = response["choices"][0]["message"]["content"]
    return answer

async def handle_text(update: telegram.Update,
                      context: telegram.ext.ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    answer = generate_response(text)
    await update.message.reply_text(answer)

def summarize_transcript(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes texts in Spanish."},
            {"role": "user", "content": f"Organiza las ideas y indica los puntos clave el siguiente texto en español: {text}"}
        ]
    )

    summary = response["choices"][0]["message"]["content"].strip()
    bullet_points = re.split(r'\n+', summary)
    return bullet_points

async def handle_voice(update: telegram.Update,
                       context: telegram.ext.ContextTypes.DEFAULT_TYPE) -> None:
    ogg_filepath = await download_voice_as_ogg(update.message.voice)
    mp3_filepath = convert_ogg_to_mp3(ogg_filepath)
    transcripted_text = convert_speech_to_text(mp3_filepath)
    bullet_points = summarize_transcript(transcripted_text)
    summary_text = "\n".join([f"• {point}" for point in bullet_points])
    await update.message.reply_text(summary_text)
    os.remove(ogg_filepath)
    os.remove(mp3_filepath)

def main() -> None:
    create_dir_if_not_exists(AUDIOS_DIR)

    openai.api_key = OPENAI_TOKEN

    application = telegram.ext.Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(telegram.ext.MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(telegram.ext.MessageHandler(
        filters.VOICE, handle_voice))

    application.run_polling()

if __name__ == "__main__":
    main()
