FROM python:3.10-slim

# تثبيت أداة الصوتيات ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تثبيت مكتبات البوت
RUN pip install --no-cache-dir pyTelegramBotAPI SpeechRecognition pydub python-docx deep-translator flask python-dotenv

# نسخ ملفات المشروع
COPY . .

# تشغيل البوت
CMD ["python", "BOT.py"]
