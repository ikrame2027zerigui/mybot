import os
import json
import glob
import time
import random
import subprocess
import re
from datetime import datetime
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
import speech_recognition as sr
from deep_translator import GoogleTranslator
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
import requests

from keep_alive import keep_alive

# تحميل متغيرات البيئة من ملف .env
if load_dotenv:
    load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    import base64
    _ENC = "ODgxOTgzMDgwMTpBQUVCb3kwWnBpWG84NVgyZXR0XzY0b3E0cjg1RHA1cEZBZw=="
    TOKEN = base64.b64decode(_ENC).decode("utf-8")

TG_API_ID = int(os.environ.get("TG_API_ID", 35521120))
TG_API_HASH = os.environ.get("TG_API_HASH", "149519bc317198bd16527e19fd4bada1")

TELETHON_MEDIA_CACHE = {}
telethon_client = None

def start_telethon_listener():
    global telethon_client
    try:
        import threading
        from telethon.sync import TelegramClient, events
        client = TelegramClient("bot_mtproto_worker", TG_API_ID, TG_API_HASH)
        
        @client.on(events.NewMessage)
        def handle_mtproto_event(event):
            try:
                if event.message and event.message.media:
                    TELETHON_MEDIA_CACHE[f"{event.chat_id}_{event.id}"] = event.message
                    TELETHON_MEDIA_CACHE[event.chat_id] = event.message
            except Exception:
                pass
                
        client.start(bot_token=TOKEN)
        telethon_client = client
        print("✅ محرك MTProto المباشر متصل ويستمع للملفات الكبيرة بنجاح!")
        client.run_until_disconnected()
    except Exception as e:
        print("Telethon worker error:", e)

import threading
threading.Thread(target=start_telethon_listener, daemon=True).start()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

bot = telebot.TeleBot(TOKEN)
recognizer = sr.Recognizer()
translator = GoogleTranslator(source='auto', target='ar')

listening_language = "ar-DZ"

ADMIN_ID = 6619712661
USERS_DB_FILE = "bot_users.json"
ADMIN_BROADCAST_STATE = {}

