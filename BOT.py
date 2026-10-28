import os
import json
import glob
import time
import random
import subprocess
import re
import shutil
from datetime import datetime
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
import speech_recognition as sr
from pydub import AudioSegment
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
    _DEF_T = "ODgxOTgzMDgwMTpBQUVCb3kwWnBpWG84NVgyZXR0XzY0b3E0cjg1RHA1cEZBZw=="
    TOKEN = base64.b64decode(_DEF_T).decode("utf-8")

TG_API_ID = int(os.environ.get("TG_API_ID", 35521120))
TG_API_HASH = os.environ.get("TG_API_HASH", "149519bc317198bd16527e19fd4bada1")

def is_port_open(port, host="127.0.0.1"):
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def init_local_telegram_bot_api():
    """تشغيل خادم تيليجرام المحلي لرفع حد تحميل الملفات إلى 2000 ميغابايت (2GB)"""
    binary = "/usr/local/bin/telegram-bot-api"
    if os.path.exists(binary):
        os.makedirs("/tmp/tg_bot_api", exist_ok=True)
        os.makedirs("/tmp/tg_bot_api_temp", exist_ok=True)
        cmd = [
            binary,
            f"--api-id={TG_API_ID}",
            f"--api-hash={TG_API_HASH}",
            "--local",
            "--http-port=8081",
            "--dir=/tmp/tg_bot_api",
            "--temp-dir=/tmp/tg_bot_api_temp"
        ]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2.5)
            if is_port_open(8081):
                telebot.apihelper.API_URL = "http://127.0.0.1:8081/bot{0}/{1}"
                telebot.apihelper.FILE_URL = "http://127.0.0.1:8081/file/bot{0}/{1}"
                print("🚀 خادم Telegram Bot API المحلي يعمل بنجاح! تم فتح دعم الملفات الكبيرة حتى 2000 ميغابايت (2GB)!")
            else:
                print("ℹ️ خادم Telegram Bot API المحلي لم يستجب على المنفذ 8081، سيتم استخدام خادم تيليجرام الرسمي.")
        except Exception as e:
            print("Local bot api notice:", e)

USE_LOCAL_TG_API = os.environ.get("USE_LOCAL_TG_API", "false").lower() == "true"
if USE_LOCAL_TG_API:
    init_local_telegram_bot_api()
else:
    print("✅ استخدام خادم Telegram Cloud API الرسمي المباشر والمستقر لجميع الملفات الصوتية حتى 20MB.")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

bot = telebot.TeleBot(TOKEN)
recognizer = sr.Recognizer()
translator = GoogleTranslator(source='auto', target='ar')

listening_language = "ar-DZ"

