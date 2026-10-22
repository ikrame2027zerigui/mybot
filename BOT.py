import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BotCommand
import speech_recognition as sr
from pydub import AudioSegment
import os
from datetime import datetime
from deep_translator import GoogleTranslator
import random
from docx import Document  # مكتبة إنشاء ملفات الورد

TOKEN = "8819830801:AAFU1Q5z-pPjnj9K6YW3rcoEHwwH3uoAG3c"

bot = telebot.TeleBot(TOKEN)
recognizer = sr.Recognizer()
translator = GoogleTranslator(source='auto', target='ar')

listening_language = "ar-DZ"
HISTORY_FILE = "bot_history.txt"
USER_SCHEDULES = {} 
USER_QUIZ_STATE = {} 

QUIZ_BANK = [
    {
        "question": "في أصول المراجعة والدراسة، ماذا يُقصد بأهمية التنظيم الذاتي للوقت؟",
        "options": "أ) عشوائية إنجاز المهام.\nب) ترتيب الأولويات لتحقيق أقصى إنتاجية.\nج) تأجيل المهام دون خطة.",
        "answer": "ب"
    },
    {
        "question": "ما هي الخطوة الأولى والأهم عند الاستماع لمحاضرة طويلة بهدف تفريغها؟",
        "options": "أ) البدء بالكتابة فوراً دون استماع.\nب) سماع المقطع كاملاً لفهم الفكرة العامة وتحديد لغة التفريغ.\nج) حذف الصوت مباشرة.",
        "answer": "ب"
    },
    {
        "question": "في أدوات البحث العلمي، ما الفائدة الأساسية من توثيق سجل المحاضرات بانتظام؟",
        "options": "أ) استرجاع المعلومات ومراجعتها بسهولة عند الحاجة.\nب) ملء مساحة التخزين فقط.\nج) زيادة مدة الفيديو.",
        "answer": "أ"
    }
]

