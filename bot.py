import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, Response
from threading import Thread

from telegram import (
    Update,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

TOKEN = "8636909610:AAHMczAFyqNEQOSEkdH6hdQs7DdUOW8mmmI"
BASE_URL = "https://everify.bdris.gov.bd/"

# আপনার রেন্ডার বা সার্ভারের ডোমেন লিংক এখানে দিতে হবে (যেমন: https://your-app.onrender.com)
# লোকাল টেস্ট করলে এটি ফাকা রাখতে পারেন বা লোকাল আইপি দিতে পারেন
SERVER_URL = "https://your-app.onrender.com" 

user_data = {}

# ===== FLASK KEEP ALIVE & CAPTCHA VIEW ROUTE =====
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "BDRIS Link Bot is alive!"

# এই রাউটটি ইউজারের নির্দিষ্ট চ্যাট আইডি অনুযায়ী ঠিক সেই মুহূর্তের ক্যাপচা ইমেজ দেখাবে
@app_flask.route('/view_captcha/<int:chat_id>')
def view_captcha(chat_id):
    if chat_id in user_data and "captcha_bytes" in user_data[chat_id]:
        return Response(user_data[chat_id]["captcha_bytes"], mimetype='image/jpeg')
    return "❌ ক্যাপচা পাওয়া যায়নি অথবা সেশন শেষ হয়ে গেছে!", 404

def run():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ===== SAFE GET TABLE VALUE =====
def get_table_value(soup, keyword):
    for row in soup.find_all("tr"):
        cols = row.find_all(["td", "th"])
        for i, col in enumerate(cols):
            if keyword in col.text:
                if i + 1 < len(cols):
                    return cols[i + 1].text.strip()
    return "N/A"

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🔍 জন্ম নিবন্ধন যাচাই"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "আসসালামু আলাইকুম!\nজন্ম নিবন্ধন যাচাই করতে নিচের বাটনে ক্লিক করুন:",
        reply_markup=reply_markup
    )