ADMIN_ID = int(os.environ.get("ADMIN_ID", 6619712661))
USERS_DB_FILE = "bot_users.json"
ADMIN_BROADCAST_STATE = {}
USER_TRANSLATE_STATE = {}
TRANSLATION_CACHE = {}

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
# 🧠 بنك الأسئلة والمراجعة الذاتية للعلوم الإسلامية والدراسات الجامعية
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
        "question": "ما هي القاعدة الفقهية الكبرى التي تفيد بأن 'الأصل بقاء ما كان على ما كان حتى يثبت العكس'؟",
        "options": ["أ) المشقة تجلب التيسير", "ب) اليقين لا يزول بالشك", "ج) العادة محكّمة"],
        "answer": "ب",
        "explanation": "قاعدة 'اليقين لا يزول بالشك' أصل عظيم يتفرع عنها: استصحاب الحال وبراءة الذمة."
    },
    {
        "category": "مصطلح الحديث",
        "question": "الحديث الذي اتصل سنده بنقل العدل الضابط عن مثله إلى منتهاه من غير شذوذ ولا علة هو:",
        "options": ["أ) الحديث الصحيح", "ب) الحديث الحسن", "ج) الحديث المتواتر"],
        "answer": "أ",
        "explanation": "هذا هو التعريف الدقيق للحديث الصحيح لذاته بشروطه الخمسة المقررة عند أئمة الحديث."
    },
    {
        "category": "علوم القرآن",
        "question": "الآيات التي نزلت بمكة المكرمة قبل الهجرة النبوية تسمى بالاصطلاح المشهور:",
        "options": ["أ) القرآن المدني", "ب) القرآن المكي", "ج) المحكم"],
        "answer": "ب",
        "explanation": "المكي ما نزل قبل الهجرة ولو بغير مكة، والمدني ما نزل بعد الهجرة ولو بمكة كآية إكمال الدين."
    },
    {
        "category": "مقاصد الشريعة",
        "question": "الكليات الخمس الضرورية التي اتفقت جميع الشرائع السماوية على حفظها هي:",
        "options": ["أ) الدين، النفس، العقل، النسل، المال", "ب) المال، العلم، الوطن، الجاه، النسب", "ج) الصحة، القوة، الفكر، العمل، العبادة"],
        "answer": "أ",
        "explanation": "الضروريات الخمس هي: حفظ الدين، النفس، العقل، العرض/النسل، والمال؛ وعليها مدار مصالح الدارين."
    },
    {
        "category": "الفقه المقارن",
        "question": "إمام دار الهجرة وصاحب كتاب 'الموطأ' ومذهب أهل المدينة المشهور هو الإمام:",
        "options": ["أ) الشافعي", "ب) أبو حنيفة", "ج) مالك بن أنس"],
        "answer": "ج",
        "explanation": "هو الإمام مالك بن أنس رحمه الله، إمام دار الهجرة ومؤسس المذهب المالكي."
    },
    {
        "category": "أصول الفقه",
        "question": "اللفظ الذي يستغرق الصالح له من غير حصر بحسب وضع واحد يسمى في مباحث الألفاظ الأصولية بـ:",
        "options": ["أ) العام", "ب) الخاص", "ج) المطلق"],
        "answer": "أ",
        "explanation": "العام يستغرق جميع الأفراد دفعة واحدة بألفاظه المعروفة كـ (كل، جميع، والأسماء الموصولة، والمعرف بأل الجنسية)."
    },
    {
        "category": "القواعد الفقهية",
        "question": "قاعدة 'الضرر يُزال' تستند بالأساس إلى الحديث النبوي الشريف المشهور:",
        "options": ["أ) إنما الأعمال بالنيات", "ب) لا ضرر ولا ضرار", "ج) الحلال بيّن والحرام بيّن"],
        "answer": "ب",
        "explanation": "حديث 'لا ضرر ولا ضرار' أصل تشريعي جامع تفرعت عنه قواعد دفع الضرر ورفعه ومنع الاعتداء."
    },
    {
        "category": "مصطلح الحديث",
        "question": "ما أضيف إلى النبي ﷺ من قول أو فعل أو تقرير أو صفة خَلقية أو خُلقية يسمى:",
        "options": ["أ) الحديث الموقوف", "ب) الحديث المرفوع", "ج) الحديث المقطوع"],
        "answer": "ب",
        "explanation": "المرفوع ما أضيف للنبي ﷺ، والموقوف ما أضيف للصحابي، والمقطوع ما أضيف للتابعي فمن بعده."
    },
    {
        "category": "مقاصد الشريعة",
        "question": "الرخص الشرعية كالفطر في رمضان للمسافر والمريض وقصر الصلاة تندرج ضمن مرتبة المقاصد:",
        "options": ["أ) الضروريات", "ب) الحاجيات", "ج) التحسينيات"],
        "answer": "ب",
        "explanation": "الحاجيات هي ما يفتقر إليها الناس لرفع الحرج والمشقة؛ وتفويتها يوقع في الضيق والحرج دون هلاك الكليات."
    },
    {
        "category": "أصول الفقه",
        "question": "دلالة اللفظ على ثبوت حكم المنطوق به للمسكوت عنه لاشتراكهما في علة الحكم المفهومة تسمى:",
        "options": ["أ) مفهوم المخالفة", "ب) مفهوم الموافقة", "ج) دلالة الاقتضاء"],
        "answer": "ب",
        "explanation": "مفهوم الموافقة كتحريم التأفيف للوالدين الدال بالأولى على تحريم ضربهما (فحوى الخطاب)."
    },
    {
        "category": "الفقه والمعاملات",
        "question": "بيع ما ليس عند الإنسان مع تأجيل البدلين معاً (الدين بالدين أو الكالئ بالكالئ) حكمه في الشريعة:",
        "options": ["أ) مباح ومستحب", "ب) جائز مع الكراهة", "ج) محرم وممنوع باتفاق"],
        "answer": "ج",
        "explanation": "بيع الكالئ بالكالئ (الدين بالدين) مجمع على تحريمه لما فيه من الغرر والربا والمفاسد."
    },
    {
        "category": "علوم القرآن",
        "question": "أجمع الصحابة رضي الله عنهم على كتابة القرآن على رسم مصحف واحد بلغة قريش في عهد الخليفة الراشد:",
        "options": ["أ) أبو بكر الصديق", "ب) عمر بن الخطاب", "ج) عثمان بن عفان"],
        "answer": "ج",
        "explanation": "نسخ عثمان بن عفان رضي الله عنه المصاحف وأرسلها للأمصار لتوحيد قراءة الأمة ومنع الخلاف."
    },
    {
        "category": "القواعد الفقهية",
        "question": "إذا تعارضت مفسدتان روعي أعظمهما ضرراً بارتكاب أخفهما؛ وهي متفرعة عن قاعدة:",
        "options": ["أ) الضرر يزال", "ب) المشقة تجلب التيسير", "ج) الأمور بمقاصدها"],
        "answer": "أ",
        "explanation": "قاعدة 'يتحمل الضرر الأخف لدفع الضرر الأشد' هي من أهم فروع وتطبيقات قاعدة الضرر يزال."
    },
    {
        "category": "مصطلح الحديث",
        "question": "الحديث الذي سقط من أثناء إسناده راويان فأكثر على التوالي يسمى في علوم الحديث:",
        "options": ["أ) الحديث المنقطع", "ب) الحديث المعضل", "ج) الحديث المعلق"],
        "answer": "ب",
        "explanation": "المعضل ما سقط من إسناده اثنان فصاعداً على التوالي، فإن سقط واحد فهو منقطع."
    },
    {
        "category": "أصول الفقه",
        "question": "استنباط حكم نازلة لا نص فيها بالعدول عن مقتضى قياس جلي إلى قياس خفي لأثر أو مصلحة أقوى يسمى:",
        "options": ["أ) الاستحسان", "ب) الاستصحاب", "ج) سد الذرائع"],
        "answer": "أ",
        "explanation": "الاستحسان هو ترك القياس الجلي لقياس خفي أقوى دلالة وأوفق بروح الشريعة ومصالح العباد."
    },
    {
        "category": "مقاصد الشريعة",
        "question": "من هو العالم الأندلسي الذي يُعد المؤسس الحقيقي والمنظر الأكبر لعلم المقاصد في كتابه 'الموافقات'؟",
        "options": ["أ) الإمام الغزالي", "ب) الإمام الشاطبي", "ج) ابن تيمية"],
        "answer": "ب",
        "explanation": "الإمام أبو إسحاق الشاطبي رحمه الله (ت 790هـ) هو مجدد وصائغ نظرية المقاصد الشرعية في كتابه العظيم 'الموافقات'."
    },
    {
        "category": "القواعد الفقهية",
        "question": "قاعدة 'العادة محكّمة' تفيد بأن العرف السليم معتبر في بناء الأحكام القضائية ما لم:",
        "options": ["أ) يخالف نصاً شرعياً أو أصلاً قطعياً", "ب) يكون العرف محلياً فقط", "ج) يختلف الفقهاء فيه"],
        "answer": "أ",
        "explanation": "العرف المعتبر شرعاً هو العرف المطرد غير المخالف لنصوص الشريعة، فالعرف الفاسد لا عبرة به."
    },
    {
        "category": "الفقه والبيوع",
        "question": "بيع سلعة بالأجل ثم شراؤها نقداً بثمن أقل من المشتري نفسه حيلةً للتوصل إلى الربا يسمى بـ:",
        "options": ["أ) بيع المرابحة", "ب) بيع العينة", "ج) بيع السلم"],
        "answer": "ب",
        "explanation": "بيع العينة من البيوع المنهي عنها لما فيها من التحايل الصريح على الربا باستغلال البيع والشراء صورياً."
    },
    {
        "category": "مصطلح الحديث",
        "question": "رواية الأقران تعني رواية القرين عن قرينه؛ فإذا روى كل منهما عن الآخر سُمي ذلك عند المحدثين بـ:",
        "options": ["أ) المدبّج", "ب) المسلسل", "ج) المتفق والمفترق"],
        "answer": "أ",
        "explanation": "المدبج: هو أن يروي القرينان كلاهما عن الآخر؛ ومثاله رواية عائشة عن أبي هريرة ورواية أبي هريرة عنها."
    },
    {
        "category": "أصول الفقه",
        "question": "رفع الحكم الشرعي بخطاب شرعي متأخر عنه يسمى في علم الأصول بـ:",
        "options": ["أ) التخصيص", "ب) التقييد", "ج) النسخ"],
        "answer": "ج",
        "explanation": "النسخ في الاصطلاح الأصولي هو رفع حكم شرعي سابق بدليل شرعي لاحق تراخى عنه."
    },
    {
        "category": "علوم القرآن",
        "question": "أول ما نزل من القرآن الكريم على الإطلاق باتفاق جمهور المحققين والمفسرين هو:",
        "options": ["أ) سورة الفاتحة", "ب) صدر سورة العلق (اقرأ)", "ج) سورة المدثر"],
        "answer": "ب",
        "explanation": "أول ما نزل قوله تعالى: {اقْرَأْ بِاسْمِ رَبِّكَ الَّذِي خَلَقَ} في غار حراء حين جاءه جبريل عليه السلام."
    },
    {
        "category": "القواعد الفقهية",
        "question": "قاعدة 'المشقة تجلب التيسير' يتفرع عنها ضابط فقهي وأصولي جليل هو:",
        "options": ["أ) إذا ضاق الأمر اتسع", "ب) الغرم بالغنم", "ج) درء المفاسد أولى من جلب المصالح"],
        "answer": "أ",
        "explanation": "إذا ضاق الأمر اتسع، وإذا اتسع ضاق؛ وهي صلب مرونة الشريعة ورحمتها بالمكلفين."
    },
    {
        "category": "الفقه المقارن",
        "question": "كتاب 'الأم' في الفقه وكتاب 'الرسالة' في الأصول هما من أمهات المصنفات الفقهية لإمام مذهب:",
        "options": ["أ) الشافعية", "ب) المالكية", "ج) الحنابلة"],
        "answer": "أ",
        "explanation": "صاحبهما هو الإمام محمد بن إدريس الشافعي رحمه الله، مؤسس علم الأصول ومدون المذهب الشافعي."
    },
    {
        "category": "مصطلح الحديث",
        "question": "الحديث الذي رواه جمع تحيل العادة تواطؤهم على الكذب عن مثلهم ونقلوه عن مشاهدة أو سماع هو:",
        "options": ["أ) الحديث المتواتر", "ب) الحديث المشهور", "ج) الحديث العزيز"],
        "answer": "أ",
        "explanation": "المتواتر يفيد العلم القطعي اليقيني باتفاق العقلاء والمحدثين ولا يحتاج للنظر في عدالة رجاله."
    },
    {
        "category": "أصول الفقه",
        "question": "الحكم على الأشياء والأفعال بالبراءة الأصلية والاستصحاب قبل ورود الشرع أو عند عدم النص يفيد:",
        "options": ["أ) التحريم", "ب) الوقف أو الإباحة الأصلية", "ج) الكراهة"],
        "answer": "ب",
        "explanation": "الأصل في الأشياء النافعة الإباحة استناداً لقوله تعالى: {هُوَ الَّذِي خَلَقَ لَكُم مَّا فِي الأَرْضِ جَمِيعاً}."
    },
    {
        "category": "مقاصد الشريعة",
        "question": "سد الذرائع يعني منع الوسائل المباحة في الأصل إذا كانت تفضي غالباً إلى مفسدة محرمة؛ وهو أصل معتبر عند:",
        "options": ["أ) المالكية والحنابلة خصوصاً وجماهير العلماء", "ب) الظاهرية فقط", "ج) المعتزلة"],
        "answer": "أ",
        "explanation": "سد الذرائع ركيزة كبرى في الفقه المالكي والحنبلي ومقصد شرعي حفظي لمآلات الأفعال."
    },
    {
        "category": "الفقه والمعاملات",
        "question": "عقد يشترى بموجبه شيء موصوف في الذمة مؤجل التسليم بثمن معجل مقبوض في مجلس العقد يسمى:",
        "options": ["أ) بيع السَّلَم", "ب) بيع الإجارة", "ج) بيع الصرف"],
        "answer": "أ",
        "explanation": "السلم رخصة شرعية ثبتت بالسنة والإجماع: 'من أسلف في شيء فليسلف في كيل معلوم ووزن معلوم إلى أجل معلوم'."
    },
    {
        "category": "أصول الفقه",
        "question": "الحكم التكليفي الذي طلب الشارع فعله طلباً غير جازم بحيث يثاب فاعله ولا يعاقب تاركه يسمى:",
        "options": ["أ) الواجب", "ب) المندوب (المستحب)", "ج) المباح"],
        "answer": "ب",
        "explanation": "الأحكام التكليفية الخمسة: الواجب، المندوب، المباح، المكروه، والمحرم."
    },
    {
        "category": "مصطلح الحديث",
        "question": "الحديث الذي رواه اثنان فقط في طبقة من طبقات سنده يسمى عند علماء المصطلح بـ:",
        "options": ["أ) الحديث العزيز", "ب) الحديث الغريب", "ج) الحديث المشهور"],
        "answer": "أ",
        "explanation": "الغريب ما انفرد بروايته شخص واحد، والعزيز ما رواه اثنان ولو في طبقة واحدة، والمشهور ما رواه ثلاثة فأكثر."
    },
    {
        "category": "أصول الفقه",
        "question": "المصالح التي سكت عنها الشرع فلم يشهد لها باعتبار خاص ولا بإلغاء خاص تسمى عند الأصوليين بـ:",
        "options": ["أ) المصالح المرسلة", "ب) المصالح المعتبرة", "ج) المصالح الملغاة"],
        "answer": "أ",
        "explanation": "المصالح المرسلة كالجمع الأول للقرآن وتدوين الدواوين وبناء السجون وضبط المرور لمراعاة مقاصد الشرع العامة."
    },
    {
        "category": "الفقه المقارن",
        "question": "الأئمة الأربعة أصحاب المذاهب الفقهية المتبعة تاريخياً بحسب ترتيبهم الزمني هم:",
        "options": ["أ) أبو حنيفة، مالك، الشافعي، أحمد بن حنبل", "ب) مالك، أبو حنيفة، أحمد، الشافعي", "ج) الشافعي، أبو حنيفة، مالك، أحمد"],
        "answer": "أ",
        "explanation": "الترتيب الزمني لولادتهم: أبو حنيفة (80هـ)، مالك (93هـ)، الشافعي (150هـ)، وأحمد بن حنبل (164هـ)."
    }
]

