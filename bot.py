import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, Response
from threading import Thread
import time

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
# আপনার রেন্ডার সার্ভারের আসল লিংক এখানে দিন
SERVER_URL = "https://begum-badrunnessa-girls-college.onrender.com" 

users = {}

# ===== FLASK KEEP ALIVE & CAPTCHA VIEW ROUTE =====
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Result Bot with Web Captcha is alive!"

# এই রাউটটি ইউজারের নির্দিষ্ট চ্যাট আইডি অনুযায়ী ঠিক সেই মুহূর্তের ক্যাপচা ইমেজ ব্রাউজারে দেখাবে
@app_flask.route('/view_captcha/<int:chat_id>')
def view_captcha(chat_id):
    if chat_id in users and "captcha_bytes" in users[chat_id]:
        return Response(users[chat_id]["captcha_bytes"], mimetype='image/jpeg')
    return "❌ ক্যাপচা পাওয়া যায়নি অথবা সেশন শেষ হয়ে গেছে!", 404

def run():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ================= MAIN MENU =================
def main_menu():
    return ReplyKeyboardMarkup([
        ["🚀 রেজাল্ট বের করুন 🚀"],
        ["⁉️ Help & Info.", "⭐ Rate us"],
        ["📊 Statistics", "🔮 Developer Info."]
    ], resize_keyboard=True)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return
    users[chat.id] = {}
    await update.message.reply_text(
        "🎉 Welcome!\n\nResult দেখতে নিচের বাটনে চাপ দিন 👇",
        reply_markup=main_menu()
    )

