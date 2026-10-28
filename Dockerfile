FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

# تثبيت أداة الصوتيات ffmpeg و curl و ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# تنزيل محرك خادم تيليجرام الرسمي المباشر لدعم الملفات حتى 2000 ميغابايت (2GB) مع حماية ضد فشل التحميل
RUN (curl -fsSL -o /usr/local/bin/telegram-bot-api https://github.com/jakbin/telegram-bot-api-binary/releases/download/2026-08-05/telegram-bot-api && chmod +x /usr/local/bin/telegram-bot-api) || true

WORKDIR /app

# تثبيت متطلبات البوت مع الاستفادة من التخزين المؤقت (Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ ملفات المشروع
COPY . .

# تشغيل البوت
CMD ["python", "BOT.py"]
