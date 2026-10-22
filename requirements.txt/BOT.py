import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BotCommand
import speech_recognition as sr
from pydub import AudioSegment
import os
from datetime import datetime
from deep_translator import GoogleTranslator

TOKEN = "8819830801:AAFU1Q5z-pPjnj9K6YW3rcoEHwwH3uoAG3c"

bot = telebot.TeleBot(TOKEN)
recognizer = sr.Recognizer()
translator = GoogleTranslator(source='auto', target='ar')

listening_language = "ar-DZ"
HISTORY_FILE = "bot_history.txt"
USER_SCHEDULES = {} 
USER_QUIZ_STATE = {} 

bot.set_my_commands([
    BotCommand("start", "تشغيل البوت 🌟"),
    BotCommand("help", "دليل الاستخدام 📚"),
    BotCommand("schedule", "جدول المحاضرات 📅"),
    BotCommand("set_schedule", "تعديل الجدول ✏️"),
    BotCommand("quiz", "سؤال المراجعة 🧠"),
    BotCommand("history", "السجل 📂")
])

def save_to_history(filename_desc):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"📁 {filename_desc} — ⏱️ التاريخ: {current_time}\n")

def language_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("العربية 🇩🇿", callback_data="lang_ar-DZ"),
        InlineKeyboardButton("الروسية 🇷🇺", callback_data="lang_ru-RU"),
        InlineKeyboardButton("الفرنسية 🇫🇷", callback_data="lang_fr-FR"),
        InlineKeyboardButton("الانكليزية 🇺🇸", callback_data="lang_en-US")
    )
    return markup

def permanent_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🌐 تغيير لغة التفريغ"), KeyboardButton("📅 جدولي الدراسي"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    name = message.from_user.first_name
    
    banner_text = (
        "╔═════════════════════════╗\n"
        "   🌟 **مُدَوِّنُ الْإِكْرَامِ** 🌟   \n"
        "╚═════════════════════════╝\n\n"
        f"👋 أهلاً بك يا {name or 'عزيزي المستخدم'} في مساعدك الذكي الشامل للدراسة والمحاضرات!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📚 **مميزات البوت:**\n"
        "• 🎙️ تفريغ التسجيلات والمحاضرات الصوتية فوراً.\n"
        "• 🌍 ترجمة النصوص والملفات بأكثر من لغة.\n"
        "• 📅 إدارة الجدول الدراسي والمواعيد بدقة.\n"
        "• 🧠 اختبارات المراجعة الذكية (`/quiz`).\n"
        "• 📂 حفظ وتوثيق سجل المحاضرات.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 *اختر لغة المقطع الصوتي للبدء:*"
    )
    
    bot.send_message(message.chat.id, banner_text, parse_mode="Markdown", reply_markup=permanent_keyboard())
    bot.send_message(message.chat.id, "اختر لغة التفريغ من القائمة أدناه:", reply_markup=language_menu())

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.send_message(message.chat.id, "📖 أرسل أي تسجيل صوتي أو ملاحظة صوتية لتفريغها فوراً!", reply_markup=permanent_keyboard())

@bot.message_handler(commands=['quiz'])
def start_quiz(message):
    chat_id = message.chat.id
    USER_QUIZ_STATE[chat_id] = True
    quiz_q = (
        "🧠 **سؤال المراجعة السريعة:**\n\n"
        "في أصول المراجعة والدراسة، ماذا يُقصد بأهمية التنظيم الذاتي للوقت؟\n\n"
        "أ) عشوائية إنجاز المهام.\n"
        "ب) ترتيب الأولويات لتحقيق أقصى إنتاجية.\n"
        "ج) تأجيل المهام دون خطة.\n\n"
        "👇 *اكتب حرف الإجابة (أ، ب، أو ج):*"
    )
    bot.send_message(message.chat.id, quiz_q, parse_mode="Markdown", reply_markup=permanent_keyboard())

@bot.message_handler(commands=['set_schedule'])
def set_schedule_start(message):
    bot.send_message(message.chat.id, "✏️ أرسل جدولك الدراسي كاملاً في رسالة واحدة:", reply_markup=permanent_keyboard())
    bot.register_next_step_handler(message, lambda m: USER_SCHEDULES.update({m.chat.id: m.text}) and bot.reply_to(m, "✅ تم حفظ الجدول بنجاح!"))