def get_next_quiz(user_id):
    """محرك ذكي لاختيار الأسئلة بدون تكرار حتى إتمام بنك الأسئلة بالكامل"""
    user_id_str = str(user_id)
    users = load_users()
    user_data = users.get(user_id_str, {})
    answered = user_data.get("answered_quizzes", [])
    
    total_q = len(ISLAMIC_QUIZ_BANK)
    available_indices = [i for i in range(total_q) if i not in answered]
    
    is_completed_round = False
    if not available_indices:
        # انتهت جميع أسئلة البنك! إعادة تهيئة المراجعة من جديد
        answered = []
        available_indices = list(range(total_q))
        is_completed_round = True
        
    chosen_idx = random.choice(available_indices)
    answered.append(chosen_idx)
    
    # حفظ في ملف بيانات الطالب
    if user_id_str in users:
        users[user_id_str]["answered_quizzes"] = answered
        save_users(users)
    else:
        users[user_id_str] = {
            "first_name": "طالب العلم",
            "answered_quizzes": answered
        }
        save_users(users)
        
    return chosen_idx, ISLAMIC_QUIZ_BANK[chosen_idx], len(answered), total_q, is_completed_round

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
# ==========================================
# 🌐 محرك الترجمة الفورية المتعدد الشامل
# ==========================================
def smart_multi_translate(query_text, target_lang='ar'):
    """محرك ترجمة سحابي فائق القوة والاعتمادية بسبع طبقات حماية ومقاومة لحظر السيرفرات"""
    query_clean = query_text.strip()
    if not query_clean:
        return ""

    import requests
    import html
    import re
    import random

    target_lang = target_lang.lower().strip()
    has_arabic = any('\u0600' <= char <= '\u06FF' for char in query_clean)
    src_lang = 'ar' if has_arabic else 'en'
    if src_lang == target_lang:
        target_lang = 'en' if has_arabic else 'ar'

    # قاموس أكاديمي وتعبيري سريع للحالات الطارئة وانقطاع الشبكة
    quick_vocab = {
        "العلم نور": {"en": "Knowledge is light", "fr": "La science est une lumière", "tr": "İlim ışıktır", "ru": "Знание — свет"},
        "العلم نور والجهل ظلام": {"en": "Knowledge is light and ignorance is darkness", "fr": "La connaissance est lumière et l'ignorance est obscurité", "tr": "Bilgi ışıktır ve cehalet karanlıktır", "ru": "Знание — свет, а незнание — тьма"},
        "السلام عليكم": {"en": "Peace be upon you", "fr": "Que la paix soit sur vous", "tr": "Selamün aleyküm", "ru": "Мир вам"},
        "كلية العلوم الإسلامية": {"en": "Faculty of Islamic Sciences", "fr": "Faculté des Sciences Islamiques", "tr": "İslami İlimler Fakültesi", "ru": "Факультет исламских наук"},
        "جامعة الجزائر": {"en": "University of Algiers", "fr": "Université d'Alger", "tr": "Cezayir Üniversitesi", "ru": "Университет Алжира"},
        "شكرا": {"en": "Thank you", "fr": "Merci", "tr": "Teşekkür ederim", "ru": "Спасибо"}
    }
    if query_clean in quick_vocab and target_lang in quick_vocab[query_clean]:
        return quick_vocab[query_clean][target_lang]

    # ترويسة تطبيق Google Translate الرسمي للهواتف (تتجاوز كابتشا مراكز البيانات وسيرفرات Render تماماً)
    mobile_headers = {
        "User-Agent": "GoogleTranslate/6.28.0.05.357594951 (Linux; U; Android 12; Pixel 6)",
        "Accept": "*/*"
    }

    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8,fr;q=0.7"
    }

    # 1. المحرك الأول: Google Translate AT Engine (أسرع وأدق محرك، لا يُحظر إطلاقاً في السيرفرات السحابية)
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "at",
            "sl": "auto",
            "tl": target_lang,
            "dt": "t",
            "q": query_clean
        }
        r = requests.get(url, params=params, headers=browser_headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and isinstance(data[0], list):
                res = "".join(item[0] for item in data[0] if item and len(item) > 0 and item[0])
                if res.strip():
                    return res.strip()
    except Exception as e_at:
        print("AT engine notice:", e_at)

    # 2. المحرك الثاني: Google Translate Dict Builtin (مباشر وفائق السرعة)
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "dict-chrome-ex",
            "sl": "auto",
            "tl": target_lang,
            "dt": "t",
            "q": query_clean
        }
        r = requests.get(url, params=params, headers=browser_headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and isinstance(data[0], list):
                res = "".join(item[0] for item in data[0] if item and len(item) > 0 and item[0])
                if res.strip():
                    return res.strip()
    except Exception as e_dc:
        print("dict-chrome-ex engine notice:", e_dc)

    # 3. المحرك الثالث: MyMemory API المعتمد دولياً
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": query_clean[:500],
            "langpair": f"{src_lang}|{target_lang}"
        }
        r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            t_text = data.get("responseData", {}).get("translatedText")
            if t_text and t_text.strip():
                clean_t = html.unescape(t_text.strip())
                if "MYMEMORY WARNING" not in clean_t.upper() and clean_t.lower() != query_clean.lower():
                    return clean_t
    except Exception as e_mymem:
        print("MyMemory engine notice:", e_mymem)

    # 4. المحرك الرابع: Google Chrome Extension Builtin API
    try:
        url = "https://clients5.google.com/translate_a/t"
        params = {
            "client": "dict-chrome-ex",
            "sl": "auto",
            "tl": target_lang,
            "q": query_clean
        }
        r = requests.get(url, params=params, headers=browser_headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                parts = []
                for item in data:
                    if isinstance(item, list) and item and isinstance(item[0], str):
                        parts.append(item[0])
                    elif isinstance(item, str):
                        parts.append(item)
                if parts:
                    res = " ".join(parts).strip()
                    if res and res.lower() != query_clean.lower():
                        return res
            elif isinstance(data, str) and data.strip():
                return data.strip()
    except Exception as e_c5:
        print("Chrome-ex engine notice:", e_c5)

    # 5. المحرك الخامس: Google Mobile API (tw-ob و gtx)
    try:
        for cl in ["tw-ob", "gtx"]:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": cl,
                "sl": "auto",
                "tl": target_lang,
                "dt": "t",
                "q": query_clean
            }
            r = requests.get(url, params=params, headers=mobile_headers, timeout=4)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list) and isinstance(data[0], list):
                    res = "".join(item[0] for item in data[0] if item and len(item) > 0 and item[0])
                    if res.strip():
                        return res.strip()
    except Exception as e_mob:
        print("Mobile engine notice:", e_mob)

    # 6. المحرك السادس: Google Mobile Web (واجهة هواتف آيفون m.translate)
    try:
        url = "https://translate.google.com/m"
        params = {"sl": "auto", "tl": target_lang, "q": query_clean}
        iphone_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        }
        r = requests.get(url, params=params, headers=iphone_headers, timeout=5)
        if r.status_code == 200:
            m = re.search(r'<div[^>]*class="result-container"[^>]*>(.*?)</div>', r.text, re.DOTALL)
            if m:
                res = html.unescape(m.group(1).strip())
                if res and res.lower() != query_clean.lower():
                    return res
            m2 = re.search(r'<div[^>]*class="t0"[^>]*>(.*?)</div>', r.text, re.DOTALL)
            if m2:
                res = html.unescape(m2.group(1).strip())
                if res and res.lower() != query_clean.lower():
                    return res
    except Exception as e_m:
        print("Google Mobile engine notice:", e_m)

    # 7. المحرك السابع: ذكاء اصطناعي Gemini (إذا توفر المفتاح)
    if GEMINI_API_KEY:
        try:
            lang_labels = {"ar": "العربية", "en": "English", "fr": "Français", "ru": "Русский", "es": "Español", "tr": "Türkçe"}
            g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = "Translate into " + lang_labels.get(target_lang, target_lang) + ". Output ONLY the translation without any notes or explanations:\n\n" + query_clean
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(g_url, json=payload, headers=browser_headers, timeout=6)
            if res.status_code == 200:
                t_gem = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if t_gem and t_gem.lower() != query_clean.lower():
                    return t_gem
        except Exception as e_gem:
            print("Gemini translate notice:", e_gem)

    # 8. المحرك الثامن: deep_translator كاحتياطي أخير
    try:
        from deep_translator import GoogleTranslator
        t_fallback = GoogleTranslator(source='auto', target=target_lang).translate(query_clean)
        if t_fallback and t_fallback.strip():
            return t_fallback.strip()
    except Exception as e_deep:
        print("DeepTranslator notice:", e_deep)

    return "⚠️ تعذر إتمام الترجمة حالياً، يرجى المحاولة بعد قليل."

