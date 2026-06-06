import asyncio
import aiohttp
import io
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BufferedInputFile
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from config import BOT_TOKEN, OPENROUTER_API_KEY

# Bot sozlash
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM States
class CVGenerator(StatesGroup):
    entering_category = State()
    entering_name = State()
    entering_education = State()
    entering_direction = State()
    entering_experience = State()
    entering_skills = State()
    entering_languages = State()

# Asosiy menyu
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 CV Tekshirish")],
            [KeyboardButton(text="✍️ CV Yaratish")]
        ],
        resize_keyboard=True
    )

# O'zbek harflarini oddiy lotin harflarga almashtirish (PDF uchun)
def fix_uzbek(text):
    replacements = {
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
        "\u2014": "-", "\u2013": "-", "\u2026": "...",
        # O'zbek maxsus harflarini o'xshash lotin harflarga almashtiramiz
        "o\u2018": "o'", "g\u2018": "g'",
        "O\u2018": "O'", "G\u2018": "G'",
        "\u0490": "G'", "\u0491": "g'",  # Cyrillic G with upturn
        "\u2019": "'",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

# Matnni PDF uchun xavfsiz qilish (ASOSIY TO'G'IRLASH)
def make_pdf_safe(text):
    """
    O'zbek lotin harflarini saqlab, faqat PDF ko'tarolmaydigan
    maxsus Unicode belgilarni almashtiradi
    """
    result = []
    for char in text:
        code = ord(char)
        # Oddiy ASCII harflar - qabul qilamiz
        if code < 128:
            result.append(char)
        # O'zbek lotin harflari va keng tarqalgan Lotin-1 harflar
        elif code < 512:
            result.append(char)
        # Boshqa Unicode - o'chiramiz
        else:
            result.append('?')
    return ''.join(result)

# PDF yaratish funksiyasi (TO'G'IRLANGAN)
def create_pdf(cv_text: str, name: str) -> bytes:
    cv_text = fix_uzbek(cv_text)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=16,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=13,
        spaceAfter=10,
        spaceBefore=15,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        fontName='Helvetica',
        leading=16
    )

    story = []
    lines = cv_text.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue

        # ESKI KOD O'RNIGA - to'g'ri tozalash
        clean_line = make_pdf_safe(line).strip()

        if not clean_line:
            continue

        if any(keyword in clean_line.upper() for keyword in ['REZYUME', 'CURRICULUM VITAE', 'CV']):
            story.append(Paragraph(clean_line, title_style))
        elif clean_line.isupper() and len(clean_line) > 3:
            story.append(Paragraph(clean_line, heading_style))
        else:
            story.append(Paragraph(clean_line, normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()

# OpenRouter AI
async def ask_ai(prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "CV Checker Bot"
    }
    data = {
        "model": "openrouter/auto",
        "messages": [
            {
                "role": "system",
                "content": "Siz professional CV yozuvchi va tekshiruvchi AI assistentsiz. Barcha javoblaringiz O'zbek tilida bo'lsin."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            result = await response.json()
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
            else:
                return f"Xatolik: {result}"

# /start
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Salom! Men AI Resume Checker botman!\n\n"
        "📌 Ikki xizmat taqdim etaman:\n"
        "🔍 CV Tekshirish — CVingizni tahlil qilaman\n"
        "✍️ CV Yaratish — Savol-javob orqali CV yozaman\n\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=main_menu()
    )

# CV Tekshirish rejimi
@dp.message(F.text == "🔍 CV Tekshirish")
async def cv_check_mode(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📄 CV matningizni yuboring!\n\n"
        "Men quyidagilarni tekshiraman:\n"
        "✅ Grammatika\n"
        "✅ Bo'limlar\n"
        "✅ Ball va tavsiyalar",
        reply_markup=ReplyKeyboardRemove()
    )

# CV Yaratish rejimi
@dp.message(F.text == "✍️ CV Yaratish")
async def cv_create_mode(message: types.Message, state: FSMContext):
    await state.set_state(CVGenerator.entering_category)
    await message.answer(
        "✍️ CV Yaratish boshlandi!\n\n"
        "💼 Qaysi soha yoki kasb uchun CV kerak?\n\n"
        "Masalan:\n"
        "• Oshpaz\n"
        "• Shifokor\n"
        "• Python Developer\n"
        "• Haydovchi\n"
        "• O'qituvchi\n\n"
        "Sohangizni yozing:",
        reply_markup=ReplyKeyboardRemove()
    )

# Soha kiritildi
@dp.message(CVGenerator.entering_category)
async def category_entered(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(CVGenerator.entering_name)
    await message.answer(
        f"✅ Soha: {message.text}\n\n"
        "👤 Ismingiz va familiyangizni kiriting:\n"
        "Masalan: Abdullayev Jasur"
    )

# Ism kiritildi
@dp.message(CVGenerator.entering_name)
async def name_entered(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(CVGenerator.entering_education)
    await message.answer(
        "🎓 Ta'lim muassasangizni kiriting:\n\n"
        "Masalan: TATU, 2020-2024\n\n"
        "Agar ta'lim yo'q bo'lsa: 'Maktab' deb yozing"
    )

# Ta'lim kiritildi
@dp.message(CVGenerator.entering_education)
async def education_entered(message: types.Message, state: FSMContext):
    await state.update_data(education=message.text)
    await state.set_state(CVGenerator.entering_direction)
    await message.answer(
        "📚 Mutaxassisligingiz (yo'nalishingiz) ni kiriting:\n\n"
        "Masalan: Kompyuter Injiniringi\n"
        "Yoki: Tibbiyot, Iqtisodiyot, Huquqshunoslik\n\n"
        "Agar yo'nalish yo'q bo'lsa: Yo'q deb yozing"
    )

# Yo'nalish kiritildi
@dp.message(CVGenerator.entering_direction)
async def direction_entered(message: types.Message, state: FSMContext):
    await state.update_data(direction=message.text)
    await state.set_state(CVGenerator.entering_experience)
    await message.answer(
        "💼 Ish tajribangizni kiriting:\n\n"
        "Masalan: ABC kompaniyada 2 yil Python dasturchi\n\n"
        "Agar tajriba yo'q bo'lsa: Tajriba yoq deb yozing"
    )

# Tajriba kiritildi
@dp.message(CVGenerator.entering_experience)
async def experience_entered(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(CVGenerator.entering_skills)
    await message.answer(
        "🛠 Ko'nikmalaringizni kiriting:\n\n"
        "Masalan: Python, Django, SQL, Git\n"
        "Yoki: Milliy taomlar, Xalqaro oshpazlik"
    )

# Ko'nikmalar kiritildi
@dp.message(CVGenerator.entering_skills)
async def skills_entered(message: types.Message, state: FSMContext):
    await state.update_data(skills=message.text)
    await state.set_state(CVGenerator.entering_languages)
    await message.answer(
        "🌐 Til bilimlaringizni kiriting:\n\n"
        "Masalan: O'zbek - ona tili, Ingliz - B2, Rus - A2"
    )

# Tillar kiritildi - CV yaratish
@dp.message(CVGenerator.entering_languages)
async def languages_entered(message: types.Message, state: FSMContext):
    await state.update_data(languages=message.text)
    data = await state.get_data()
    await state.clear()

    await message.answer("⏳ CV yaratilmoqda, biroz kuting...")

    prompt = f"""
Quyidagi malumotlar asosida professional CV yoz.
CV OZBEK TILIDA bolsin, professional formatda yoz.
Hech qanday emoji ishlatma, faqat oddiy matn.
Apostraf belgisi sifatida faqat oddiy (') belgisini ishlatma, o'rniga (`) yoki harf ketma-ketligini ishlat.

Soha/Kasb: {data['category']}
Ism: {data['name']}
Talim muassasasi: {data['education']}
Mutaxassislik: {data['direction']}
Ish tajribasi: {data['experience']}
Konikmalar: {data['skills']}
Til bilimlari: {data['languages']}

Quyidagi formatda yoz:

REZYUME

SHAXSIY MALUMOTLAR
Ism-Familiya: ...
Kasb: ...

TALIM
Talim muassasasi: ...
Mutaxassislik: ...
Oqish yillari: ...

ISH TAJRIBASI
...

KONIKMALAR
...

TIL BILIMLARI
...

CV ni toliq, professional va chiroyli qilib yoz ozbek tilida.
Agar tajriba yoq bolsa, konikma va talimga koprok etibor ber.
"""

    try:
        cv_result = await ask_ai(prompt)
        await message.answer(f"✅ Sizning CVingiz tayyor!\n\n{cv_result}")
        await message.answer("📄 PDF fayl tayyorlanmoqda...")
        pdf_bytes = create_pdf(cv_result, data['name'])
        pdf_file = BufferedInputFile(
            pdf_bytes,
            filename=f"CV_{data['name'].replace(' ', '_')}.pdf"
        )
        await message.answer_document(
            pdf_file,
            caption=f"📄 {data['name']} ning professional CVsi (PDF)"
        )
        await message.answer(
            "🔄 Yana nima qilmoqchisiz?",
            reply_markup=main_menu()
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi: {str(e)}\n\n"
            "Iltimos, qaytadan urinib ko'ring yoki /start bosing."
        )

# CV Tekshirish - matn kelsa
@dp.message()
async def check_cv(message: types.Message):
    cv_text = message.text

    if len(cv_text) < 50:
        await message.answer(
            "⚠️ CV juda qisqa!\n\n"
            "Iltimos, to'liq CV matnini yuboring.\n"
            "Yoki /start bosib menyuga qayting."
        )
        return

    await message.answer("⏳ CV tahlil qilinmoqda, biroz kuting...")

    prompt = f"""
Quyidagi CVni tahlil qil va OZBEK TILIDA javob ber:

CV:
{cv_text}

Quyidagilarni tekshir:
1. Umumiy ball (100 dan)
2. Kuchli tomonlar
3. Kamchiliklar
4. Muhim bolimlar bor-yoqligi (Talim, Tajriba, Konikmalar)
5. Tavsiyalar
"""

    try:
        result = await ask_ai(prompt)
        await message.answer(result)
        await message.answer(
            "🔄 Yana nima qilmoqchisiz?",
            reply_markup=main_menu()
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi: {str(e)}\n\n"
            "Iltimos, qaytadan urinib ko'ring yoki /start bosing."
        )

# Botni ishga tushirish
async def main():
    print("✅ Bot ishga tushdi!")
    print("📌 Bot: @mycv_analyzer_bot")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())