def load_users():
    if os.path.exists(USERS_DB_FILE):
        try:
            with open(USERS_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_users(users):
    try:
        with open(USERS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save users error:", e)

def register_or_update_user(from_user, is_transcription=False):
    if not from_user:
        return
    user_id = str(from_user.id)
    users = load_users()
    is_new = user_id not in users
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    first_name = from_user.first_name or "بدون اسم"
    last_name = from_user.last_name or ""
    username = from_user.username or "بدون يوزرنيم"
    
    if is_new:
        users[user_id] = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "joined_at": now_str,
            "last_active": now_str,
            "transcriptions_count": 1 if is_transcription else 0
        }
        save_users(users)
        
        # إشعار فوري للمديرة (إكرام) عند دخول أي طالب جديد
        try:
            total_students = len(users)
            user_link = f"@{username}" if username != "بدون يوزرنيم" else f"{first_name}"
            alert_msg = (
                f"🔔 **طالب(ة) جديد(ة) انضم إلى بوت مدون الإكرام!** 🌿\n\n"
                f"👤 **الاسم:** {first_name} {last_name}\n"
                f"🆔 **الحساب:** {user_link}\n"
                f"🔢 **معرف التيليجرام:** `{user_id}`\n"
                f"📅 **التاريخ:** `{now_str}`\n\n"
                f"📊 **إجمالي الطلاب المسجلين بالبوت:** `{total_students}` طالب(ة)"
            )
            bot.send_message(ADMIN_ID, alert_msg, parse_mode="Markdown")
        except Exception as e:
            print("Admin new user alert error:", e)
    else:
        users[user_id]["first_name"] = first_name
        users[user_id]["last_name"] = last_name
        users[user_id]["username"] = username
        users[user_id]["last_active"] = now_str
        if is_transcription:
            users[user_id]["transcriptions_count"] = users[user_id].get("transcriptions_count", 0) + 1
        save_users(users)

HISTORY_FILE = "bot_history.txt"
USER_SCHEDULES = {}
USER_QUIZ_STATE = {}

# ==========================================
# 📚 بنك أسئلة واختبارات العلوم الإسلامية التفاعلي
# ==========================================
ISLAMIC_QUIZ_BANK = [
    {
        "category": "أصول الفقه",
        "question": "ما هو الدليل الشرعي الرابع المتفق عليه عند جمهور الأصوليين بعد الكتاب والسنة والإجماع؟",
        "options": ["أ) الاستحسان", "ب) القياس", "ج) المصالح المرسلة"],
        "answer": "ب",
        "explanation": "الأدلة المتفق عليها عند جمهور الأمة أربعة: القرآن الكريم، السنة النبوية، الإجماع، والقياس."
    },
    {
        "category": "القواعد الفقهية",
        "question": "ما هي القاعدة الفقهية التي تفيد بأن 'الأصل بقاء ما كان على ما كان حتى يثبت العكس'؟",
        "options": ["أ) المشقة تجلب التيسير", "ب) اليقين لا يزول بالشك", "ج) الأمور بمقاصدها"],
        "answer": "ب",
        "explanation": "قاعدة 'اليقين لا يزول بالشك' ينبني عليها استصحاب الأصل وبقاء ما كان حتى يرد الدليل المغير."
    },
    {
        "category": "علوم الحديث",
        "question": "ما يُعرّف بأنه: 'ما سقط من مبتدأ إسناده راوٍ فأكثر على التوالي' يسمى في المصطلح:",
        "options": ["أ) الحديث المعلق", "ب) الحديث المعضل", "ج) الحديث المرسل"],
        "answer": "أ",
        "explanation": "الحديث المعلق هو ما حُذف من أول إسناده راوٍ فأكثر، ولو إلى آخر الإسناد."
    },
    {
        "category": "علوم الحديث",
        "question": "الحديث الذي رواه جمعٌ تحيل العادة تواطؤهم على الكذب عن مثلهم من البداية إلى المنتهى يسمى:",
        "options": ["أ) الحديث المشهور", "ب) الحديث المتواتر", "ج) الحديث العزيز"],
        "answer": "ب",
        "explanation": "الحديث المتواتر يفيد العلم اليقيني القطعي، وهو ما نقله جمع عن جمع يؤمن تواطؤهم على الكذب."
    },
    {
        "category": "أصول الفقه",
        "question": "في مباحث دلالات الألفاظ، اللفظ الذي يحتمل معنيين أو أكثر على السواء يسمى:",
        "options": ["أ) المشترك", "ب) الظاهر", "ج) النص"],
        "answer": "أ",
        "explanation": "اللفظ المشترك مثل كلمة (القرء) التي تحتمل الحيض أو الطهر."
    },
    {
        "category": "علوم القرآن",
        "question": "أهم ضابط في التفريق بين السور المكية والمدنية عند جمهور العلماء يعتمد على:",
        "options": ["أ) مكان النزول بمكة أو المدينة", "ب) وقت النزول قبل الهجرة أو بعدها", "ج) مخاطبة أهل مكة أو أهل المدينة"],
        "answer": "ب",
        "explanation": "الرأي الراجح: المكي ما نزل قبل الهجرة ولو بغير مكة، والمدني ما نزل بعد الهجرة ولو بمكة."
    },
    {
        "category": "مقاصد الشريعة",
        "question": "الضروريات الخمس الكبرى التي جاءت الشريعة لحفظها هي:",
        "options": ["أ) الدين، النفس، العقل، النسل/العرض، المال", "ب) العبادة، المعاملة، الأخلاق، العقيدة، القضاء", "ج) العلم، العمل، الإيمان، الإحسان، الدعوة"],
        "answer": "أ",
        "explanation": "الكليات الخمس الضرورية المتفق عليها هي: حفظ الدين، النفس، العقل، النسل، والمال."
    },
    {
        "category": "الفقه وأصوله",
        "question": "إلحاق واقعة لا نص على حكمها بواقعة ورد نص بحكمها لاشتراكهما في العلة يسمى:",
        "options": ["أ) الإجماع", "ب) الاستصحاب", "ج) القياس"],
        "answer": "ج",
        "explanation": "أركان القياس أربعة: الأصل، الفرع، حكم الأصل، والعلة الجامعة."
    }
]

# ==========================================
# 🧠 محرك المعارف والبحوث للعلوم الإسلامية
# ==========================================
ISLAMIC_KNOWLEDGE_BASE = {
    "قواعد فقهية": (
        "📖 **القواعد الفقهية الخمس الكبرى:**\n\n"
        "1️⃣ **الأمور بمقاصدها:** مستندة لحديث (إنما الأعمال بالنيات)، فالحكم يدور مع نية المكلف.\n"
        "2️⃣ **اليقين لا يزول بالشك:** ما ثبت بيقين لا يرتفع بظن عارض، ومنها استصحاب الأصل.\n"
        "3️⃣ **المشقة تجلب التيسير:** وتنبني عليها رخص الشريعة عند الأعذار والسفر والمرض.\n"
        "4️⃣ **الضرر يُزال:** مستندة لحديث (لا ضرر ولا ضرار)، فتدفع المفاسد وتمنع الأضرار.\n"
        "5️⃣ **العادة مُحكَّمة:** العرف الصحيح الذي لا يصادم نصاً معتبر شرعاً في الأحكام والمعاملات."
    ),
    "أصول الفقه": (
        "📚 **موجز علم أصول الفقه وأدلته:**\n\n"
        "• **التعريف:** العلم بالقواعد التي يتوصل بها المجتهد إلى استنباط الأحكام الشرعية العملية من أدلتها التفصيلية.\n"
        "• **الأدلة المتفق عليها:** القرآن الكريم، السنة النبوية، الإجماع، القياس.\n"
        "• **الأدلة المختلف فيها:** الاستحسان، المصالح المرسلة، الاستصحاب، العرف، سد الذرائع، شرع من قبلنا، قول الصحابي.\n"
        "• **ثمرة العلم:** ضبط الفهم الفقهي وتجنب الخبط والاجتهاد بغير علم."
    ),
    "شروط الحديث الصحيح": (
        "🔍 **شروط الحديث الصحيح لذاته الخمسة:**\n\n"
        "1. **اتصال السند:** أن يسمع كل راوٍ ممن فوقه دون انقطاع.\n"
        "2. **عدالة الرواة:** الاستقامة في الدين والأخلاق والسلامة من الفسق وخوارم المروءة.\n"
        "3. **تمام الضبط:** حفظ الراوي وإتقانه لما يرويه صدراً وكتاباً.\n"
        "4. **السلامة من الشذوذ:** ألا يخالف الراوي الثقة من هو أوثق منه.\n"
        "5. **السلامة من العلة القادحة:** خلوه من أسباب خفية تقدح في صحته مع أن الظاهر السلامة."
    ),
    "مقاصد الشريعة": (
        "🎯 **مقاصد الشريعة الإسلامية الكبرى:**\n\n"
        "تنقسم مصالح الخلق إلى ثلاث مراتب:\n"
        "1. **الضروريات:** الكليات الخمس (حفظ الدين، النفس، العقل، النسل، المال).\n"
        "2. **الحاجيات:** ما يحتاجه الناس لرفع الحرج والمشقة كالإجارات والرخص الشرعية.\n"
        "3. **التحسينيات:** الأخذ بمحاسن العادات ومكارم الأخلاق كالطهارة والستر وآداب الأكل."
    ),
    "القياس": (
        "⚖️ **مبحث القياس في أصول الفقه:**\n\n"
        "• **تعريفه:** مساواة فرع بأصل في علة حكمه الشرعي.\n"
        "• **أركانه الأربعة:**\n"
        "   1. **الأصل (المَقيس عليه):** الواقعة الثابت حكمها بنص أو إجماع.\n"
        "   2. **الفرع (المَقيس):** الواقعة الجديدة المراد معرفة حكمها.\n"
        "   3. **حكم الأصل:** الحكم الشرعي الثابت للأصل.\n"
        "   4. **العِلّة:** الوصف المشترك الجامع بين الأصل والفرع الذي لأجله شُرع الحكم."
    )
}

# ==========================================
# 🤖 استعلام الذكاء الاصطناعي (Gemini أو المحرك المدمج)
# ==========================================
def ask_ai_study_assistant(query, user_name="الطالب"):
    query_clean = query.strip().lower()
    
    # 1. إذا توفر مفتاح Gemini API، نستخدم الذكاء التوليدي المباشر
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            prompt_text = (
                f"أنت مساعد أكاديمي متخصص في الشريعة والعلوم الإسلامية لطلبة الجامعة في بوت 'مدون الإكرام'. "
                f"أجب على الطالب/الطالبة ({user_name}) بأسلوب علمي رصين وميسر وموثق مع تنظيم العناوين والنقاط:\n\n{query}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt_text}]}]
            }
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
        except Exception as e:
            print("Gemini API error:", e)

    # 2. البحث في المحرك المعرفي الإسلامي المحلي
    for key, content in ISLAMIC_KNOWLEDGE_BASE.items():
        if key in query_clean:
            return f"📚 **إفادة أكاديمية في العلوم الإسلامية يا {user_name}:**\n\n" + content
            
    if any(w in query_clean for w in ["حديث", "صحيح", "سند", "إسناد", "رواية"]):
        return ISLAMIC_KNOWLEDGE_BASE["شروط الحديث الصحيح"]
    if any(w in query_clean for w in ["قاعدة", "قواعد", "أمور بمقاصدها", "يقين"]):
        return ISLAMIC_KNOWLEDGE_BASE["قواعد فقهية"]
    if any(w in query_clean for w in ["أصول", "دليل", "أدلة", "استحسان", "إجماع"]):
        return ISLAMIC_KNOWLEDGE_BASE["أصول الفقه"]
    if any(w in query_clean for w in ["قياس", "أركان القياس", "علة"]):
        return ISLAMIC_KNOWLEDGE_BASE["القياس"]
    if any(w in query_clean for w in ["مقاصد", "ضروريات", "حاجيات"]):
        return ISLAMIC_KNOWLEDGE_BASE["مقاصد الشريعة"]

    # رد توجيهي ذكي ومشجع
    return (
        f"🌿 أهلاً بك يا {user_name} في ركن المذاكرة والعلوم الشرعية!\n\n"
        f"لقد استلمت استفسارك:\n«{query}»\n\n"
        "💡 **يمكنك استكشاف مباحث العلوم الإسلامية بكتابة كلمات مثل:**\n"
        "• *'القواعد الفقهية'*\n"
        "• *'شروط الحديث الصحيح'*\n"
        "• *'أصول الفقه والأدلة'*\n"
        "• *'أركان القياس'*\n"
        "• *'مقاصد الشريعة'*\n\n"
        "أو أرسل تسجيل المحاضرة وسأتولى تفريغها وتنظيمها في ملف Word أنيق فوراً!"
    )

# ==========================================
# 🎛️ القوائم ولوحات التحكم
# ==========================================
bot.set_my_commands([
    BotCommand("start", "تشغيل البوت 🌟"),
    BotCommand("help", "دليل الاستخدام 📚"),
    BotCommand("quiz", "مسابقة العلوم الإسلامية 🧠"),
    BotCommand("summary", "دليل المذاكرة السريعة 📝"),
    BotCommand("schedule", "جدول المحاضرات 📅"),
    BotCommand("set_schedule", "تعديل الجدول ✏️"),
    BotCommand("cancel", "إلغاء العمليات الحالية ❌"),
    BotCommand("history", "سجل الملفات 📂")
])

def permanent_keyboard(user_id=None):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🎙️ أرسل تسجيلاً للتفريغ"), KeyboardButton("🧠 مسابقة العلوم الإسلامية"))
    markup.row(KeyboardButton("📚 مساعدة وأسئلة دراسية"), KeyboardButton("📅 جدولي الدراسي"))
    markup.row(KeyboardButton("🌐 تغيير لغة التفريغ"), KeyboardButton("❌ إلغاء"))
    if user_id == ADMIN_ID or str(user_id) == str(ADMIN_ID):
        markup.row(KeyboardButton("👑 لوحة تحكم الإدارة والمطورة"))
    return markup

def admin_panel_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
        InlineKeyboardButton("👥 قائمة الطلاب المسجلين", callback_data="admin_users"),
        InlineKeyboardButton("📁 تحميل تقرير الطلاب (.txt)", callback_data="admin_export"),
        InlineKeyboardButton("📢 إذاعة رسالة للجميع", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔄 تحديث وحالة السيرفر", callback_data="admin_status")
    )
    return markup

def language_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("العربية (الجزائر) 🇩🇿", callback_data="lang_ar-DZ"),
        InlineKeyboardButton("العربية الفصحى 🇸🇦", callback_data="lang_ar-SA"),
        InlineKeyboardButton("الروسية 🇷🇺", callback_data="lang_ru-RU"),
        InlineKeyboardButton("الفرنسية 🇫🇷", callback_data="lang_fr-FR"),
        InlineKeyboardButton("الانكليزية 🇺🇸", callback_data="lang_en-US")
    )
    return markup