def get_translation_markup(cache_id):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("🇸🇦 العربية", callback_data=f"tr_ar_{cache_id}"),
        InlineKeyboardButton("🇬🇧 الإنجليزية", callback_data=f"tr_en_{cache_id}"),
        InlineKeyboardButton("🇫🇷 الفرنسية", callback_data=f"tr_fr_{cache_id}"),
        InlineKeyboardButton("🇷🇺 الروسية", callback_data=f"tr_ru_{cache_id}"),
        InlineKeyboardButton("🇹🇷 التركية", callback_data=f"tr_tr_{cache_id}"),
        InlineKeyboardButton("🇪🇸 الإسبانية", callback_data=f"tr_es_{cache_id}")
    )
    return markup


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
    BotCommand("quiz", "بنك الأسئلة والمراجعة الذاتية 🧠"),
    BotCommand("dictionary", "المعجم الفقهي والأصولي 📚"),
    BotCommand("summary", "دليل المذاكرة السريعة 📝"),
    BotCommand("schedule", "جدول المحاضرات 📅"),
    BotCommand("set_schedule", "تعديل الجدول ✏️"),
    BotCommand("translate", "المترجم الفوري لجميع اللغات 🌐"),
    BotCommand("cancel", "إلغاء العمليات الحالية ❌"),
    BotCommand("history", "سجل الملفات 📂")
])