@bot.message_handler(commands=['schedule'])
def show_schedule(message):
    schedule = USER_SCHEDULES.get(message.chat.id, "📅 لم تقم بإدخال جدولك بعد. استخدم `/set_schedule` لإدخاله.")
    bot.send_message(message.chat.id, schedule, parse_mode="Markdown", reply_markup=permanent_keyboard())

@bot.message_handler(commands=['history'])
def show_history(message):
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        bot.send_message(message.chat.id, f"📂 **السجل:**\n\n{content}" if content.strip() else "📂 السجل فارغ.", parse_mode="Markdown", reply_markup=permanent_keyboard())
    else:
        bot.send_message(message.chat.id, "📂 لا يوجد سجل بعد.", reply_markup=permanent_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def set_language_callback(call):
    global listening_language
    listening_language = call.data.split('_')[1]
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                          text=f"✅ تم ضبط لغة التفريغ بنجاح. أرسل المقطع الآن!")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    if chat_id in USER_QUIZ_STATE:
        if text in ['ب', 'option b']:
            bot.reply_to(message, "🎉 إجابة صحيحة وصائبة تماماً!", reply_markup=permanent_keyboard())
        else:
            bot.reply_to(message, "❌ إجابة خاطئة. الإجابة الصحيحة هي (ب).", reply_markup=permanent_keyboard())
        del USER_QUIZ_STATE[chat_id]
        return

    if "تغيير لغة" in text or "لغ" in text:
        bot.reply_to(message, "👇 اختر لغة المقطع:", reply_markup=language_menu())
    elif "جدولي" in text or "جدول" in text:
        show_schedule(message)
    else:
        try:
            translated = translator.translate(message.text)
            bot.reply_to(message, f"🌍 الترجمة:\n\n{translated}", reply_markup=permanent_keyboard())
        except Exception:
            bot.reply_to(message, "⚠️ تعذرت الترجمة.", reply_markup=permanent_keyboard())

@bot.message_handler(content_types=['voice', 'audio', 'document', 'video', 'video_note'])
def handle_all_media(message):
    global listening_language
    try:
        media_name = message.document.file_name if message.content_type == 'document' and message.document.file_name else "تسجيل_صوتي"
        
        if message.content_type in ['voice', 'audio']:
            file_id = message.voice.file_id if message.content_type == 'voice' else message.audio.file_id
        elif message.content_type in ['video', 'video_note']:
            file_id = message.video.file_id if message.content_type == 'video' else message.video_note.file_id
        elif message.content_type == 'document':
            file_id = message.document.file_id
            
        working_msg = bot.reply_to(message, "🎙️ جاري الاستماع والتفريغ...", reply_markup=permanent_keyboard())
        
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open("temp_media.tmp", 'wb') as new_file:
            new_file.write(downloaded_file)
            
        audio = AudioSegment.from_file("temp_media.tmp").set_channels(1).set_frame_rate(16000)
        audio.export("short_audio.wav", format="wav")
        
        with sr.AudioFile("short_audio.wav") as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data, language=listening_language)
                save_to_history(media_name)
                
                bot.delete_message(message.chat.id, working_msg.message_id)
                bot.send_message(message.chat.id, f"📝 **التفريغ المباشر:**\n\n{text}", parse_mode="Markdown", reply_markup=permanent_keyboard())
            except sr.UnknownValueError:
                bot.edit_message_text("⚠️ عذراً، لم أتمكن من سماع الصوت بوضوح، يرجى إعادة المحاولة.", chat_id=message.chat.id, message_id=working_msg.message_id)
                
        if os.path.exists("short_audio.wav"):
            os.remove("short_audio.wav")
        if os.path.exists("temp_media.tmp"):
            os.remove("temp_media.tmp")
                
    except Exception as e:
        bot.reply_to(message, "❌ حدث خطأ في معالجة الملف الصوتي.", reply_markup=permanent_keyboard())
        print("Error:", e)

print("✅ بوت 'مدون الإكرام' يعمل كأداة شاملة ومثالية!")
bot.infinity_polling()
