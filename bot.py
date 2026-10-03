import os
import requests
from flask import Flask, request as flask_request
from telebot import TeleBot, types

# আপনার টেলিগ্রাম বটের টোকেন
TOKEN = "8918915414:AAEyXjap-85zqeb4TcgtCfFf-gJXst2q6nw"
bot = TeleBot(TOKEN)
app = Flask(__name__)

# Flask Webhook Route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = flask_request.get_data().decode("UTF-8")
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Telegram Bot is running smoothly!", 200

# ফ্রি এপিআই ব্যবহার করে খুব দ্রুত একটি নতুন টেম্প মেইল জেনারেট করার ফাংশন
def generate_fresh_email():
    try:
        # mail.tm এর ফ্রি পাবলিক এপিআই ব্যবহার করে জিমেইল/ইমেল নেওয়া
        response = requests.get("https://api.mail.tm/domains")
        if response.status_code == 200:
            domain = response.json()['hydra:member'][0]['domain']
            # একটি র্যান্ডম ইউজারনেম তৈরি করা
            import random
            import string
            username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            email = f"{username}@{domain}"
            return email
    except Exception as e:
        print(f"API Error: {str(e)}")
    
    # যদি এপিআই কাজ না করে তবে ফলব্যাক হিসেবে একটি ইউনিক টেম্প মেইল ফরম্যাট বা অন্য পদ্ধতি
    import time
    return f"user_{int(time.time())}@1secmail.com"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    email = generate_fresh_email()
    
    # ব্যবহারকারীকে জিমেইল কপি করার মতো করে সুন্দরভাবে পাঠিয়ে দেওয়া
    response_text = (
        "✨ **নতুন অ্যাকাউন্ট সেটআপ করার জন্য জিমেইল প্রস্তুত!**\n\n"
        f"📧 **Email:** `{email}`\n"
        f"🔑 **Password:** `{email}`\n\n"
        "👉 **ধাপসমূহ:**\n"
        "১. উপরের জিমেইলে টাচ করে কপি করুন এবং ওয়েবসাইটের **Sign Up / Login** এ ইমেল ও পাসওয়ার্ড হিসেবে দিন।\n"
        "২. অ্যাকাউন্ট তৈরি হয়ে গেলে আপনার ছবিটি এখানে আপলোড করুন!"
    )
    
    bot.send_message(message.chat.id, response_text, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.reply_to(message, "📥 আপনার ছবি পেয়েছি! ওয়েবসাইট থেকে জেনারেট হয়ে আসলে বট আপনাকে পরবর্তী নতুন জিমেইল পাঠিয়ে দেবে।\n\n*নোট: কাজ শেষে নতুন অ্যাকাউন্টের জন্য আবার /start বা নতুন জিমেইল নিতে পারেন।*")
    
    # পরবর্তী কাজের জন্য সাথে সাথে আরেকটি নতুন জিমেইল জেনারেট করে দিয়ে দেওয়া যাতে ব্যবহারকারী থামতে না হয়
    next_email = generate_fresh_email()
    next_text = (
        "🔄 **পরবর্তী অ্যাকাউন্টের জন্য নতুন জিমেইল:**\n\n"
        f"📧 **Email:** `{next_email}`\n"
        f"🔑 **Password:** `{next_email}`\n\n"
        "👉 আগের অ্যাকাউন্ট দিয়ে কাজ শেষ হলে এই নতুন জিমেইলটি ব্যবহার করুন।"
    )
    bot.send_message(message.chat.id, next_text, parse_mode="Markdown")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