def save_to_history(filename_desc):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"📁 {filename_desc} — ⏱️ التاريخ: {current_time}\n")

# ==========================================
# 📄 توليد مستند Word والملف النصي الأكاديمي
# ==========================================
def create_text_document(raw_text, user_name, output_filename):
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        "╔═════════════════════════════════════════════════════╗",
        "   🌟 مُدَوِّنُ الْإِكْرَامِ — تفريغ وتوثيق المحاضرة 🌟   ",
        "╚═════════════════════════════════════════════════════╝",
        "",
        f"👤 الطالب(ة): {user_name}",
        f"📅 التاريخ: {dt_str}",
        "──────────────────────────────────────────────────",
        "",
        "📌 نص المحاضرة الكامل المنظم:",
        "",
        raw_text.strip(),
        "",
        "──────────────────────────────────────────────────",
        "✨ تم التفريغ والتنسيق آلياً عبر بوت 'مدون الإكرام' 🌿"
    ]
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def create_word_document(raw_text, user_name, output_filename):
    doc = Document()
    
    # ضبط هوامش الصفحة (1 بوصة من كل جهة)
    for s in doc.sections:
        s.top_margin = Inches(1)
        s.bottom_margin = Inches(1)
        s.left_margin = Inches(1)
        s.right_margin = Inches(1)
        
    # عنوان رئيسي بخط كبير ومميز
    title = doc.add_heading("مُدَوِّنُ الْإِكْرَامِ — تقرير وتفريغ المحاضرة الأكاديمية", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # صندوق بيانات المحاضرة
    info_p = doc.add_paragraph()
    info_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    meta_lines = [
        f"👤 الطالب(ة): {user_name}",
        f"📅 تاريخ التفريغ: {dt_str}",
        "🏛️ التخصص: كلية العلوم الإسلامية والدراسات الجامعية",
        "──────────────────────────────────────────────────"
    ]
    run_info = info_p.add_run("\n".join(meta_lines))
    run_info.font.size = Pt(11)
    run_info.font.color.rgb = RGBColor(90, 90, 90)

    # تقسيم النص إلى فقرات متماسكة سردية كاملة
    words = raw_text.strip().split()
    paragraph_chunks = []
    temp_chunk = []
    
    for word in words:
        temp_chunk.append(word)
        if len(temp_chunk) >= 50 and any(p in word for p in ['؛', '،', '.', 'وبعد', 'المسألة', 'الحكم', 'العلماء', 'ذلك', 'تعالى', 'الله']):
            paragraph_chunks.append(" ".join(temp_chunk))
            temp_chunk = []
        elif len(temp_chunk) >= 70:
            paragraph_chunks.append(" ".join(temp_chunk))
            temp_chunk = []
    if temp_chunk:
        paragraph_chunks.append(" ".join(temp_chunk))

    # القسم الأول: محتوى وتفريغ المحاضرة الكامل
    h2 = doc.add_heading("📌 نص المحاضرة الكامل ومحاورها المنظمة:", level=2)
    h2.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # تقسيم المحاضرة إلى محاور رئيسية كل بضع فقرات
    section_titles = [
        "المحور الأول: الاستفتاح والتمهيد للموضوع",
        "المحور الثاني: عرض المسائل والأدلة والأصول المقررة",
        "المحور الثالث: التفصيل والشرح والضوابط العلمية",
        "المحور الرابع: الفروع والتطبيقات المعاصرة",
        "المحور الخامس: الخاتمة وأهم النتائج"
    ]
    
    sec_idx = 0
    for idx, p_text in enumerate(paragraph_chunks):
        if idx % 3 == 0 and sec_idx < len(section_titles) and len(paragraph_chunks) > 4:
            sec_h = doc.add_heading(f"🔸 {section_titles[sec_idx]}:", level=3)
            sec_h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            sec_idx += 1
            
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.line_spacing = 1.25
        run = p.add_run(p_text.strip() + "؛")
        run.font.size = Pt(14)
        run.font.name = "Arial"

    # القسم الثاني: أهم الفوائد والمسائل المستخلصة
    doc.add_paragraph()
    h_summary = doc.add_heading("💡 أبرز الفوائد والمسائل المستخلصة من المحاضرة:", level=2)
    h_summary.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    key_sentences = [p for p in paragraph_chunks if any(k in p for k in ["أصول", "حكم", "قاعدة", "دليل", "علة", "شرط", "سبب", "قول", "مسألة", "القياس", "الشريعة", "صلاة", "واجب"])]
    if not key_sentences:
        key_sentences = paragraph_chunks[:3]
    
    for point in key_sentences[:5]:
        short_point = " ".join(point.split()[:25]) + "..."
        bullet = doc.add_paragraph(style='List Bullet')
        bullet.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = bullet.add_run(f"مسألة/فائدة: {short_point}")
        r.font.size = Pt(13)

    # القسم الثالث: أسئلة مقترحة للمراجعة والامتحان
    h_quiz = doc.add_heading("❓ أسئلة مقترحة للمراجعة الذاتية ومذاكرة الامتحان:", level=2)
    h_quiz.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    sample_questions = [
        "س1: ما هو المحور الرئيسي والقضية المركزية التي دارت حولها هذه المحاضرة؟",
        "س2: استخرج أهم المصطلحات العلمية والضوابط التي ذكرها الأستاذ في الشرح.",
        "س3: كيف يمكن الاستدلال والتطبيق العملي للمسائل المذكورة في المحاضرة؟"
    ]
    for q in sample_questions:
        q_p = doc.add_paragraph(style='List Bullet')
        q_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        q_run = q_p.add_run(q)
        q_run.font.size = Pt(13)

    # تذييل ختامي
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("\n✨ تم التفريغ والتنسيق آلياً عبر بوت 'مدون الإكرام' — عِلماً نافعاً وعملاً متقبلاً 🌿")
    footer_run.font.size = Pt(11)
    footer_run.font.italic = True
    footer_run.font.color.rgb = RGBColor(120, 120, 120)

    doc.save(output_filename)

# ==========================================
# 🧠 المصحح الإملائي الذكي للغة العربية والتاء المربوطة
# ==========================================
HA_STRICT = {
    'الله', 'إله', 'اله', 'وجه', 'شبه', 'فقه', 'مياه', 'جاه', 'منبه', 'سفيه',
    'نزيه', 'مكروه', 'مشبوه', 'اتجاه', 'اشتباه', 'تشابه', 'جباه', 'أفواه', 'افواه',
    'توجيه', 'تنبيه', 'فقيه', 'واله', 'معتوه', 'عاه', 'شائه', 'تائه', 'متاه',
    'هذه', 'عنه', 'منه', 'فيه', 'إليه', 'اليه', 'عليه', 'لديه', 'به', 'له',
    'إياه', 'اياه', 'دونه', 'حوله', 'بينه', 'معه', 'وراءه', 'أمامه', 'امامه',
    'فوقه', 'تحته', 'بعده', 'قبله', 'خلاله', 'عبره', 'ضده', 'نحوه', 'عنده',
    'يشبه', 'ينبه', 'يتوجه', 'يفقه', 'كره', 'تاه', 'نزه'
}

COMMON_FEMININE_ROOTS = {
    'محاضره': 'محاضرة', 'جامعه': 'جامعة', 'كليه': 'كلية', 'مدرسه': 'مدرسة', 'شريعه': 'شريعة',
    'اسلاميه': 'إسلامية', 'فقهيه': 'فقهية', 'علميه': 'علمية', 'جامعيه': 'جامعية',
    'اهميه': 'أهمية', 'قيمه': 'قيمة', 'قييمه': 'قيمة', 'مساله': 'مسألة', 'دقيقه': 'دقيقة',
    'صلاه': 'صلاة', 'زكاه': 'زكاة', 'حياه': 'حياة', 'وفاه': 'وفاة', 'نجاه': 'نجاة',
    'قراءه': 'قراءة', 'متانيه': 'متأنية', 'شبهه': 'شبهة', 'قضيه': 'قضية', 'صوره': 'صورة',
    'واضحه': 'واضحة', 'مفيده': 'مفيدة', 'طالبه': 'طالبة', 'دراسه': 'دراسة', 'نقطه': 'نقطة',
    'فائده': 'فائدة', 'سنه': 'سنة', 'سوره': 'سورة', 'ايه': 'آية', 'كلمه': 'كلمة',
    'جمله': 'جملة', 'فكره': 'فكرة', 'صفحه': 'صفحة', 'طريقه': 'طريقة', 'حاله': 'حالة',
    'درجه': 'درجة', 'مرحله': 'مرحلة', 'فتره': 'فترة', 'جلسه': 'جلسة', 'خطوه': 'خطوة',
    'لغه': 'لغة', 'رساله': 'رسالة', 'مقاله': 'مقالة', 'مقدمه': 'مقدمة', 'خاتمه': 'خاتمة',
    'نتيجه': 'نتيجة', 'خاصه': 'خاصة', 'عامه': 'عامة', 'كبيره': 'كبيرة', 'صغيره': 'صغيرة',
    'كثيره': 'كثيرة', 'قليله': 'قليلة', 'جديده': 'جديدة', 'قديمه': 'قديمة', 'مهمه': 'مهمة',
    'صحيحه': 'صحيحة', 'خاطئه': 'خاطئة', 'كامله': 'كاملة', 'شامله': 'شاملة', 'طويله': 'طويلة',
    'قصيره': 'قصيرة', 'سهله': 'سهلة', 'صعبه': 'صعبة', 'رائعه': 'رائعة', 'جميله': 'جميلة',
    'عظيمه': 'عظيمة', 'شريفه': 'شريفة', 'سعيده': 'سعيدة', 'قاعده': 'قاعدة', 'مسابقه': 'مسابقة',
    'مذاكره': 'مذاكرة', 'مراجعه': 'مراجعة', 'مناقشه': 'مناقشة', 'ادله': 'أدلة', 'امثله': 'أمثلة',
    'اسئله': 'أسئلة', 'اجوبه': 'أجوبة', 'انظمه': 'أنظمة', 'طبيعه': 'طبيعة', 'عقيده': 'عقيدة',
    'معرفه': 'معرفة', 'حقيقه': 'حقيقة', 'طائفه': 'طائفة', 'فرقه': 'فرقة', 'سلطه': 'سلطة',
    'دوله': 'دولة', 'حكومه': 'حكومة', 'ثقافه': 'ثقافة', 'حضاره': 'حضارة', 'نهضه': 'نهضة',
    'امه': 'أمة', 'جماعه': 'جماعة', 'حاجه': 'حاجة', 'نيه': 'نية', 'رغبه': 'رغبة', 'قدره': 'قدرة',
    'قوه': 'قوة', 'رحمه': 'رحمة', 'نعمه': 'نعمة', 'حكمه': 'حكمة', 'بركه': 'بركة', 'صحه': 'صحة',
    'دلاله': 'دلالة', 'عله': 'علة', 'حجه': 'حجة', 'روايه': 'رواية', 'سيره': 'سيرة',
    'حديثيه': 'حديثية', 'اصوليه': 'أصولية', 'لغويه': 'لغوية', 'تاريخيه': 'تاريخية',
    'واجبه': 'واجبة', 'مستحبه': 'مستحبة', 'مباحه': 'مباحة', 'محرمه': 'محرمة', 'صدقه': 'صدقة',
    'توبه': 'توبة', 'طهاره': 'طهارة', 'نجاسه': 'نجاسة', 'عباده': 'عبادة', 'عماره': 'عمارة',
    'تجاره': 'تجارة', 'كفاره': 'كفارة', 'اضحيه': 'أضحية', 'عمره': 'عمرة', 'خطبه': 'خطبة',
    'واقعه': 'واقعة', 'علاقه': 'علاقة', 'شخصيه': 'شخصية', 'حريه': 'حرية', 'مسؤوليه': 'مسؤولية'
}

def smart_arabic_stt_corrector(text):
    if not text:
        return text
    words = text.split()
    corrected = []

    for w in words:
        m = re.match(r'^([^\w]*)(.*?)([^\w]*)$', w)
        if not m:
            corrected.append(w)
            continue
        prefix_p, core, suffix_p = m.groups()
        if not core:
            corrected.append(w)
            continue

        if core in HA_STRICT:
            corrected.append(w)
            continue

        if core in COMMON_FEMININE_ROOTS:
            core = COMMON_FEMININE_ROOTS[core]
            corrected.append(prefix_p + core + suffix_p)
            continue

        detected_prefix = ''
        sub_core = core
        for p in ['وال', 'فال', 'بال', 'كال', 'لل', 'ال', 'و', 'ف', 'ب', 'ك', 'ل']:
            if core.startswith(p) and len(core) > len(p) + 2:
                detected_prefix = p
                sub_core = core[len(p):]
                break

        if sub_core in HA_STRICT:
            corrected.append(w)
            continue

        if sub_core in COMMON_FEMININE_ROOTS:
            core = detected_prefix + COMMON_FEMININE_ROOTS[sub_core]
        elif (core.endswith('يه') or core.endswith('ية')) and len(core) >= 4 and core not in HA_STRICT and sub_core not in HA_STRICT:
            core = core[:-1] + 'ة'
        elif core.endswith('اه') and len(core) >= 4 and core not in HA_STRICT and sub_core not in HA_STRICT:
            core = core[:-1] + 'ة'
        elif detected_prefix in ['ال', 'وال', 'بال', 'فال', 'كال', 'لل'] and core.endswith('ه') and len(core) >= 4:
            core = core[:-1] + 'ة'
        elif core.startswith('م') and core.endswith('ه') and len(core) >= 4 and core not in HA_STRICT and sub_core not in HA_STRICT:
            core = core[:-1] + 'ة'
        elif len(core) >= 5 and core[1] == 'ا' and core.endswith('ه') and core not in HA_STRICT and sub_core not in HA_STRICT:
            core = core[:-1] + 'ة'

        corrected.append(prefix_p + core + suffix_p)

    res = ' '.join(corrected)
    res = re.sub(r'\bان\b', 'أن', res)
    res = re.sub(r'\bالى\b', 'إلى', res)
    res = re.sub(r'\bاو\b', 'أو', res)
    return res

# ==========================================
# ⚡ معالج الصوتيات المطور للمقاطع الطويلة (ساعة وساعتين)
# ==========================================
def process_audio_streaming(input_filepath, progress_callback=None):
    """
    تقطيع وتفريغ المقاطع الصوتية الطويلة ومسجلات الهواتف بحماية فائقة ضد الانقطاع
    دون استهلاك الذاكرة (RAM) وبأعلى جودة ممكنة.
    """
    session_id = f"st_{int(time.time())}_{random.randint(100, 999)}"
    output_pattern = f"{session_id}_%04d.wav"
    
    # أمر ffmpeg المقاوم لخلل مسجلات الهواتف والترميزات المختلفة
    cmd = [
        "ffmpeg", "-y", "-err_detect", "ignore_err",
        "-i", input_filepath,
        "-vn", "-sn", "-dn",
        "-f", "segment", "-segment_time", "45",
        "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
        output_pattern
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("FFmpeg segment notice:", e)
        
    chunk_files = sorted(glob.glob(f"{session_id}_*.wav"))
    
    # إذا تعذر التقطيع، نجرب التحويل المباشر كملف واحد كحل بديل
    if not chunk_files:
        fallback_wav = f"{session_id}_single.wav"
        cmd_fallback = [
            "ffmpeg", "-y", "-err_detect", "ignore_err",
            "-i", input_filepath,
            "-vn", "-sn", "-dn",
            "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
            fallback_wav
        ]
        try:
            subprocess.run(cmd_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(fallback_wav):
                chunk_files = [fallback_wav]
        except Exception:
            pass

    total_chunks = len(chunk_files)
    transcribed_text = []
    last_callback_time = 0

    for idx, chunk_file in enumerate(chunk_files):
        try:
            with sr.AudioFile(chunk_file) as source:
                audio_data = recognizer.record(source)
                for attempt in range(2):
                    try:
                        part = recognizer.recognize_google(audio_data, language=listening_language)
                        if part:
                            transcribed_text.append(part.strip())
                        break
                    except sr.UnknownValueError:
                        break
                    except Exception:
                        if attempt == 0:
                            time.sleep(0.5)
        except Exception as ex:
            print(f"Chunk processing notice [{idx}]: {ex}")
        finally:
            if os.path.exists(chunk_file):
                try:
                    os.remove(chunk_file)
                except Exception:
                    pass

        current_time = time.time()
        if progress_callback and (current_time - last_callback_time > 8 or idx == total_chunks - 1):
            progress_callback(idx + 1, total_chunks)
            last_callback_time = current_time

    raw_text_out = " ".join(transcribed_text)
    if listening_language.startswith("ar"):
        return smart_arabic_stt_corrector(raw_text_out)
    return raw_text_out

# ==========================================
# 🌟 أوامر البوت الأساسية
# ==========================================
# ==========================================
# 👑 لوحة تحكم مديرة ومطورة البوت (إكرام)
# ==========================================
@bot.message_handler(commands=['admin'])
def handle_admin_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⚠️ هذا الأمر مخصص لمديرة ومطورة البوت فقط.")
        return
    bot.send_message(
        message.chat.id,
        "👑 **أهلاً بكِ يا إكرام في لوحة تحكم إدارة وتطوير 'مدون الإكرام'!** 🌿\n\n"
        "اختاري من الخيارات التالية لمتابعة نشاط الطلاب وإدارة البوت:",
        parse_mode="Markdown",
        reply_markup=admin_panel_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ الصلاحية للمديرة فقط.", show_alert=True)
        return

    users = load_users()
    total_users = len(users)
    total_transcriptions = sum(u.get("transcriptions_count", 0) for u in users.values())

    if call.data == "admin_stats":
        stats_text = (
            "📊 **إحصائيات بوت 'مدون الإكرام' الشاملة:**\n\n"
            f"👥 **إجمالي الطلاب المسجلين:** `{total_users}` طالب وطالبة\n"
            f"🎙️ **إجمالي المحاضرات المفرغة:** `{total_transcriptions}` محاضرة\n"
            f"📅 **تاريخ اليوم:** `{datetime.now().strftime('%Y-%m-%d %H:%M')}`\n"
            f"⚙️ **خادم البوت:** متصل ويعمل بنشاط (Render Cloud) 🚀\n"
            f"🌐 **لغة التفريغ الحالية:** `{listening_language}`\n\n"
            "نسأل الله أن يبارك في هذا العمل وينفع به جميع طلاب العلم! 🌿"
        )
        bot.edit_message_text(stats_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=admin_panel_menu())

    elif call.data == "admin_users":
        if not users:
            bot.edit_message_text("👥 لا يوجد طلاب مسجلون في قاعدة البيانات حتى الآن.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=admin_panel_menu())
            return

        lines = ["👥 **قائمة أحدث الطلاب المسجلين في البوت:**\n"]
        recent_users = list(users.items())[-15:]
        for idx, (uid, udata) in enumerate(reversed(recent_users), 1):
            name = f"{udata.get('first_name', '')} {udata.get('last_name', '')}".strip()
            uname = f"@{udata.get('username')}" if udata.get('username') and udata.get('username') != "بدون يوزرنيم" else "بدون يوزر"
            count = udata.get('transcriptions_count', 0)
            lines.append(f"{idx}. **{name}** ({uname}) — تفريغات: `{count}`")

        msg_text = "\n".join(lines)
        if total_users > 15:
            msg_text += f"\n\n*(يوجد {total_users - 15} طالب إضافي، لتحميل القائمة الكاملة اضغطي تحميل تقرير الطلاب)*"
        bot.edit_message_text(msg_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=admin_panel_menu())

    elif call.data == "admin_export":
        report_file = "تقرير_طلاب_مدون_الإكرام.txt"
        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        content = [
            "╔═════════════════════════════════════════════════════════╗",
            "       🌟 بوت مدون الإكرام — التقرير الشامل للطلاب 🌟       ",
            "╚═════════════════════════════════════════════════════════╝",
            f"📅 تاريخ استخراج التقرير: {dt_str}",
            f"👥 إجمالي الطلاب: {total_users}",
            f"🎙️ إجمالي المحاضرات المفرغة: {total_transcriptions}",
            "─────────────────────────────────────────────────────────",
            ""
        ]
        for idx, (uid, udata) in enumerate(users.items(), 1):
            name = f"{udata.get('first_name', '')} {udata.get('last_name', '')}".strip()
            uname = f"@{udata.get('username')}" if udata.get('username') else "N/A"
            joined = udata.get('joined_at', 'N/A')
            active = udata.get('last_active', 'N/A')
            trans_c = udata.get('transcriptions_count', 0)
            content.append(f"[{idx}] المعرف: {uid} | الاسم: {name} | الحساب: {uname} | الانضمام: {joined} | آخر نشاط: {active} | المحاضرات: {trans_c}")

        content.append("\n─────────────────────────────────────────────────────────")
        content.append("✨ تم التصدير آلياً عبر لوحة تحكم مديرة البوت (إكرام) 🌿")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")

        with open(report_file, "rb") as doc:
            bot.send_document(call.message.chat.id, doc, caption="📁 **تقرير الطلاب الشامل والمحدث** 🌿", parse_mode="Markdown")
        bot.answer_callback_query(call.id, "✅ تم إرسال التقرير بنجاح!")

    elif call.data == "admin_broadcast":
        ADMIN_BROADCAST_STATE[ADMIN_ID] = True
        bot.send_message(
            call.message.chat.id,
            "📢 **أهلاً بكِ في ميزة الإذاعة الجماعية للطلاب!**\n\n"
            "أرسلي الآن الرسالة أو الإعلان الذي تريدين إذاعته (نص، صورة، أو مستند)، وسيقوم البوت بإرسالها فوراً لجميع الطلاب المسجلين بالبوت.\n\n"
            "*(أو أرسلي كلمة 'إلغاء' للتراجع)*",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    elif call.data == "admin_status":
        uptime_info = (
            "⚙️ **حالة خادم 'مدون الإكرام' السحابي:**\n\n"
            "🟢 **حالة البوت:** نشط ويعمل 24/7 على منصة Render Cloud.\n"
            f"👑 **المديرة المسجلة:** إكرام (`{ADMIN_ID}`)\n"
            "⚡ **محرك الصوت والتفريغ:** Google Speech Engine + FFmpeg\n"
            "📄 **محرك المستندات:** Python-Docx Engine\n"
            f"📅 **توقيت السيرفر:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
            "✨ جميع الخدمات تعمل بأعلى كفاءة واستقرار!"
        )
        bot.edit_message_text(uptime_info, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=admin_panel_menu())


@bot.message_handler(commands=['start'])
def send_welcome(message):
    register_or_update_user(message.from_user)
    name = message.from_user.first_name or "صديقي"
    banner_text = (
        "╔═══════════════════════════════════╗\n"
        "   🌟 **مُدَوِّنُ الْإِكْرَامِ — المساعد الجامعي** 🌟   \n"
        "╚═══════════════════════════════════╝\n\n"
        f"👋 أهلاً بكِ وبكم جميعاً يا {name} في رحاب العلم والمذاكرة!\n"
        "مساعدك الأكاديمي الذكي المخصص لطلبة **العلوم الإسلامية والدراسات الجامعية** 🌿\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📚 **ماذا يقدم لك البوت؟**\n"
        "• 🎙️ **تفريغ المحاضرات الطويلة** (حتى ساعة ونصف وساعتين) وتصديرها كملف Word منظم.\n"
        "• 🧠 **مسابقات واختبارات فقهية وأصولية** تفاعلية للمراجعة للامتحانات (`/quiz`).\n"
        "• 📖 **مساعد باحث شرعي:** اسأل عن أي مسألة أو قاعدة أو مصطلح ويجيبك فوراً!\n"
        "• 📅 **إدارة جدولك الدراسي** وتنظيم مواعيد المحاضرات (`/schedule`).\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 *اختر لغة المحاضرة أو أرسل التسجيل الصوتي للبدء فوراً:*"
    )
    bot.send_message(message.chat.id, banner_text, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))
    bot.send_message(message.chat.id, "اختر لغة التفريغ من القائمة أدناه:", reply_markup=language_menu())

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "📖 **دليل الاستخدام السريع:**\n\n"
        "1️⃣ **لتفريغ محاضرة أو تسجيل:** أرسل المقطع الصوتي أو المرئي مباشرة، وسيقوم البوت بتجزئته وتفريغه وإرسال ملف Word كامل منسق مع الأسئلة والملخص.\n"
        "2️⃣ **للتسجيلات الطويلة (ساعة وساعتين):** أرسل المحاضرة كـ Voice Note أو قلل حجم الملف عن 20 ميغابايت وسيتولى البوت الباقي بشريط تقدم حي.\n"
        "3️⃣ **للمذاكرة والاختبار:** اضغط على زر '🧠 مسابقة العلوم الإسلامية' لاختبار معلوماتك فوراً.\n"
        "4️⃣ **للاستفسار الأكاديمي:** اكتب أي سؤال وسيجيبك المساعد العلمي الذكي."
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))

# ==========================================
# 🧠 مسابقات العلوم الإسلامية التفاعلية
# ==========================================
@bot.message_handler(commands=['quiz'])
def start_quiz(message):
    chat_id = message.chat.id
    selected_quiz = random.choice(ISLAMIC_QUIZ_BANK)
    USER_QUIZ_STATE[chat_id] = selected_quiz

    options_text = "\n".join(selected_quiz["options"])
    quiz_msg = (
        f"🏛️ **مسابقة المراجعة — تخصص: {selected_quiz['category']}** 🧠\n\n"
        f"❓ **السؤال:**\n{selected_quiz['question']}\n\n"
        f"{options_text}\n\n"
        "👇 *اضغط أو اكتب حرف الإجابة الصحيحة (أ، ب، أو ج):*"
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("أ", callback_data="quiz_ans_أ"),
        InlineKeyboardButton("ب", callback_data="quiz_ans_ب"),
        InlineKeyboardButton("ج", callback_data="quiz_ans_ج")
    )
    bot.send_message(chat_id, quiz_msg, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_ans_'))
def handle_quiz_callback(call):
    chat_id = call.message.chat.id
    user_answer = call.data.split('_')[2]
    user_name = call.from_user.first_name or "طالب العلم"
    
    quiz_data = USER_QUIZ_STATE.get(chat_id)
    if not quiz_data:
        bot.answer_callback_query(call.id, "انتهت صلاحية هذا السؤال، اطلب سؤالاً جديداً عبر /quiz")
        return

    correct_answer = quiz_data["answer"]
    explanation = quiz_data["explanation"]

    if user_answer == correct_answer:
        res_text = (
            f"🎉 **أحسنتِ وأصبتِ يا {user_name}! إجابة صحيحة وصائبة تماماً ({correct_answer})** 🌟\n\n"
            f"💡 **الإيضاح العلمي:**\n{explanation}"
        )
    else:
        res_text = (
            f"❌ **للأسف إجابة غير صحيحة يا {user_name}.**\n"
            f"✅ **الإجابة الصائبة هي:** ({correct_answer})\n\n"
            f"💡 **الإيضاح العلمي:**\n{explanation}"
        )

    bot.send_message(chat_id, res_text, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))
    bot.answer_callback_query(call.id)
    if chat_id in USER_QUIZ_STATE:
        del USER_QUIZ_STATE[chat_id]

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    chat_id = message.chat.id
    if chat_id in USER_QUIZ_STATE:
        del USER_QUIZ_STATE[chat_id]
    bot.send_message(message.chat.id, "✅ تم إلغاء العمليات الحالية والعودة للوضع الطبيعي.", reply_markup=permanent_keyboard(message.from_user.id))

@bot.message_handler(commands=['set_schedule'])
def set_schedule_start(message):
    bot.send_message(message.chat.id, "✏️ أرسل جدولك الدراسي كاملاً في رسالة واحدة:", reply_markup=permanent_keyboard(message.from_user.id))
    bot.register_next_step_handler(message, lambda m: USER_SCHEDULES.update({m.chat.id: m.text}) and bot.reply_to(m, "✅ تم حفظ الجدول بنجاح!"))

@bot.message_handler(commands=['schedule'])
def show_schedule(message):
    schedule = USER_SCHEDULES.get(message.chat.id, "📅 لم تقم بإدخال جدولك بعد. استخدم `/set_schedule` لإدخاله.")
    bot.send_message(message.chat.id, schedule, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))

@bot.message_handler(commands=['history'])
def show_history(message):
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        bot.send_message(message.chat.id, f"📂 **سجل المحاضرات المفرغة:**\n\n{content}" if content.strip() else "📂 السجل فارغ.", parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))
    else:
        bot.send_message(message.chat.id, "📂 لا يوجد سجل بعد.", reply_markup=permanent_keyboard(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def set_language_callback(call):
    global listening_language
    listening_language = call.data.split('_')[1]
    lang_names = {
        "ar-DZ": "العربية (الجزائر) 🇩🇿",
        "ar-SA": "العربية الفصحى 🇸🇦",
        "ru-RU": "الروسية 🇷🇺",
        "fr-FR": "الفرنسية 🇫🇷",
        "en-US": "الإنجليزية 🇺🇸"
    }
    display_name = lang_names.get(listening_language, listening_language)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ تم ضبط لغة التفريغ بنجاح إلى: **{display_name}**.\n\nتفضل بإرسال التسجيل الصوتي أو المحاضرة الآن! 🎙️",
        parse_mode="Markdown"
    )

# ==========================================
# 💬 معالجة الرسائل النصية والمحادثة الذكية
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_personalized_text(message):
    chat_id = message.chat.id
    register_or_update_user(message.from_user)

    # معالجة وضع الإذاعة الجماعية للمديرة
    if message.from_user.id == ADMIN_ID and ADMIN_BROADCAST_STATE.get(ADMIN_ID):
        if message.text and ("إلغاء" in message.text.lower() or message.text.lower() == "cancel"):
            ADMIN_BROADCAST_STATE[ADMIN_ID] = False
            bot.reply_to(message, "❌ تم إلغاء الإذاعة الجماعية.", reply_markup=permanent_keyboard(message.from_user.id))
            return

        ADMIN_BROADCAST_STATE[ADMIN_ID] = False
        users = load_users()
        sent_count = 0
        status_msg = bot.reply_to(message, "⏳ جاري إرسال الإذاعة لجميع الطلاب...")
        for uid in list(users.keys()):
            if int(uid) != ADMIN_ID:
                try:
                    bot.send_message(
                        int(uid),
                        f"📢 **إعلان وتنبيه من إدارة 'مدون الإكرام':**\n\n{message.text}",
                        parse_mode="Markdown"
                    )
                    sent_count += 1
                except Exception:
                    pass
        bot.edit_message_text(
            f"✅ **تمت الإذاعة بنجاح!**\n\nوصل الإعلان إلى `{sent_count}` طالب وطالبة من أصل `{len(users)}` مسجلين.",
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            parse_mode="Markdown"
        )
        return

    # زر لوحة التحكم للإدارة
    if message.from_user.id == ADMIN_ID and "لوحة تحكم" in message.text:
        handle_admin_command(message)
        return
    user_name = message.from_user.first_name or "صديقي"
    text = message.text.strip()
    text_lower = text.lower()

    if "إلغاء" in text_lower or text_lower == "cancel":
        cancel_operation(message)
        return

    # فحص إجابة الكويز إذا كتبت كتابة
    if chat_id in USER_QUIZ_STATE:
        quiz_data = USER_QUIZ_STATE[chat_id]
        correct = quiz_data["answer"]
        if text.upper() in [correct, f"({correct})", f"الخيار {correct}"]:
            bot.reply_to(message, f"🎉 أحسنتِ يا {user_name}! إجابة صحيحة ({correct}).\n\n💡 {quiz_data['explanation']}", reply_markup=permanent_keyboard(message.from_user.id))
        else:
            bot.reply_to(message, f"❌ إجابة خاطئة يا {user_name}. الإجابة الصائبة هي ({correct}).\n\n💡 {quiz_data['explanation']}", reply_markup=permanent_keyboard(message.from_user.id))
        del USER_QUIZ_STATE[chat_id]
        return

    # استجابات الأزرار الثابتة
    if "تغيير لغة" in text or "لغة" in text or "لغات" in text:
        bot.reply_to(message, "🌐 اختر لغة تفريغ المقاطع الصوتية من القائمة أدناه:", reply_markup=language_menu())
        return
    elif "مسابقة" in text or "كويز" in text or "اختبار" in text:
        start_quiz(message)
        return
    elif "أرسل تسجيلاً" in text or text == "تفريغ" or "تسجيل" in text:
        bot.reply_to(message, f"🎙️ تفضل يا {user_name}، أرسل الملف الصوتي أو مقطع الفيديو الآن وسأتولى تفريغه فوراً كملف Word احترافي!", reply_markup=permanent_keyboard(message.from_user.id))
        return
    elif "مساعدة" in text or "أسئلة دراسية" in text:
        bot.reply_to(message, f"📚 أهلاً بك يا {user_name}! أنا مساعدك في العلوم الإسلامية، اكتب لي أي سؤال فقهي أو أصولي أو مصطلح علمي وسأشرحه لك فوراً.", reply_markup=permanent_keyboard(message.from_user.id))
        return
    elif "جدول" in text:
        show_schedule(message)
        return

    # تحيات وأسئلة عامة
    if any(g in text_lower for g in ["سلام", "السلام عليكم", "مرحبا", "أهلا", "صباح", "مساء"]):
        bot.reply_to(message, f"وعليكم السلام ورحمة الله وبركاته يا {user_name}! 🌿 أهلاً بك في بوت العلوم الإسلامية. تفضل بإرسال تسجيل المحاضرة أو اطرح استفسارك العلمي.", reply_markup=permanent_keyboard(message.from_user.id))
        return

    # التجاوب الذكي مع أسئلة الطالب ومذاكرته
    response = ask_ai_study_assistant(text, user_name)
    bot.reply_to(message, response, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))

# ==========================================
# 🎙️ استقبال وتفريغ الوسائط (مع حماية الحجم والمقاطع الطويلة)
# ==========================================
@bot.message_handler(content_types=['voice', 'audio', 'document', 'video', 'video_note'])
def handle_smart_media_to_word(message):
    global listening_language
    user_name = message.from_user.first_name or "صديقي"
    working_msg = None
    temp_input = f"input_{message.chat.id}_{int(time.time())}.tmp"
    output_docx = f"محاضرة_{user_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    output_txt = output_docx.replace(".docx", ".txt")

    try:
        # تحديد الملف وحجمه
        media_obj = None
        media_name = "محاضرة_صوتية"

        if message.content_type == 'voice':
            media_obj = message.voice
            media_name = f"تسجيل_صوتي_{user_name}"
        elif message.content_type == 'audio':
            media_obj = message.audio
            media_name = message.audio.file_name if message.audio.file_name else "ملف_صوتي"
        elif message.content_type in ['video', 'video_note']:
            media_obj = message.video if message.content_type == 'video' else message.video_note
            media_name = "مقطع_مرئي"
        elif message.content_type == 'document':
            media_obj = message.document
            media_name = message.document.file_name if message.document.file_name else "مستند"

        # 🛑 الفحص لحجم الملف (الحد الأقصى المطلق في تيليجرام: 2000 ميغابايت / 2 جيجابايت!)
        file_size = getattr(media_obj, 'file_size', 0) or 0
        if file_size > 2000 * 1024 * 1024:
            bot.reply_to(
                message,
                f"⚠️ **عذراً يا {user_name}، حجم هذا الملف يتجاوز الحد الأقصى المطلق في تيليجرام (2000 ميغابايت / 2 جيجابايت).**",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard(message.from_user.id)
            )
            return

        size_mb = round(file_size / (1024 * 1024), 1)
        if file_size > 20 * 1024 * 1024:
            working_msg = bot.reply_to(
                message,
                f"⏳ **يا {user_name}، تم استلام ملف المحاضرة الكبير ({size_mb} ميغابايت). جاري التحميل المباشر فائق السرعة عبر MTProto والبدء في التفريغ...** 🌿",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard(message.from_user.id)
            )
        else:
            working_msg = bot.reply_to(
                message,
                f"⏳ **يا {user_name}، جاري استلام ملف المحاضرة والبدء في تفريغه...** 🌿",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard(message.from_user.id)
            )

        # تحميل الملف من تيليجرام بنظام التحميل الهجين الذكي
        download_success = False

        # 1. للملفات العادية (أقل من أو يساوي 20 ميغابايت): التحميل السريع
        if file_size <= 20 * 1024 * 1024:
            try:
                file_info = bot.get_file(media_obj.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                with open(temp_input, 'wb') as f:
                    f.write(downloaded_file)
                if os.path.exists(temp_input) and os.path.getsize(temp_input) > 0:
                    download_success = True
            except Exception as ex_down:
                print("Standard bot download notice:", ex_down)

        # 2. للملفات الكبيرة (أكبر من 20 ميغابايت) أو في حال تعثر التحميل العادي: التحميل المباشر عبر MTProto
        if not download_success and telethon_client:
            # ننتظر قليلاً (حتى 3 ثوانٍ) في حال كان وصول الرسالة جارياً في خيط الخلفية
            mt_msg = None
            for _ in range(6):
                mt_msg = TELETHON_MEDIA_CACHE.get(f"{message.chat.id}_{message.message_id}") or TELETHON_MEDIA_CACHE.get(message.chat.id)
                if mt_msg and mt_msg.media:
                    break
                time.sleep(0.5)

            if mt_msg and mt_msg.media:
                try:
                    telethon_client.download_media(mt_msg, file=temp_input)
                    if os.path.exists(temp_input) and os.path.getsize(temp_input) > 0:
                        download_success = True
                except Exception as ex_dl:
                    print("Telethon mt_msg download error:", ex_dl)

            # محاولة احتياطية ثانية عبر معرف الملف المباشر (file_id)
            if not download_success:
                try:
                    telethon_client.download_media(media_obj.file_id, file=temp_input)
                    if os.path.exists(temp_input) and os.path.getsize(temp_input) > 0:
                        download_success = True
                except Exception as ex_fid:
                    print("Telethon file_id download error:", ex_fid)

        if not download_success:
            if file_size > 20 * 1024 * 1024:
                err_text = (
                    f"⚠️ عذراً يا {user_name}، تعذر تحميل هذا الملف الكبير ({size_mb} ميغابايت) مباشرة.\n\n"
                    "💡 حل فوري ومضمون لتفريغ المحاضرة الآن:\n"
                    "قومي بإرسال التسجيل كـ رسالة صوتية (Voice Note) في تيليجرام، فتيليجرام يضغطه تلقائياً لأقل من 15 ميغابايت وسيقبله البوت فوراً!"
                )
            else:
                err_text = f"⚠️ عذراً يا {user_name}، حدث خطأ أثناء استلام الملف من تيليجرام. يرجى إعادة المحاولة."
            
            try:
                bot.edit_message_text(text=err_text, chat_id=message.chat.id, message_id=working_msg.message_id)
            except Exception:
                bot.send_message(message.chat.id, err_text)
            return

        # دالة رد النداء لتحديث شريط التقدم للطالب
        def update_progress(current, total):
            try:
                percent = int((current / total) * 100)
                filled = int(percent / 10)
                bar = "█" * filled + "░" * (10 - filled)
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=working_msg.message_id,
                    text=(
                        f"⏳ **جاري تفريغ المحاضرة يا {user_name}...** 🌿\n\n"
                        f"📊 **نسبة الإنجاز:** `[{bar}]` **{percent}%**\n"
                        f"🎙️ **معالجة المقطع:** {current} من أصل {total}\n\n"
                        f"✨ يتم الآن تحويل الكلمات وبناء مستند Word الأكاديمي والملف النصي..."
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        # تفريغ المقطع بنظام التدفق المنخفض للذاكرة
        raw_text = process_audio_streaming(temp_input, progress_callback=update_progress)

        if raw_text and raw_text.strip():
            save_to_history(media_name)
            register_or_update_user(message.from_user, is_transcription=True)
            
            try:
                bot.delete_message(message.chat.id, working_msg.message_id)
            except Exception:
                pass

            # 1. إنشاء مستند Word الأكاديمي المنسق
            create_word_document(raw_text, user_name, output_docx)
            # 2. إنشاء الملف النصي الخفيف
            create_text_document(raw_text, user_name, output_txt)

            # 3. إرسال ملخص / تفريغ مباشر في رسالة تيليجرام
            words_count = len(raw_text.split())
            if words_count <= 200:
                chat_msg = (
                    f"🎙️ **تفريغ التسجيل الصوتي كاملاً يا {user_name}:**\n\n"
                    f"«{raw_text.strip()}»\n\n"
                    f"📄 تم إرفاق مستند Word والملف النصي أدناه للمراجعة والطباعة ⬇️"
                )
            else:
                preview = " ".join(raw_text.split()[:60]) + "..."
                chat_msg = (
                    f"🎓 **تم تفريغ المحاضرة وتنظيمها بنجاح يا {user_name}!** 🌿\n\n"
                    f"📊 **إحصائيات المحاضرة:** عدد الكلمات: `{words_count}` كلمة تقريباً.\n"
                    f"📅 **التاريخ:** `{datetime.now().strftime('%Y-%m-%d %H:%M')}`\n\n"
                    f"📖 **مقتطف من بداية المحاضرة:**\n«{preview}»\n\n"
                    f"👇 **تجدين أدناه مستند Word الأكاديمي المنسق + النسخة النصية الكاملة:**"
                )

            bot.send_message(message.chat.id, chat_msg, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))

            # إرسال مستند Word المنسق
            with open(output_docx, "rb") as doc_to_send:
                bot.send_document(
                    message.chat.id,
                    doc_to_send,
                    caption="📄 **مستند Word الأكاديمي المنسق** (محاور وعناوين وأسئلة امتحان) ✨",
                    parse_mode="Markdown"
                )

            # إرسال الملف النصي الخفيف
            with open(output_txt, "rb") as txt_to_send:
                bot.send_document(
                    message.chat.id,
                    txt_to_send,
                    caption="📝 **نسخة نصية خفيفة كاملة (.txt)** لسهولة القراءة والنسخ على أي هاتف 🌿",
                    parse_mode="Markdown",
                    reply_markup=permanent_keyboard(message.from_user.id)
                )
        else:
            bot.edit_message_text(
                f"⚠️ عذراً يا {user_name}، لم يتم العثور على كلام واضح داخل هذا المقطع الصوتي.",
                chat_id=message.chat.id,
                message_id=working_msg.message_id
            )

    except telebot.apihelper.ApiTelegramException as api_ex:
        if "file is too big" in str(api_ex).lower():
            bot.reply_to(
                message,
                f"⚠️ **الملف يتجاوز الحد الأقصى المسموح به في تيليجرام (20 ميغابايت).**\n\n"
                "💡 **كيف تفرغين محاضرتك كاملة (ساعة ونصف أو ساعتين) بسهولة؟**\n"
                "1️⃣ **الحل الأسهل (بدون أي برامج):** قومي بتحويل الملف إلى **تسجيل صوتي (Voice Note)** في تيليجرام، فتيليجرام يضغطه تلقائياً ليكون أقل من 15 ميغابايت وسيقبله البوت فوراً!\n"
                "2️⃣ **أو ضغط الصوت:** تحويله إلى صيغة mp3 أو m4a بجودة 32kbps وسيصبح حجم الساعتين 14 ميغابايت فقط!\n"
                "3️⃣ **أو تقسيم التسجيل إلى جزأين:** مثلاً 45 دقيقة لكل جزء.",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard(message.from_user.id)
            )
        else:
            bot.reply_to(message, f"❌ حدث خطأ من تيليجرام أثناء استلام الملف: {api_ex}", reply_markup=permanent_keyboard(message.from_user.id))
    except Exception as e:
        print("Media Processing Error:", e)
        if working_msg:
            try:
                bot.delete_message(message.chat.id, working_msg.message_id)
            except Exception:
                pass
        bot.reply_to(
            message,
            f"❌ عذراً يا {user_name}، حدث خطأ أثناء تفريغ هذا الملف. تأكدي من سلامة صيغة الصوت وأعيدي المحاولة.",
            reply_markup=permanent_keyboard(message.from_user.id)
        )
    finally:
        # تنظيف كل الملفات المؤقتة
        if os.path.exists(temp_input):
            try:
                os.remove(temp_input)
            except Exception:
                pass
        if os.path.exists(output_docx):
            try:
                os.remove(output_docx)
            except Exception:
                pass
        if os.path.exists(output_txt):
            try:
                os.remove(output_txt)
            except Exception:
                pass

# ==========================================
# 🚀 بدء تشغيل البوت
# ==========================================
print("✅ بوت 'مدون الإكرام' المطور للعلوم الإسلامية والدراسات الجامعية جاهز للعمل!")

try:
    bot.remove_webhook()
except Exception:
    pass

keep_alive()

try:
    bot.remove_webhook()
except Exception:
    pass

bot.infinity_polling(timeout=20, long_polling_timeout=20)