# ================= HANDLE MESSAGES =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return
    chat_id = chat.id

    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()

    if chat_id not in users:
        users[chat_id] = {}

    data = users[chat_id]

    if text == "🚀 রেজাল্ট বের করুন 🚀":
        users[chat_id] = {"step": "exam"}
        keyboard = [["JSC/JDC", "SSC/Dakhil"], ["HSC/Alim", "DIBS"]]
        await message.reply_text("📘 Exam নির্বাচন করুন:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    step = data.get("step")

    if step == "exam" or "exam" not in data:
        data["exam"] = text.split("/")[0].lower()
        data["step"] = "year"
        keyboard = [["2026","2025","2024"], ["2023","2022","2021"], ["2020","2019","2018"], ["➡️ Next Page"]]
        await message.reply_text("📅 Year নির্বাচন করুন:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if step == "year" or "year" not in data:
        if "Next" in text:
            await message.reply_text("👉 Older year selection is coming soon!")
            return
        data["year"] = text
        data["step"] = "board"
        keyboard = [["Dhaka","Rajshahi","Cumilla"], ["Chattogram","Sylhet","Barishal"], ["Dinajpur","Jashore","Mymensingh"], ["Madrasha","Technical"]]
        await message.reply_text("🏫 Board নির্বাচন করুন:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if step == "board" or "board" not in data:
        data["board"] = text.lower()
        data["step"] = "roll"
        await message.reply_text("🆔 Roll লিখুন:")
        return

    if step == "roll" or "roll" not in data:
        data["roll"] = text
        data["step"] = "reg"
        await message.reply_text("📄 Registration লিখুন:")
        return

    if step == "reg" or "reg" not in data:
        data["reg"] = text
        
        loading_msg = await message.reply_text("⏳ সিকিউর সেশন ও ক্যাপচা তৈরি করা হচ্ছে...")

        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://eboardresults.com/v2/home",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            }
            
            # হোমপেজ ভিজিট করে কুকি সেটআপ করা
            session.get("https://eboardresults.com/v2/home", headers=headers)
            
            # ক্যাপচা ইমেজ ফেচ করা
            captcha_url = f"https://eboardresults.com/v2/captcha?t={int(time.time() * 1000)}"
            r = session.get(captcha_url, headers=headers)
            
            if r.status_code == 200 and len(r.content) > 100:
                data["session"] = session
                data["captcha_bytes"] = r.content
                data["step"] = "captcha"
                
                await loading_msg.delete()

                # ইউজারের নিজস্ব ক্যাপচা দেখার লিংক তৈরি করা
                captcha_link = f"{SERVER_URL}/view_captcha/{chat_id}"

                await message.reply_text(
                    "🔗 **আপনার জন্য ক্যাপচা লিংক তৈরি করা হয়েছে:**\n\n"
                    f"১. [এখানে ক্লিক করে ক্যাপচাটি দেখুন]({captcha_link})\n"
                    "২. লিংকে যে ক্যাপচা দেখতে পাবেন, তার কোডটি এখানে লিখে পাঠান:",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([["🔄 Reload Captcha"]], resize_keyboard=True)
                )
            else:
                await loading_msg.delete()
                await message.reply_text("❌ ক্যাপচা ইমেজ লোড হয়নি। আবার চেষ্টা করুন।")
                users[chat_id] = {}
        except Exception as e:
            await loading_msg.delete()
            await message.reply_text(f"❌ ত্রুটি ঘটেছে: {str(e)}")
            users[chat_id] = {}
        return

    if text == "🔄 Reload Captcha":
        if chat_id in data and "session" in data:
            loading_msg = await message.reply_text("🔄 নতুন ক্যাপচা লোড করা হচ্ছে...")
            try:
                session = data["session"]
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://eboardresults.com/v2/home"
                }
                captcha_url = f"https://eboardresults.com/v2/captcha?t={int(time.time() * 1000)}"
                r = session.get(captcha_url, headers=headers)
                if r.status_code == 200:
                    data["captcha_bytes"] = r.content
                    await loading_msg.delete()
                    captcha_link = f"{SERVER_URL}/view_captcha/{chat_id}"
                    await message.reply_text(
                        f"🔄 নতুন ক্যাপচা লিংক:\n[এখানে ক্লিক করে ক্যাপচা দেখুন]({captcha_link})\nকোডটি এখানে লিখে পাঠান:",
                        parse_mode="Markdown"
                    )
                else:
                    await loading_msg.delete()
                    await message.reply_text("❌ ক্যাপচা রিলোড করতে সমস্যা হয়েছে।")
            except Exception:
                await loading_msg.delete()
                await message.reply_text("❌ ক্যাপচা রিলোড করতে সমস্যা হয়েছে।")
        return

    if step == "captcha" or "captcha" not in data:
        data["captcha"] = text
        loading_msg = await message.reply_text("⏳ রেজাল্ট যাচাই করা হচ্ছে...")

        payload = {
            "board": data["board"],
            "exam": data["exam"],
            "year": data["year"],
            "result_type": "1",
            "roll": data["roll"],
            "reg": data["reg"],
            "captcha": data["captcha"]
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://eboardresults.com",
            "Referer": "https://eboardresults.com/v2/home",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            res = data["session"].post("https://eboardresults.com/v2/getres", data=payload, headers=headers)
            result = res.json()
            await loading_msg.delete()

            if result.get("status") != 0:
                await message.reply_text("❌ Captcha ভুল অথবা সার্ভার এরর! নতুন ক্যাপচার জন্য লিংক দেওয়া হলো।")
                session = data["session"]
                captcha_url = f"https://eboardresults.com/v2/captcha?t={int(time.time() * 1000)}"
                r = session.get(captcha_url)
                if r.status_code == 200:
                    data["captcha_bytes"] = r.content
                    data["step"] = "captcha"
                    captcha_link = f"{SERVER_URL}/view_captcha/{chat_id}"
                    await message.reply_text(
                        f"🔗 [এখানে ক্লিক করে নতুন ক্যাপচা দেখুন]({captcha_link})",
                        parse_mode="Markdown"
                    )
                return

            info = result["res"]
            gpa = info.get("res_detail","N/A").replace("GPA=","")
            
            sex = str(info.get("sex")).strip().lower()
            gender = "FEMALE" if sex in ["1", "f", "female"] else "MALE" if sex in ["2", "0", "m", "male"] else "UNKNOWN"

            # সাবজেক্ট ওয়াইজ রেজাল্ট ও গ্রেড সাজানো
            subjects_text = ""
            sub_details = info.get("sub_details", [])
            if sub_details:
                subjects_text = "\n📚 <b>SUBJECT-WISE GRADES</b>\n━━━━━━━━━━━━━━━\n"
                for sub in sub_details:
                    sub_name = sub.get("SUB_NAME", "Unknown")
                    sub_grade = sub.get("GRADE", "N/A")
                    subjects_text += f"▪️ {sub_name}: <b>{sub_grade}</b>\n"

            msg = f"""
👨‍🎓 <b>STUDENT INFORMATION</b>
━━━━━━━━━━━━━━━
👤 Name: {info.get('name')}
👨 Father: {info.get('fname')}
👩 Mother: {info.get('mname')}
📅 DOB: {info.get('dob')}
🚻 Gender: {gender}

📘 <b>{data['exam'].upper()} RESULT {data['year']}</b>
━━━━━━━━━━━━━━━
🆔 Roll: {data['roll']}
📄 Reg: {data['reg']}
🏫 Board: {info.get('board_name')}
📊 Result: PASSED
⭐ GPA: {gpa}
🏫 Institute: {info.get('inst_name')}
{subjects_text}
"""
            await message.reply_text(msg, parse_mode="HTML", reply_markup=main_menu())
            users[chat_id] = {}
        except Exception as e:
            await loading_msg.delete()
            await message.reply_text(f"❌ রেজাল্ট আনতে সমস্যা হয়েছে। আবার শুরু করুন। ত্রুটি: {str(e)}")
            users[chat_id] = {}

# ================= RUN =================
if __name__ == "__main__":
    keep_alive()
    print("🚀 BOT WITH WEB CAPTCHA STARTED SUCCESSFULLY ✅")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling()