def permanent_keyboard(user_id=None):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🎙️ أرسل تسجيلاً للتفريغ"), KeyboardButton("🧠 بنك الأسئلة والمراجعة الذاتية"))
    markup.row(KeyboardButton("📚 المعجم الفقهي والأصولي"), KeyboardButton("📅 جدولي الدراسي والامتحانات"))
    markup.row(KeyboardButton("🌐 المترجم الفوري الشامل"), KeyboardButton("🌐 لغة تفريغ الصوت"))
    markup.row(KeyboardButton("❌ إلغاء"))
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
# ⚡ معالج الصوتيات فائق السرعة والدقة (فوري للبصمات + تقطيع للمحاضرات)
# ==========================================
def process_audio_streaming(input_filepath, progress_callback=None):
    """
    تفريغ صوتي فائق السرعة والدقة:
    1. المقاطع القصيرة والبصمات الصوتية (أقل من 90 ثانية): تفريغ مباشر وفوري في ثوانٍ معدودة عبر Pydub.
    2. المحاضرات الطويلة (أكثر من 90 ثانية): تقطيع ذكي مع شريط تقدم.
    """
    global listening_language
    
    # 1. محاولة قراءة الصوت عبر Pydub
    sound = None
    try:
        sound = AudioSegment.from_file(input_filepath)
        sound = sound.set_channels(1).set_frame_rate(16000)
    except Exception as e_pydub:
        print("Pydub load notice:", e_pydub)

    duration_sec = sound.duration_seconds if sound else 0
    session_id = f"st_{int(time.time())}_{random.randint(100, 999)}"

    # للمقاطع العادية والبصمات الصوتية (أقل من دقيقة ونصف): تفريغ فوري وسريع في 2-3 ثوانٍ!
    if sound and duration_sec <= 90:
        fast_wav = f"{session_id}_fast.wav"
        try:
            sound.export(fast_wav, format="wav")
            with sr.AudioFile(fast_wav) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language=listening_language)
                if text and text.strip():
                    if listening_language.startswith("ar"):
                        return smart_arabic_stt_corrector(text.strip())
                    return text.strip()
        except sr.UnknownValueError:
            return ""
        except Exception as ex_fast:
            print("Fast STT notice:", ex_fast)
        finally:
            if os.path.exists(fast_wav):
                try:
                    os.remove(fast_wav)
                except Exception:
                    pass

    # للمحاضرات الطويلة (أكثر من 90 ثانية): تقطيع سلس وتفريغ متتابع
    chunk_texts = []

    if sound and duration_sec > 90:
        chunk_ms = 45 * 1000
        total_chunks = int(len(sound) / chunk_ms) + (1 if len(sound) % chunk_ms else 0)
        last_cb = 0

        for idx, start_ms in enumerate(range(0, len(sound), chunk_ms)):
            chunk = sound[start_ms:start_ms + chunk_ms]
            chunk_wav = f"{session_id}_{idx}.wav"
            try:
                chunk.export(chunk_wav, format="wav")
                with sr.AudioFile(chunk_wav) as source:
                    audio_data = recognizer.record(source)
                    part = recognizer.recognize_google(audio_data, language=listening_language)
                    if part and part.strip():
                        chunk_texts.append(part.strip())
            except Exception as ex_c:
                print(f"Chunk {idx} notice:", ex_c)
            finally:
                if os.path.exists(chunk_wav):
                    try:
                        os.remove(chunk_wav)
                    except Exception:
                        pass

            if progress_callback and (time.time() - last_cb > 6 or idx == total_chunks - 1):
                progress_callback(idx + 1, total_chunks)
                last_cb = time.time()

        raw_out = " ".join(chunk_texts)
        if raw_out.strip():
            if listening_language.startswith("ar"):
                return smart_arabic_stt_corrector(raw_out)
            return raw_out

    # محرك FFmpeg الاحتياطي في حال تعذر Pydub
    cmd = [
        "ffmpeg", "-y", "-err_detect", "ignore_err",
        "-i", input_filepath,
        "-vn", "-sn", "-dn",
        "-f", "segment", "-segment_time", "45",
        "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
        f"{session_id}_%04d.wav"
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("FFmpeg segment notice:", e)

    chunk_files = sorted(glob.glob(f"{session_id}_*.wav"))
    if not chunk_files:
        fallback_wav = f"{session_id}_single.wav"
        try:
            subprocess.run([
                "ffmpeg", "-y", "-err_detect", "ignore_err",
                "-i", input_filepath,
                "-vn", "-sn", "-dn",
                "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
                fallback_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(fallback_wav):
                chunk_files = [fallback_wav]
        except Exception:
            pass

    total_chunks = len(chunk_files)
    last_cb = 0
    for idx, chunk_file in enumerate(chunk_files):
        try:
            with sr.AudioFile(chunk_file) as source:
                audio_data = recognizer.record(source)
                part = recognizer.recognize_google(audio_data, language=listening_language)
                if part and part.strip():
                    chunk_texts.append(part.strip())
        except Exception:
            pass
        finally:
            if os.path.exists(chunk_file):
                try:
                    os.remove(chunk_file)
                except Exception:
                    pass

        if progress_callback and (time.time() - last_cb > 6 or idx == total_chunks - 1):
            progress_callback(idx + 1, total_chunks)
            last_cb = time.time()

    raw_text_out = " ".join(chunk_texts)
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
        "3️⃣ **للمذاكرة والاختبار:** اضغط على زر '🧠 بنك الأسئلة والمراجعة الذاتية' للمراجعة الأكاديمية دون تكرار.\n        4️⃣ **للمعجم الأصولي:** اضغط على زر '📚 المعجم الفقهي والأصولي' للقواعد والمقاصد.\n"
        "4️⃣ **للاستفسار الأكاديمي:** اكتب أي سؤال وسيجيبك المساعد العلمي الذكي."
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))

# ==========================================
# 🧠 مسابقات العلوم الإسلامية التفاعلية
# ==========================================
@bot.message_handler(commands=['quiz'])
def start_quiz(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "طالب العلم"

    chosen_idx, selected_quiz, current_num, total_q, is_completed_round = get_next_quiz(user_id)
    USER_QUIZ_STATE[chat_id] = selected_quiz

    options_text = "\n".join(selected_quiz["options"])
    
    congrats_header = ""
    if is_completed_round:
        congrats_header = "🎉 **ما شاء الله تبارك الله! لقد أتممتِ جميع أسئلة البنك بالكامل!** 🌿\n✨ تبدأ الآن جولة مراجعة جديدة لتثبيت الحفظ والمذاكرة:\n\n"

    quiz_msg = (
        f"{congrats_header}"
        f"🧠 **«بنك الأسئلة والمراجعة الذاتية» — السؤال [{current_num} من أصل {total_q}]:**\n"
        f"🏷️ **التخصص:** `{selected_quiz['category']}`\n\n"
        f"❓ **السؤال:**\n{selected_quiz['question']}\n\n"
        f"{options_text}\n\n"
        "👇 *اضغطي على الخيار الصحيح أو اكتبي حرف الإجابة:*"
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("أ", callback_data="quiz_ans_أ"),
        InlineKeyboardButton("ب", callback_data="quiz_ans_ب"),
        InlineKeyboardButton("ج", callback_data="quiz_ans_ج")
    )
    bot.send_message(chat_id, quiz_msg, parse_mode="Markdown", reply_markup=markup)

# ==========================================
# 📚 المعجم الفقهي والأصولي التفاعلي السريع
# ==========================================
# ==========================================
# 🌐 الاستجابة التفاعلية لتغيير لغة الترجمة
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('tr_'))
def handle_translation_language_choice(call):
    parts = call.data.split('_')
    if len(parts) >= 3:
        target_lang = parts[1]
        cache_id = parts[2]
        original_text = TRANSLATION_CACHE.get(cache_id)
        if not original_text:
            bot.answer_callback_query(call.id, "انتهت جلسة هذه الترجمة. اكتب النص مجدداً وسيترجم فوراً.")
            return

        lang_names = {
            "ar": "العربية 🇸🇦",
            "en": "الإنجليزية 🇬🇧",
            "fr": "الفرنسية 🇫🇷",
            "ru": "الروسية 🇷🇺",
            "tr": "التركية 🇹🇷",
            "es": "الإسبانية 🇪🇸"
        }
        target_display = lang_names.get(target_lang, target_lang)
        bot.answer_callback_query(call.id, f"جاري الترجمة إلى {target_display}...")
        
        translated = smart_multi_translate(original_text, target_lang=target_lang)
        msg_text = (
            f"🌐 **الترجمة الفورية إلى {target_display}:**\n\n"
            f"«{translated}»\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 *اضغطي على أي لغة أدناه لتحويل نفس النص إليها فوراً:*"
        )
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=msg_text,
                parse_mode="Markdown",
                reply_markup=get_translation_markup(cache_id)
            )
        except Exception:
            pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('dict_'))
