FROM python:3.10-slim

# تثبيت أداة الصوتيات ffmpeg و curl و ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# تنزيل محرك خادم تيليجرام الرسمي المباشر لدعم الملفات حتى 2000 ميغابايت (2GB)
RUN curl -L -o /usr/local/bin/telegram-bot-api https://github.com/jakbin/telegram-bot-api-binary/releases/download/2026-08-05/telegram-bot-api \
    && chmod +x /usr/local/bin/telegram-bot-api

WORKDIR /app

# تثبيت مكتبات البوت
RUN pip install --no-cache-dir pyTelegramBotAPI SpeechRecognition pydub python-docx deep-translator flask python-dotenv

# نسخ ملفات المشروع
COPY . .

# تشغيل البوت
CMD ["python", "BOT.py"]
