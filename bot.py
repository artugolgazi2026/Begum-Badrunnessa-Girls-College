import time
import random
import string
import requests
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "8918915414:AAFLzvQJNY9a-oSaJo_GfhA08CCLpLIznDU"
BASE_URL = "https://www.undressai.shop"
GENERATE_URL = f"{BASE_URL}/api/generate"

# কনভার্সেশন স্টেটসমূহ
WAITING_FOR_EMAIL_INPUT, WAITING_FOR_COOKIE_INPUT, WAITING_FOR_IMAGE = range(3)

# Flask অ্যাপ ইনিশিয়ালাইজেশন
app_flask = Flask(__name__)

# র‍্যান্ডম টেম্পোরারি জিমেইল জেনারেটর ফাংশন
def generate_random_email():
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{random_str}@aminavin.com"

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    generated_email = generate_random_email()
    context.user_data["temp_email"] = generated_email
    
    msg_text = (
        "✉️ <b>নতুন টেম্পোরারি জিমেইল প্রস্তুত!</b>\n\n"
        "১. নিচের জিমেইলটির ওপর এক ক্লিক করে কপি করুন:\n"
        f"<code>{generated_email}</code>\n\n"
        "২. এখন নিচের লিংকে ক্লিক করে ওয়েবসাইটে যান এবং এই জিমেইল দিয়ে একটি অ্যাকাউন্ট তৈরি করুন:\n"
        f"🔗 <a href='{BASE_URL}'>ওয়েবসাইটে যান</a>\n\n"
        "৩. অ্যাকাউন্ট তৈরি করার পর ব্রাউজার থেকে আপনার **Session Cookie / Authorization Token** কপি করে এই চ্যাটে পেস্ট করুন:"
    )
    
    await update.message.reply_text(msg_text, parse_mode="HTML", disable_web_page_preview=True)
    return WAITING_FOR_COOKIE_INPUT

# কুকিজ রিসিভ করা
async def receive_cookie_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_cookie = update.message.text.strip()
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/generate",
        "Cookie": user_cookie
    })
    
    context.user_data["session"] = session
    
    await update.message.reply_text(
        "✅ <b>সেশন কুকিজ সফলভাবে যুক্ত হয়েছে!</b>\n\n"
        "দয়া করে এখন যে ছবিটির আন্ডড্রেসিং করতে চান সেটি <b>ফটো (Photo)</b> আকারে পাঠিয়ে দিন:",
        parse_mode="HTML"
    )
    return WAITING_FOR_IMAGE

# ছবি প্রসেস করা
async def handle_image_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    wait_msg = await update.message.reply_text("⏳ আপনার ছবিটি কিউতে (Queue) দেওয়া হয়েছে, প্রসেসিং চলছে...")
    
    try:
        session = context.user_data.get("session", requests.Session())
        files = {"image": ("target.jpg", bytes(photo_bytes), "image/jpeg")}
        
        response = session.post(GENERATE_URL, files=files, timeout=60)
        
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("success") or "promptId" in res_data:
                prompt_id = res_data.get("promptId")
                await wait_msg.edit_text(f"⏳ ছবি প্রসেস হচ্ছে (Prompt ID: {prompt_id})। অনুগ্রহ করে অপেক্ষা করুন...")
                
                time.sleep(10) 
                
                result_url = f"{BASE_URL}/api/result?promptId={prompt_id}"
                result_res = session.get(result_url, timeout=30)
                
                if result_res.status_code == 200 and len(result_res.content) > 1000:
                    await update.message.reply_photo(
                        photo=result_res.content,
                        caption="🎉 আপনার ছবিটি সফলভাবে প্রসেস করা হয়েছে!\n\n🔄 নতুন সেশন শুরু করতে চাইলে আবার /start দিন।"
                    )
                    await wait_msg.delete()
                else:
                    await wait_msg.edit_text("❌ প্রসেসিং এখনো সম্পন্ন হয়নি। আবার /start দিন।")
            else:
                error_msg = res_data.get("message", "Unknown error")
                await wait_msg.edit_text(f"❌ সার্ভার থেকে এরর এসেছে: {error_msg}")
        else:
            await wait_msg.edit_text(f"❌ রিকোয়েস্ট ফেল করেছে। স্ট্যাটাস কোড: {response.status_code}")
            
    except Exception as e:
        await wait_msg.edit_text(f"⚠️ প্রসেসিং ত্রুটি: {e}")
        
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("অপারেশন বাতিল করা হয়েছে। নতুন করে শুরু করতে /start দিন।")
    context.user_data.clear()
    return ConversationHandler.END

# Flask রুট (যাতে ওয়েবসাইট ব্রাউজ করলে একটি স্ট্যাটাস দেখায়)
@app_flask.route("/")
def home():
    return "Telegram Bot with Flask is Running Successfully!"

# টেলিগ্রাম বটের অ্যাপ বিল্ড করার ফাংশন
def setup_telegram_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_COOKIE_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cookie_input)
            ],
            WAITING_FOR_IMAGE: [
                MessageHandler(filters.PHOTO, handle_image_and_process)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    return app

if __name__ == "__main__":
    # টেলিগ্রাম বটকে ব্যাকগ্রাউন্ড থ্রেডে রান করার জন্য
    bot_app = setup_telegram_bot()
    
    def run_bot():
        print("টেলিগ্রাম বট পোলিং মোডে চালু হয়েছে...")
        bot_app.run_polling()

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Flask সার্ভার চালু করা (Render, Heroku বা লোকাল হোস্টের জন্য)
    print("Flask ওয়েব সার্ভার চালু হচ্ছে...")
    app_flask.run(host="0.0.0.0", port=5000)