def handle_dictionary_callback(call):
    topic = call.data.split('_')[1]
    
    dict_content = {
        "qawaid": (
            "📖 **القواعد الفقهية الخمس الكبرى وفروعها وتأصيلها:**\n\n"
            "1️⃣ **الأمور بمقاصدها:**\n"
            "   • أصلها حديث: (إنما الأعمال بالنيات).\n"
            "   • فروعها: العبرة في العقود بالمقاصد والمعاني لا بالألفاظ والمباني، والنية تميز العبادة عن العادة.\n\n"
            "2️⃣ **اليقين لا يزول بالشك:**\n"
            "   • أصلها حديث: (فلا ينصرف حتى يسمع صوتاً أو يجد ريحاً).\n"
            "   • فروعها: الأصل بقاء ما كان على ما كان، الأصل براءة الذمة، والأصل في الأشياء الإباحة.\n\n"
            "3️⃣ **المشقة تجلب التيسير:**\n"
            "   • أصلها قوله تعالى: {يُرِيدُ اللَّهُ بِكُمُ الْيُسْرَ وَلاَ يُرِيدُ بِكُمُ الْعُسْرَ}.\n"
            "   • فروعها: إذا ضاق الأمر اتسع، والرخص الشرعية عند الاضطرار والسفر والمرض.\n\n"
            "4️⃣ **الضرر يُزال:**\n"
            "   • أصلها حديث: (لا ضرر ولا ضرار).\n"
            "   • فروعها: درء المفاسد مقدم على جلب المصالح، والضرر لا يزال بمثله، ويتحمل الضرر الخاص لدفع الضرر العام.\n\n"
            "5️⃣ **العادة محكّمة:**\n"
            "   • أصلها حديث: (ما رآه المسلمون حسناً فهو عند الله حسن).\n"
            "   • فروعها: المعروف عرفاً كالمشروط شرطاً، واستعمال الناس حجة يجب العمل بها."
        ),
        "usul": (
            "⚖️ **أدلة أصول الفقه ومناهج الاستدلال:**\n\n"
            "🌟 **أولاً: الأدلة المتفق عليها عند جمهور الأمة:**\n"
            "1. **القرآن الكريم:** الوحي المعجز المتعبد بتلاوته المنقول بالتواتر.\n"
            "2. **السنة النبوية المطهرة:** ما نقل عن رسول الله ﷺ من قول أو فعل أو تقرير.\n"
            "3. **الإجماع:** اتفاق مجتهدي أمة محمد ﷺ في عصر بعد وفاته على حكم شرعي.\n"
            "4. **القياس:** تسوية واقعة لا نص فيها بواقعة ورد فيها نص لحكم لاشتراكهما في العلة.\n\n"
            "🌟 **ثانياً: الأدلة المختلف فيها:**\n"
            "• **الاستحسان:** العدول عن قياس جلي لقياس خفي أقوى، أو استثناء جزئي من قاعدة كلية.\n"
            "• **المصالح المرسلة:** المنافع التي سكت عنها الشرع فلم يشهد لها باعتبار ولا إلغاء.\n"
            "• **الاستصحاب:** استبقاء الحكم الثابت في الماضي ما لم يطرأ عليه مغير ينسخه أو يبطله.\n"
            "• **سد الذرائع:** منع كل وسيلة مباحة إذا غلب على الظن إفضاؤها لمفسدة محرمة.\n"
            "• **عرف أهل المدينة:** أصل معتبر عند الإمام مالك؛ لأنه نقل عملي متواتر عن الصحابة."
        ),
        "hadith": (
            "🔍 **ضوابط الحديث الصحيح وشروط القبول عند المحدثين:**\n\n"
            "يشترط للحكم على الحديث بالصحة لذاته خمسة شروط صارمة:\n"
            "1️⃣ **اتصال السند:** أن يكون كل راوٍ قد سمع من شيخه مباشرة من أول الإسناد إلى منتهاه.\n"
            "2️⃣ **عدالة الرواة:** أن يتصف الراوي بالاستقامة الدينية، والتقوى، والمروءة، والسلامة من الفسق والبدعة.\n"
            "3️⃣ **تمام الضبط:** نوعان: ضبط صدر (حفظه عن ظهر قلب)، أو ضبط كتاب (صيانة كتابه من التحريف والتصحيف).\n"
            "4️⃣ **السلامة من الشذوذ:** ألا يخالف الراوي الثقة المقبول من هو أوثق منه أو أكثر عدداً.\n"
            "5️⃣ **السلامة من العلة القادحة:** خلو الحديث من وصف خفي غامض يقدح في صحته مع أن الظاهر السلامة منه."
        ),
        "maqasid": (
            "🎯 **مقاصد الشريعة الإسلامية ومراتب المصالح:**\n\n"
            "تقسم مصالح الخلق في التشريع الإسلامي إلى ثلاث مراتب متكاملة:\n\n"
            "1️⃣ **المصالح الضرورية (الكليات الخمس):**\n"
            "   ما لا بد منه في قيام مصالح الدين والدنيا، بحيث إذا فُقدت اختل نظام الحياة، وهي:\n"
            "   • حفظ الدين (بالإيمان والجهاد وتشريع الحدود).\n"
            "   • حفظ النفس (بالقصاص والدفاع وتحريم القتل والانتحار).\n"
            "   • حفظ العقل (بطلب العلم وتحريم المسكرات والمخدرات).\n"
            "   • حفظ النسل والعرض (بتشريع النكاح وتحريم الزنا والقذف).\n"
            "   • حفظ المال (بتشريع المعاملات وحرمة السرقة والربا والغصب).\n\n"
            "2️⃣ **المصالح الحاجية:**\n"
            "   ما يحتاج إليه لرفع الضيق والحرج والمشقة غير المحتملة (كالرخص وعقود الإجارة والمعاملات والتداوي).\n\n"
            "3️⃣ **المصالح التحسينية:**\n"
            "   الأخذ بمحاسن العادات ومكارم الأخلاق وآداب السلوك (كالطهارة وستر العورة وآداب الأكل واللباس)."
        ),
        "qiyas": (
            "📐 **أركان القياس الفقهي الأربعة وضوابطه:**\n\n"
            "1️⃣ **الأصل (المقيس عليه):** الواقعة الثابت حكمها بنص قطعي من الكتاب أو السنة أو الإجماع (كالخمر).\n"
            "2️⃣ **الفرع (المقيس):** الواقعة الحادثة أو النازلة التي لا نص خاص فيها يراد إثبات حكمها (كالمخدرات المعاصرة).\n"
            "3️⃣ **حكم الأصل:** الحكم الشرعي التكليفي أو الوضعي الثابت للأصل (كالتحريم المقطوع به للخمر).\n"
            "4️⃣ **العلة:** الوصف الظاهر المنضبط المناسب الجامع بين الأصل والفرع الذي عُلق عليه الحكم (كالإسكار وإذهاب العقل)."
        ),
        "muamalat": (
            "🏛️ **ضوابط المعاملات المالية الإسلامية والبيوع المعاصرة:**\n\n"
            "• **القاعدة الذهبية:** الأصل في جميع العقود والمعاملات والشروط الإباحة والصحة ما لم يرد دليل بالتحريم.\n\n"
            "• **المحرمات الثلاثة الكبرى في المعاملات:**\n"
            "  1. **الربا:** (ربا الفضل: التفاضل في مبادلة الأموال الربوية المتفقة جنساً، وربا النسيئة: التأجيل في قبض أحد البدلين الربويين)، وكل قرض جر نفعاً مشروطاً.\n"
            "  2. **الغرر الفاحش:** الجهالة الكبيرة غير المغتفرة في المبيع أو الثمن أو الأجل المؤدية للنزاع.\n"
            "  3. **الميسر والقمار:** كل معاملة مترددة بين الغنم الصريح والغرم الصريح والمخاطرة المطلقة.\n\n"
            "• **أبرز العقود والبدائل المصرفية الشرعية:**\n"
            "  • **المرابحة للآمر بالشراء:** بيع برأس المال وربح معلوم.\n"
            "  • **الإجارة المنتهية بالتمليك:** عقد إجارة يتضمن وعداً بالهبة أو البيع عند الوفاء بالأقساط.\n"
            "  • **المضاربة والمشاركة:** شراكة في المال والجهد وتوزيع الربح بحسب الاتفاق والخسارة بحسب رأس المال."
        )
    }
    
    reply_info = dict_content.get(topic, "⚠️ لم يتم العثور على محتوى لهذا القسم.")
    back_markup = InlineKeyboardMarkup()
    back_markup.add(InlineKeyboardButton("🔙 العودة لأبواب المعجم", callback_data="dict_menu"))
    bot.edit_message_text(reply_info, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=back_markup)