bot.set_my_commands([
    BotCommand("start", "تشغيل البوت 🌟"),
    BotCommand("help", "دليل الاستخدام 📚"),
    BotCommand("schedule", "جدول المحاضرات 📅"),
    BotCommand("set_schedule", "تعديل الجدول ✏️"),
    BotCommand("quiz", "سؤال المراجعة 🧠"),
    BotCommand("cancel", "إلغاء العمليات الحالية ❌"),
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
    markup.add(KeyboardButton("🌐 تغيير لغة التفريغ"), KeyboardButton("📅 جدولي الدراسي"), KeyboardButton("❌ إلغاء"))
    return markup

# دالة لتوليد ملف Word منظم وبخط كبير وواضح
def create_word_document(raw_text, user_name, output_filename):
    doc = Document()
    
    # عنوان رئيسي بخط كبير
    title = doc.add_heading(f"مُدَوِّنُ الْإِكْرَامِ - تقرير التفريغ", level=1)
    title.alignment = 1  # توسيط العنوان
    
    # معلومات المستخدم والتاريخ
    doc.add_paragraph(f"👤 الطالبة / المستخدم: {user_name}\n📅 تاريخ التفريغ: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph("--------------------------------------------------")
    
    # عنوان فرعي للمحتوى
    doc.add_heading("📌 محتوى المحاضرة المنظم:", level=2)
    
    cleaned = raw_text.strip()
    words = cleaned.split()
    chunks = []
    current_chunk = []
    
    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= 12:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    for chunk in chunks:
        p = doc.add_paragraph(chunk, style='List Bullet')  # إضافة كعناصر نقاط منظمة وبخط واضح
        
    # فقرة ختامية للملاحظات
    doc.add_heading("💡 أبرز النقاط والملاحظات:", level=2)
    doc.add_paragraph("• تم استخراج النص ومعالجته وتنسيقه آلياً لسهولة المراجعة الدراسية.")
    
    doc.save(output_filename)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    name = message.from_user.first_name or "صديقي"
    banner_text = (
        "╔═════════════════════════╗\n"
        "   🌟 **مُدَوِّنُ الْإِكْرَامِ** 🌟   \n"
        "╚═════════════════════════╝\n\n"
        f"👋 أهلاً بك يا {name} في مساعدك الذكي الشامل للدراسة والمحاضرات!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📚 **مميزات البوت:**\n"
        "• 🎙️ تفريغ وتنظيم التسجيلات في ملفات Word (.docx) بخط واضح.\n"
        "• 🌍 ترجمة النصوص والملفات بأكثر من لغة.\n"
        "• 📅 إدارة الجدول الدراسي والمواعيد بدقة.\n"
        "• 🧠 اختبارات المراجعة الذكية (`/quiz`).\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 *اختر لغة المقطع الصوتي للبدء:*"
    )
    bot.send_message(message.chat.id, banner_text, parse_mode="Markdown", reply_markup=permanent_keyboard())
    bot.send_message(message.chat.id, "اختر لغة التفريغ من القائمة أدناه:", reply_markup=language_menu())

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.send_message(message.chat.id, "📖 أرسل أي تسجيل صوتي أو مرئي، وسيقوم البوت بتفريغه وإرساله لك كملف Word (`.docx`) بخط كبير ومنظم!", reply_markup=permanent_keyboard())

@bot.message_handler(commands=['quiz'])
def start_quiz(message):
    chat_id = message.chat.id
    selected_quiz = random.choice(QUIZ_BANK)
    USER_QUIZ_STATE[chat_id] = selected_quiz["answer"]
    quiz_q = (
        "🧠 **سؤال المراجعة الذكي:**\n\n"
        f"{selected_quiz['question']}\n\n"
        f"{selected_quiz['options']}\n\n"
        "👇 *اكتب حرف الإجابة الصحيحة (أ، ب، أو ج):*"
    )
    bot.send_message(message.chat.id, quiz_q, parse_mode="Markdown", reply_markup=permanent_keyboard())

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    chat_id = message.chat.id
    if chat_id in USER_QUIZ_STATE:
        del USER_QUIZ_STATE[chat_id]
    bot.send_message(message.chat.id, "✅ تم إلغاء العمليات الحالية والعودة للوضع الطبيعي.", reply_markup=permanent_keyboard())

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
                          text=f"✅ تم ضبط لغة التفريغ بنجاح. أرسل الصوت الآن!")

@bot.message_handler(content_types=['text'])
def handle_personalized_text(message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "صديقي"
    text = message.text.strip().lower()
    
    if "إلغاء" in text or text == "cancel":
        cancel_operation(message)
        return

    if chat_id in USER_QUIZ_STATE:
        correct_answer = USER_QUIZ_STATE[chat_id]
        if text in [correct_answer, f"option {correct_answer.lower()}"]:
            bot.reply_to(message, f"🎉 أحسنت يا {user_name}! إجابة صحيحة وصائبة تماماً ({correct_answer}).", reply_markup=permanent_keyboard())
        else:
            bot.reply_to(message, f"❌ مع الأسف يا {user_name}، إجابة خاطئة. الإجابة الصحيحة هي ({correct_answer}).", reply_markup=permanent_keyboard())
        del USER_QUIZ_STATE[chat_id]
        return

    if any(greeting in text for greeting in ["سلام", "السلام عليكم", "مرحباً", "اهلا", "أهلاً", "صباح", "مساء"]):
        bot.reply_to(message, f"وعليكم السلام ورحمة الله وبركاته يا {user_name}! 🌿 أهلاً بك. أنا جاهز لتفريغ محاضراتك وإرسالها كملفات Word منسقة. تفضل بإرسال ما تريد!", reply_markup=permanent_keyboard())
    elif "كيف حالك" in text or "شخبارك" in text:
        bot.reply_to(message, f"أهلاً بك يا {user_name}, أنا أعمل بأفضل حال وجاهز تماماً لخدمتك وتصدير ملفاتك الاحترافية! ✨", reply_markup=permanent_keyboard())
    elif "تغيير لغة" in text or "لغ" in text:
        bot.reply_to(message, f"حسناً يا {user_name}, اختر لغة المقطع من القائمة أدناه:", reply_markup=language_menu())
    elif "جدولي" in text or "جدول" in text:
        show_schedule(message)
    else:
        bot.reply_to(message, f"💬 أهلاً بك يا {user_name}!\nلقد تلقيت رسالتك:\n\n«{message.text}»\n\nأرسل لي أي تسجيل صوتي أو مقطع مرئي وسأتولى تفريغه وتصديره كملف Word فوراً.", reply_markup=permanent_keyboard())

@bot.message_handler(content_types=['voice', 'audio', 'document', 'video', 'video_note'])
def handle_smart_media_to_word(message):
    global listening_language
    user_name = message.from_user.first_name or "صديقي"
    working_msg = None
    temp_input = "temp_smart_media.tmp"
    output_docx = f"ملاحظات_{user_name}_{datetime.now().strftime('%H%M%S')}.docx"
    
    try:
        is_short_voice = (message.content_type == 'voice')
        
        if is_short_voice:
            working_msg = bot.reply_to(message, f"🎙️ حسناً يا {user_name}، جاري تفريغ تسجيلك الصوتي القصير...", reply_markup=permanent_keyboard())
            file_id = message.voice.file_id
            media_name = f"تسجيل_{user_name}"
        else:
            working_msg = bot.reply_to(message, f"⏳ يا {user_name}، جاري استلام ملفك ومعالجته وتقسيمه وإعداده كملف Word احترافي...", reply_markup=permanent_keyboard())
            if message.content_type == 'audio':
                file_id = message.audio.file_id
                media_name = message.audio.file_name if message.audio.file_name else "ملف_صوتي"
            elif message.content_type in ['video', 'video_note']:
                file_id = message.video.file_id if message.content_type == 'video' else message.video_note.file_id
                media_name = "مقطع_مرئي"
            elif message.content_type == 'document':
                file_id = message.document.file_id
                media_name = message.document.file_name if message.document.file_name else "مستند_صوتي"
            else:
                return

        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(temp_input, 'wb') as f:
            f.write(downloaded_file)
            
        audio = AudioSegment.from_file(temp_input)
        audio = audio.set_channels(1).set_frame_rate(16000)
        
        raw_text = ""
        
        if is_short_voice and len(audio) < 60000:
            wav_output = "short_direct.wav"
            audio.export(wav_output, format="wav")
            
            with sr.AudioFile(wav_output) as source:
                audio_data = recognizer.record(source)
                raw_text = recognizer.recognize_google(audio_data, language=listening_language)
            
            if os.path.exists(wav_output):
                os.remove(wav_output)
        else:
            chunk_length_ms = 30 * 1000 
            chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
            
            for idx, chunk in enumerate(chunks):
                chunk_filename = f"chunk_{idx}.wav"
                chunk.export(chunk_filename, format="wav")
                
                with sr.AudioFile(chunk_filename) as source:
                    audio_data = recognizer.record(source)
                    try:
                        part_text = recognizer.recognize_google(audio_data, language=listening_language)
                        raw_text += part_text + " "
                    except sr.UnknownValueError:
                        pass
                
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)
                    
        if raw_text.strip():
            save_to_history(media_name)
            bot.delete_message(message.chat.id, working_msg.message_id)
            
            # إنشاء ملف الورد وتنسيقه بخطوط واضحة
            create_word_document(raw_text, user_name, output_docx)
                
            # إرسال مستند الورد إلى المستخدم في تيليجرام
            with open(output_docx, "rb") as doc_to_send:
                bot.send_document(
                    message.chat.id, 
                    doc_to_send, 
                    caption=f"📄 إليك ملف Word المنظم بخط واضح يا {user_name}، جاهز للحفظ والمراجعة! 🌿", 
                    reply_markup=permanent_keyboard()
                )
        else:
            bot.edit_message_text(f"⚠️ عذراً يا {user_name}، لم يتم العثور على كلام واضح داخل الملف.", chat_id=message.chat.id, message_id=working_msg.message_id)
                
    except Exception as e:
        if working_msg:
            try:
                bot.delete_message(message.chat.id, working_msg.message_id)
            except:
                pass
        bot.reply_to(message, f"❌ عذراً يا {user_name}، حدث خطأ أثناء معالجة الملف وتصديره بصيغة Word.", reply_markup=permanent_keyboard())
        print("Word Export Error:", e)
        
    finally:
        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(output_docx):
            os.remove(output_docx)

print("✅ بوت 'مدون الإكرام' يعمل بنظام تصدير مستندات Word المنظمة وذات الخط الواضح!")
bot.infinity_polling()