# ===== HANDLE MESSAGE =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return
    user_id = chat.id

    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()

    if text == "🔍 জন্ম নিবন্ধন যাচাই":
        user_data[user_id] = {"step": "ubrn"}
        await message.reply_text("📥 দয়া করে ১৭ অংকের জন্ম নিবন্ধন নম্বরটি (UBRN) দাও:")
        return

    if user_id not in user_data:
        await message.reply_text("অনুগ্রহ করে শুরু করতে /start বা নিচে বাটনে চাপ দিন।")
        return

    data = user_data[user_id]

    # ধাপ ১: জন্ম নিবন্ধন নম্বর নেওয়া
    if data.get("step") == "ubrn":
        if len(text) != 17 or not text.isdigit():
            await message.reply_text("❌ ভুল নম্বর! সঠিক ১৭ অংকের জন্ম নিবন্ধন নম্বর দিন:")
            return
        
        data["ubrn"] = text
        data["step"] = "dob"
        await message.reply_text("📅 এখন জন্ম তারিখ দাও (ফরম্যাট: YYYY-MM-DD, যেমন: 2010-10-05):")
        return

    # ধাপ ২: জন্ম তারিখ নিয়ে সেশন তৈরি করা এবং ক্যাপচা ইমেজ ফেচ করে নিজস্ব লিংক তৈরি করা
    elif data.get("step") == "dob":
        data["dob"] = text
        
        loading_msg = await message.reply_text("⏳ একটু অপেক্ষা করো, আপনার জন্য সিকিউর সেশন ও ক্যাপচা তৈরি করা হচ্ছে...")

        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": BASE_URL
            }

            res = session.get(BASE_URL, headers=headers)
            soup = BeautifulSoup(res.text, "html.parser")
            token_input = soup.find("input", {"name": "__RequestVerificationToken"})

            if not token_input:
                await loading_msg.delete()
                await message.reply_text("❌ সিকিউরিটি টোকেন পাওয়া যায়নি। আবার চেষ্টা করুন।")
                del user_data[user_id]
                return

            token = token_input.get("value")

            # ওয়েবসাইট থেকে সরাসরি ক্যাপচা ইমেজ বাইট আকারে ডাউনলোড করা
            captcha_res = session.get(BASE_URL + "DefaultCaptcha/Generate", headers=headers)

            if captcha_res.status_code != 200:
                await loading_msg.delete()
                await message.reply_text("❌ ক্যাপচা ইমেজ আনতে সমস্যা হয়েছে।")
                del user_data[user_id]
                return

            # সেশন, টোকেন এবং ক্যাপচা বাইট ডিকশনারিতে সেভ করে রাখা
            data["session"] = session
            data["token"] = token
            data["captcha_bytes"] = captcha_res.content
            data["step"] = "captcha"

            await loading_msg.delete()

            # ইউজারের নিজস্ব ক্যাপচা দেখার লিংক তৈরি করা
            captcha_link = f"{SERVER_URL}/view_captcha/{user_id}"

            await message.reply_text(
                "🔗 **আপনার জন্য ক্যাপচা লিংক তৈরি করা হয়েছে:**\n\n"
                f"১. [এখানে ক্লিক করে আপনার ক্যাপচাটি দেখুন]({captcha_link})\n"
                "২. লিংকে যে ক্যাপচা দেখতে পাবেন, তার উত্তরটি এখানে শুধু সংখ্যায় লিখে পাঠান:",
                parse_mode="Markdown"
            )

        except Exception as e:
            await loading_msg.delete()
            await message.reply_text(f"ত্রুটি ঘটেছে: {str(e)}")
            del user_data[user_id]
        return

    # ধাপ ৩: ক্যাপচার উত্তর নিয়ে ফাইনাল সাবমিট করা (একই সেশন ব্যবহার করায় ১০০% ম্যাচ করবে)
    elif data.get("step") == "captcha":
        captcha_text = text
        loading_msg = await message.reply_text("⏳ তথ্য যাচাই করা হচ্ছে...")

        session = data.get("session")
        token = data.get("token")
        ubrn = data.get("ubrn")
        dob = data.get("dob")

        payload = {
            "__RequestVerificationToken": token,
            "UBRN": ubrn,
            "BirthDate": dob,
            "CaptchaDaText": captcha_text,
            "CaptchaOutputText": captcha_text
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": BASE_URL,
            "Origin": "https://everify.bdris.gov.bd"
        }

        try:
            res = session.post(
                BASE_URL + "UBRNVerification/Search",
                data=payload,
                headers=headers
            )

            html = res.text
            await loading_msg.delete()

            if ubrn in html and ("নিবন্ধিত ব্যক্তির নাম" in html or "Registered Person Name" in html):
                result_soup = BeautifulSoup(html, "html.parser")

                name_bn = get_table_value(result_soup, "নিবন্ধিত ব্যক্তির নাম")
                name_en = get_table_value(result_soup, "Registered Person Name")
                birth_place = get_table_value(result_soup, "জন্মস্থান")
                mother_bn = get_table_value(result_soup, "মাতার নাম")
                father_bn = get_table_value(result_soup, "পিতার নাম")

                reg_date = get_table_value(result_soup, "REGISTRATION DATE")
                reg_office = get_table_value(result_soup, "REGISTRATION OFFICE")
                issue_date = get_table_value(result_soup, "ISSUANCE DATE")

                msg = (
                    "✅ **জন্ম নিবন্ধন সফলভাবে যাচাই করা হয়েছে!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 **নাম (বাংলা):** {name_bn}\n"
                    f"👤 **Name (English):** {name_en}\n"
                    f"🆔 **নম্বর:** {ubrn}\n"
                    f"📅 **জন্ম তারিখ:** {dob}\n\n"
                    f"👩 **মাতার নাম:** {mother_bn}\n"
                    f"👨 **পিতার নাম:** {father_bn}\n"
                    f"📍 **জন্মস্থান:** {birth_place}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "📋 **অতিরিক্ত তথ্যাবলী:**\n"
                    f"🗓 **নিবন্ধন তারিখ:** {reg_date}\n"
                    f"🏢 **নিবন্ধন অফিস:** {reg_office}\n"
                    f"📅 **ইস্যু তারিখ:** {issue_date}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "📌 *Status: Verified from Official Database*"
                )

                await message.reply_text(msg, parse_mode="Markdown")
            else:
                await message.reply_text("❌ ভুল CAPTCHA, জন্ম নিবন্ধন নম্বর বা জন্ম তারিখ! আবার শুরু করতে /start দিন।")

        except Exception as e:
            await loading_msg.delete()
            await message.reply_text(f"সাবমিট করার সময় ত্রুটি: {str(e)}")

        if user_id in user_data:
            del user_data[user_id]

# ===== RUN =====
if __name__ == "__main__":
    keep_alive()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 BDRIS Custom Link Bot Running...")
    app.run_polling()
