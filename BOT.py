import os
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

telethon_client = None
try:
    from telethon.sync import TelegramClient
    telethon_client = TelegramClient("bot_mtproto_sync", TG_API_ID, TG_API_HASH)
    telethon_client.start(bot_token=TOKEN)
    print("✅ محرك MTProto المباشر متصل وجاهز للتعامل مع ملفات حتى 2GB!")
except Exception as e:
    print("MTProto init notice:", e)
    telethon_client = None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

bot = telebot.TeleBot(TOKEN)
recognizer = sr.Recognizer()
translator = GoogleTranslator(source='auto', target='ar')

listening_language = "ar-DZ"
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

def permanent_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🎙️ أرسل تسجيلاً للتفريغ"), KeyboardButton("🧠 مسابقة العلوم الإسلامية"))
    markup.row(KeyboardButton("📚 مساعدة وأسئلة دراسية"), KeyboardButton("📅 جدولي الدراسي"))
    markup.row(KeyboardButton("🌐 تغيير لغة التفريغ"), KeyboardButton("❌ إلغاء"))
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
@bot.message_handler(commands=['start'])
def send_welcome(message):
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
    bot.send_message(message.chat.id, banner_text, parse_mode="Markdown", reply_markup=permanent_keyboard())
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
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown", reply_markup=permanent_keyboard())

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

    bot.send_message(chat_id, res_text, parse_mode="Markdown", reply_markup=permanent_keyboard())
    bot.answer_callback_query(call.id)
    if chat_id in USER_QUIZ_STATE:
        del USER_QUIZ_STATE[chat_id]

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
        bot.send_message(message.chat.id, f"📂 **سجل المحاضرات المفرغة:**\n\n{content}" if content.strip() else "📂 السجل فارغ.", parse_mode="Markdown", reply_markup=permanent_keyboard())
    else:
        bot.send_message(message.chat.id, "📂 لا يوجد سجل بعد.", reply_markup=permanent_keyboard())

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
            bot.reply_to(message, f"🎉 أحسنتِ يا {user_name}! إجابة صحيحة ({correct}).\n\n💡 {quiz_data['explanation']}", reply_markup=permanent_keyboard())
        else:
            bot.reply_to(message, f"❌ إجابة خاطئة يا {user_name}. الإجابة الصائبة هي ({correct}).\n\n💡 {quiz_data['explanation']}", reply_markup=permanent_keyboard())
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
        bot.reply_to(message, f"🎙️ تفضل يا {user_name}، أرسل الملف الصوتي أو مقطع الفيديو الآن وسأتولى تفريغه فوراً كملف Word احترافي!", reply_markup=permanent_keyboard())
        return
    elif "مساعدة" in text or "أسئلة دراسية" in text:
        bot.reply_to(message, f"📚 أهلاً بك يا {user_name}! أنا مساعدك في العلوم الإسلامية، اكتب لي أي سؤال فقهي أو أصولي أو مصطلح علمي وسأشرحه لك فوراً.", reply_markup=permanent_keyboard())
        return
    elif "جدول" in text:
        show_schedule(message)
        return

    # تحيات وأسئلة عامة
    if any(g in text_lower for g in ["سلام", "السلام عليكم", "مرحبا", "أهلا", "صباح", "مساء"]):
        bot.reply_to(message, f"وعليكم السلام ورحمة الله وبركاته يا {user_name}! 🌿 أهلاً بك في بوت العلوم الإسلامية. تفضل بإرسال تسجيل المحاضرة أو اطرح استفسارك العلمي.", reply_markup=permanent_keyboard())
        return

    # التجاوب الذكي مع أسئلة الطالب ومذاكرته
    response = ask_ai_study_assistant(text, user_name)
    bot.reply_to(message, response, parse_mode="Markdown", reply_markup=permanent_keyboard())

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
                reply_markup=permanent_keyboard()
            )
            return

        size_mb = round(file_size / (1024 * 1024), 1)
        if file_size > 20 * 1024 * 1024:
            working_msg = bot.reply_to(
                message,
                f"⏳ **يا {user_name}، تم استلام ملف المحاضرة الكبير ({size_mb} ميغابايت). جاري التحميل المباشر فائق السرعة عبر MTProto والبدء في التفريغ...** 🌿",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard()
            )
        else:
            working_msg = bot.reply_to(
                message,
                f"⏳ **يا {user_name}، جاري استلام ملف المحاضرة والبدء في تفريغه...** 🌿",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard()
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
            try:
                peer = message.from_user.username if getattr(message.from_user, 'username', None) else message.chat.id
                mt_msg = telethon_client.get_messages(peer, ids=message.message_id)
                if mt_msg and mt_msg.media:
                    telethon_client.download_media(mt_msg, file=temp_input)
                    if os.path.exists(temp_input) and os.path.getsize(temp_input) > 0:
                        download_success = True
            except Exception as ex_mt:
                print("Telethon direct download notice:", ex_mt)

        if not download_success:
            if file_size > 20 * 1024 * 1024:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=working_msg.message_id,
                    text=(
                        f"⚠️ **عذراً يا {user_name}، تعذر تحميل الملف الكبير ({size_mb} ميغابايت) مباشرة.**\n\n"
                        "💡 **حل فوري وسهل:** قومي بإرسال التسجيل كـ **رسالة صوتية (Voice Note)** في تيليجرام، فتيليجرام يضغطه تلقائياً لأقل من 15 ميغابايت وسيقبله البوت فوراً!"
                    ),
                    parse_mode="Markdown"
                )
                return
            else:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=working_msg.message_id,
                    text=f"⚠️ عذراً يا {user_name}، حدث خطأ أثناء تحميل الملف من خوادم تيليجرام. يرجى إعادة المحاولة."
                )
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

            bot.send_message(message.chat.id, chat_msg, parse_mode="Markdown", reply_markup=permanent_keyboard())

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
                    reply_markup=permanent_keyboard()
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
                reply_markup=permanent_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ حدث خطأ من تيليجرام أثناء استلام الملف: {api_ex}", reply_markup=permanent_keyboard())
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
            reply_markup=permanent_keyboard()
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