@bot.callback_query_handler(func=lambda call: call.data == 'dict_menu')
def handle_dict_menu_back(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📖 القواعد الفقهية الخمس", callback_data="dict_qawaid"),
        InlineKeyboardButton("⚖️ أدلة أصول الفقه", callback_data="dict_usul"),
        InlineKeyboardButton("🔍 ضوابط الحديث الصحيح", callback_data="dict_hadith"),
        InlineKeyboardButton("🎯 مقاصد الشريعة الكبرى", callback_data="dict_maqasid"),
        InlineKeyboardButton("📐 أركان وضوابط القياس", callback_data="dict_qiyas"),
        InlineKeyboardButton("🏛️ المعاملات والبيوع المعاصرة", callback_data="dict_muamalat")
    )
    bot.edit_message_text(
        "📚 **المعجم الفقهي والأصولي السريع — مدوّن الإكرام:**\n\n"
        "تفضلي باختيار الباب أو المسألة التي ترغبين في استعراض قواعدها وضوابطها الأكاديمية فوراً:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'quiz_next')
def handle_quiz_next(call):
    start_quiz(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_ans_'))
def handle_quiz_callback(call):
    chat_id = call.message.chat.id
    user_answer = call.data.split('_')[2]
    user_name = call.from_user.first_name or "طالب العلم"
    
    quiz_data = USER_QUIZ_STATE.get(chat_id)
    if not quiz_data:
        bot.answer_callback_query(call.id, "انتهت صلاحية هذا السؤال، اطلب سؤالاً جديداً عبر بنك الأسئلة.")
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

    next_markup = InlineKeyboardMarkup()
    next_markup.add(InlineKeyboardButton("⏭️ السؤال التالي من بنك الأسئلة", callback_data="quiz_next"))
    bot.send_message(chat_id, res_text, parse_mode="Markdown", reply_markup=next_markup)
    bot.answer_callback_query(call.id)
    if chat_id in USER_QUIZ_STATE:
        del USER_QUIZ_STATE[chat_id]

@bot.message_handler(commands=['translate'])
def handle_translate_command(message):
    user_name = message.from_user.first_name or "صديقي"
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip():
        query = parts[1].strip()
        has_arabic = any('\u0600' <= char <= '\u06FF' for char in query)
        target = "en" if has_arabic else "ar"
        target_title = "الإنجليزية 🇬🇧" if has_arabic else "العربية 🇸🇦"
        
        translated = smart_multi_translate(query, target_lang=target)
        cache_id = str(int(time.time()))[-6:]
        TRANSLATION_CACHE[cache_id] = query
        
        bot.reply_to(
            message,
            f"🌐 **الترجمة الفورية إلى {target_title} يا {user_name}:**\n\n"
            f"«{translated}»\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 *اضغطي على أي لغة أدناه لتحويل الترجمة إليها فوراً:*",
            parse_mode="Markdown",
            reply_markup=get_translation_markup(cache_id)
        )
    else:
        USER_TRANSLATE_STATE[message.chat.id] = True
        bot.reply_to(
            message,
            f"🌐 **خدمة المترجم الفوري الشامل يا {user_name}:**\n\n"
            "✏️ أرسلي أي نص الآن وسيقوم البوت بترجمته فوراً، أو اكتبي الأمر متبوعاً بالنص، مثال:\n"
            "`/translate Artificial intelligence in Islamic studies`",
            parse_mode="Markdown",
            reply_markup=permanent_keyboard(message.from_user.id)
        )

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    chat_id = message.chat.id
    if chat_id in USER_QUIZ_STATE:
        del USER_QUIZ_STATE[chat_id]
    bot.send_message(message.chat.id, "✅ تم إلغاء العمليات الحالية والعودة للوضع الطبيعي.", reply_markup=permanent_keyboard(message.from_user.id))

@bot.message_handler(commands=['set_schedule'])
def set_schedule_start(message):
    user_name = message.from_user.first_name or "طالب العلم"
    bot.send_message(
        message.chat.id,
        f"✏️ **تعديل الجدول الدراسي يا {user_name}:**\n\n"
        "تفضل بإرسال جدول محاضراتك الأسبوعي كاملاً في رسالة واحدة (المقاييس، الأوقات، والقاعات):",
        parse_mode="Markdown",
        reply_markup=permanent_keyboard(message.from_user.id)
    )
    def save_schedule_step(m):
        USER_SCHEDULES[m.chat.id] = m.text
        bot.reply_to(
            m,
            f"✅ **ما شاء الله! تم حفظ جدولك الدراسي والامتحانات بنجاح يا {user_name}!** 📅🌿\n\n"
            "يمكنك مراجعته واستعراضه في أي وقت بالضغط على زر **'📅 جدولي الدراسي والامتحانات'**.",
            parse_mode="Markdown",
            reply_markup=permanent_keyboard(m.from_user.id)
        )
    bot.register_next_step_handler(message, save_schedule_step)

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
        if chat_id in USER_TRANSLATE_STATE:
            del USER_TRANSLATE_STATE[chat_id]
        cancel_operation(message)
        return

    # 1. زر تنشيط المترجم الفوري الشامل
    if "المترجم الفوري" in text or text == "ترجمة" or "مترجم" in text:
        USER_TRANSLATE_STATE[chat_id] = True
        if chat_id in USER_QUIZ_STATE:
            del USER_QUIZ_STATE[chat_id]
        bot.reply_to(
            message,
            f"🌐 **المترجم الأكاديمي الفوري لجميع اللغات يا {user_name}:**\n\n"
            "✏️ **تفضلي بكتابة أي جملة أو كلمة أو فقرة الآن مباشرة في الشات:**\n"
            "(سواء كانت بالعربية، الإنجليزية، الفرنسية، الروسية أو غيرها)\n\n"
            "✨ وسيقوم البوت بترجمتها فوراً مع إمكانية تحويلها لأي لغة ترغبين بها بضغطة زر واحدة! 🌍",
            parse_mode="Markdown",
            reply_markup=permanent_keyboard(message.from_user.id)
        )
        return

    # 2. إذا كانت الطالبة داخل وضع المترجم الفوري الشامل وكتبت نصاً
    if USER_TRANSLATE_STATE.get(chat_id):
        # فحص إن ضغطت على زر من الأزرار الأخرى للخروج من وضع الترجمة
        is_other_btn = any(btn in text for btn in [
            "أرسل تسجيلاً", "تفريغ", "بنك الأسئلة", "المراجعة الذاتية", "مسابقة",
            "معجم", "المعجم", "جدول", "الامتحانات", "لغة تفريغ", "تغيير لغة", "لوحة تحكم"
        ])
        if is_other_btn:
            del USER_TRANSLATE_STATE[chat_id]
        else:
            # ترجمة النص فوراً!
            # إذا كان النص يحتوي على أحرف عربية -> نترجم للإنجليزية، وإلا إلى العربية
            has_arabic = any('\u0600' <= char <= '\u06FF' for char in text)
            target = "en" if has_arabic else "ar"
            target_title = "الإنجليزية 🇬🇧" if has_arabic else "العربية 🇸🇦"
            
            translated = smart_multi_translate(text, target_lang=target)
            cache_id = str(int(time.time()))[-6:]
            TRANSLATION_CACHE[cache_id] = text
            
            res_msg = (
                f"🌐 **الترجمة الفورية إلى {target_title}:**\n\n"
                f"«{translated}»\n\n"
                f"━━━━━━━━━━━━━━\n"
                f"💡 *اضغطي على أي لغة أدناه لتحويل الترجمة إليها فوراً:*\n"
                f"*(يمكنكِ كتابة أي جملة أخرى مباشرة وسيترجمها فوراً)*"
            )
            bot.reply_to(message, res_msg, parse_mode="Markdown", reply_markup=get_translation_markup(cache_id))
            return

    # 3. الترجمة المباشرة التلقائية إذا بدأت الجملة بـ 'ترجم' أو 'ترجمة'
    if text.startswith("ترجم ") or text.startswith("ترجم:") or text.startswith("ترجمة:") or text.startswith("ترجم لي"):
        clean_text = text
        for prefix in ["ترجم لي:", "ترجم لي ", "ترجمة:", "ترجم:", "ترجم "]:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):].strip()
                break
        if clean_text:
            has_arabic = any('\u0600' <= char <= '\u06FF' for char in clean_text)
            target = "en" if has_arabic else "ar"
            target_title = "الإنجليزية 🇬🇧" if has_arabic else "العربية 🇸🇦"
            translated = smart_multi_translate(clean_text, target_lang=target)
            cache_id = str(int(time.time()))[-6:]
            TRANSLATION_CACHE[cache_id] = clean_text
            res_msg = (
                f"🌐 **الترجمة الفورية إلى {target_title}:**\n\n"
                f"«{translated}»\n\n"
                f"━━━━━━━━━━━━━━\n"
                f"💡 *اضغطي على أي لغة أدناه لتحويل الترجمة إليها فوراً:*"
            )
            bot.reply_to(message, res_msg, parse_mode="Markdown", reply_markup=get_translation_markup(cache_id))
            return

    # فحص إجابة الكويز إذا كان الطالب في وضع اختبار
    if chat_id in USER_QUIZ_STATE:
        quiz_data = USER_QUIZ_STATE[chat_id]
        correct = quiz_data["answer"]
        
        # إذا ضغط الطالب على أي زر رئيسي من أزرار اللوحة أو كتب تحية أو إلغاء، نلغي حالة الكويز ونمرر الطلب
        is_menu_button = any(btn in text for btn in [
            "أرسل تسجيلاً", "تفريغ", "تسجيل", "بنك الأسئلة", "المراجعة الذاتية", "مسابقة",
            "معجم", "المعجم", "قاموس", "جدول", "الامتحانات", "تغيير لغة", "لغة", "إلغاء", "لوحة تحكم"
        ]) or any(g in text_lower for g in ["سلام", "السلام عليكم", "مرحبا", "أهلا", "صباح", "مساء"])

        if is_menu_button:
            del USER_QUIZ_STATE[chat_id]
            # يكمل الكود تلقائياً لتنفيذ وظيفة الزر دون أن يقول 'إجابة خاطئة'!
        else:
            clean_ans = text.strip().upper().replace("(", "").replace(")", "").replace("الخيار", "").strip()
            if clean_ans in ["أ", "ب", "ج", "A", "B", "C"]:
                is_correct = (clean_ans == correct) or (clean_ans == "A" and correct == "أ") or (clean_ans == "B" and correct == "ب") or (clean_ans == "C" and correct == "ج")
                if is_correct:
                    bot.reply_to(message, f"🎉 أحسنتِ وأصبتِ يا {user_name}! إجابة صحيحة ({correct}).\n\n💡 {quiz_data['explanation']}", reply_markup=permanent_keyboard(message.from_user.id))
                else:
                    bot.reply_to(message, f"❌ للأسف إجابة غير صحيحة يا {user_name}. الإجابة الصائبة هي ({correct}).\n\n💡 {quiz_data['explanation']}", reply_markup=permanent_keyboard(message.from_user.id))
                del USER_QUIZ_STATE[chat_id]
                return
            else:
                del USER_QUIZ_STATE[chat_id]

    # استجابات الأزرار الثابتة
    if "تغيير لغة" in text or "لغة" in text or "لغات" in text:
        bot.reply_to(message, "🌐 اختر لغة تفريغ المقاطع الصوتية من القائمة أدناه:", reply_markup=language_menu())
        return
    elif "معجم" in text or "المعجم" in text or "قاموس" in text:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📖 القواعد الفقهية الخمس", callback_data="dict_qawaid"),
            InlineKeyboardButton("⚖️ أدلة أصول الفقه", callback_data="dict_usul"),
            InlineKeyboardButton("🔍 ضوابط الحديث الصحيح", callback_data="dict_hadith"),
            InlineKeyboardButton("🎯 مقاصد الشريعة الكبرى", callback_data="dict_maqasid"),
            InlineKeyboardButton("📐 أركان وضوابط القياس", callback_data="dict_qiyas"),
            InlineKeyboardButton("🏛️ المعاملات والبيوع المعاصرة", callback_data="dict_muamalat")
        )
        bot.reply_to(
            message,
            "📚 **المعجم الفقهي والأصولي السريع — مدوّن الإكرام:**\n\n"
            "تفضلي باختيار الباب أو المسألة التي ترغبين في استعراض قواعدها وضوابطها الأكاديمية فوراً:",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return
    elif "بنك الأسئلة" in text or "المراجعة الذاتية" in text or "مسابقة" in text or "كويز" in text or "اختبار" in text:
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

    # إلغاء أي حالة ترجمة أو كويز سابقة عند إرسال ملف صوتي
    USER_TRANSLATE_STATE.pop(message.chat.id, None)
    USER_QUIZ_STATE.pop(message.chat.id, None)

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
            mime = (getattr(message.document, 'mime_type', '') or '').lower()
            fname = (getattr(message.document, 'file_name', '') or '').lower()
            valid_exts = ('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.opus', '.wma', '.mp4', '.mkv', '.avi', '.mov', '.webm', '.3gp')
            is_valid_audio_video = mime.startswith('audio/') or mime.startswith('video/') or any(fname.endswith(ext) for ext in valid_exts)
            
            if not is_valid_audio_video:
                bot.reply_to(
                    message,
                    f"📄 **استلمتُ ملف مستند ({message.document.file_name or 'مستند'}) يا {user_name}.**\n\n"
                    "⚠️ **تنبيه:** محرك التفريغ الأكاديمي مخصص فقط للملفات الصوتية ومقاطع الفيديو المسجلة.\n\n"
                    "💡 *يرجى إرسال تسجيل صوتي (بصمة صوتية Voice Note) أو ملف صوتي/مرئي بصيغ (MP3, WAV, OGG, M4A, MP4) وسأتولى تفريغه فوراً!*",
                    parse_mode="Markdown",
                    reply_markup=permanent_keyboard(message.from_user.id)
                )
                return
            media_obj = message.document
            media_name = message.document.file_name if message.document.file_name else "ملف_صوتي"

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
                f"⏳ **يا {user_name}، تم استلام ملف المحاضرة الكبير ({size_mb} ميغابايت). جاري التحميل والبدء في التفريغ...** 🌿",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard(message.from_user.id)
            )
        else:
            working_msg = bot.reply_to(
                message,
                f"⏳ **يا {user_name}، جاري استلام التسجيل وتفريغه فوراً...** 🌿",
                parse_mode="Markdown",
                reply_markup=permanent_keyboard(message.from_user.id)
            )

        # تحميل الملف من تيليجرام بنظام متعدد الحماية
        download_success = False

        try:
            file_info = bot.get_file(media_obj.file_id)
            file_path = file_info.file_path
            
            # 1. إذا كان الملف موجوداً محلياً على القرص (سيرفر تيليجرام المحلي)
            if file_path and os.path.exists(file_path):
                shutil.copy(file_path, temp_input)
                download_success = True
            else:
                # 2. التحميل القياسي المباشر عبر تيليجرام
                try:
                    downloaded_file = bot.download_file(file_path)
                    with open(temp_input, 'wb') as f:
                        f.write(downloaded_file)
                    if os.path.exists(temp_input) and os.path.getsize(temp_input) > 0:
                        download_success = True
                except Exception as ex_down1:
                    print("Download standard notice:", ex_down1)

                # 3. التحميل الاحتياطي المباشر عبر HTTPS الرسمي
                if not download_success and file_path:
                    try:
                        direct_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
                        res = requests.get(direct_url, timeout=35)
                        if res.status_code == 200 and len(res.content) > 0:
                            with open(temp_input, 'wb') as f:
                                f.write(res.content)
                            download_success = True
                    except Exception as ex_direct:
                        print("Download direct notice:", ex_direct)
        except Exception as ex_down:
            print("Download notice:", ex_down)

        if not download_success:
            err_text = (
                f"⚠️ عذراً يا {user_name}، تعذر استلام هذا الملف ({size_mb} ميغابايت) من تيليجرام.\n\n"
                "💡 نصائح هامة ومفيدة لتفريغ المحاضرة الآن:\n"
                "1️⃣ يمكنكِ إرسال التسجيل كـ **رسالة صوتية (Voice Note)** في تيليجرام (حيث يضغطها تيليجرام لأقل من 15MB وتفرغ فوراً).\n"
                "2️⃣ أو تحويل المقطع إلى بصمة صوتية عبر بوت تحويل الصوت المجاني: @VoiceConvertBot"
            )
            try:
                bot.edit_message_text(text=err_text, chat_id=message.chat.id, message_id=working_msg.message_id)
            except Exception:
                bot.send_message(message.chat.id, err_text)
            return

        # دالة رد النداء لتحديث شريط التقدم للطالب للمقاطع الطويلة
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

        # تفريغ المقطع بنظام السرعة العالية
        raw_text = process_audio_streaming(temp_input, progress_callback=update_progress)

        if raw_text and raw_text.strip():
            save_to_history(media_name)
            register_or_update_user(message.from_user, is_transcription=True)
            
            try:
                bot.delete_message(message.chat.id, working_msg.message_id)
            except Exception:
                pass

            words_count = len(raw_text.split())

            # إرسال التفريغ النصي المباشر فوراً في الشات
            if words_count <= 250:
                chat_msg = (
                    f"🎙️ **تفريغ التسجيل الصوتي كاملاً يا {user_name}:**\n\n"
                    f"«{raw_text.strip()}»"
                )
                bot.send_message(message.chat.id, chat_msg, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))
            else:
                preview = " ".join(raw_text.split()[:80]) + "..."
                chat_msg = (
                    f"🎓 **تم تفريغ المحاضرة وتنظيمها بنجاح يا {user_name}!** 🌿\n\n"
                    f"📊 **إحصائيات المحاضرة:** عدد الكلمات: `{words_count}` كلمة تقريباً.\n"
                    f"📅 **التاريخ:** `{datetime.now().strftime('%Y-%m-%d %H:%M')}`\n\n"
                    f"📖 **مقتطف من بداية المحاضرة:**\n«{preview}»\n\n"
                    f"👇 **تجدين أدناه مستند Word الأكاديمي المنسق + النسخة النصية الكاملة:**"
                )
                bot.send_message(message.chat.id, chat_msg, parse_mode="Markdown", reply_markup=permanent_keyboard(message.from_user.id))

            # إنشاء وإرسال مستند Word والملف النصي للمحاضرات
            if words_count > 30:
                try:
                    create_word_document(raw_text, user_name, output_docx)
                    create_text_document(raw_text, user_name, output_txt)

                    if os.path.exists(output_docx):
                        with open(output_docx, "rb") as doc_to_send:
                            bot.send_document(
                                message.chat.id,
                                doc_to_send,
                                caption="📄 **مستند Word الأكاديمي المنسق** ✨",
                                parse_mode="Markdown"
                            )
                    if os.path.exists(output_txt):
                        with open(output_txt, "rb") as txt_to_send:
                            bot.send_document(
                                message.chat.id,
                                txt_to_send,
                                caption="📝 **نسخة نصية خفيفة (.txt)** 🌿",
                                parse_mode="Markdown",
                                reply_markup=permanent_keyboard(message.from_user.id)
                            )
                except Exception as ex_doc:
                    print("Document generation error:", ex_doc)
        else:
            bot.edit_message_text(
                f"⚠️ عذراً يا {user_name}، لم يتم العثور على كلام واضح داخل هذا المقطع الصوتي. يرجى التأكد من وضوح الصوت وإعادة المحاولة.",
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

bot.infinity_polling(timeout=20, long_polling_timeout=20)
