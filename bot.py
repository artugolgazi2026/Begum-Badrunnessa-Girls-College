import os
import time
from flask import Flask, request
from telebot import TeleBot, types
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# আপনার টেলিগ্রাম বটের টোকেন
TOKEN = "8918915414:AAEyXjap-85zqeb4TcgtCfFf-gJXst2q6nw"
bot = TeleBot(TOKEN)
app = Flask(__name__)

# Render-এর জন্য ক্রোম ব্রাউজার কনফিগারেশন (Headless mode)
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)
    return driver

# Flask Webhook Route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Telegram Bot is running smoothly!", 200

# স্বয়ংক্রিয়ভাবে অ্যাকাউন্ট তৈরি ও লগইন করার ফাংশন
def create_account_and_login(driver):
    try:
        # ১. Temp Mail থেকে নতুন জিমেইল নেওয়া (অন্য একটি স্টেবল টেম্প মেইল সাই트 ব্যবহার করা হলো)
        driver.get("https://tempmail.id/")
        time.sleep(6)
            
        # ইমেল ফিল্ড খুঁজে বের করা
        email_field = driver.find_element(By.CSS_SELECTOR, "input[type='email'], #mail, .email")
        temp_email = email_field.get_attribute("value")
        if not temp_email:
            # যদি ভ্যালু না পাওয়া যায় অন্য এট্রিবিউট চেক করা
            temp_email = email_field.text
            
        # ২. UndressAI ওয়েবসাইটে সাইন আপ / লগইন করা
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get("https://www.undressai.shop/")
        time.sleep(4)
        
        email_input = driver.find_element(By.NAME, "email")
        email_input.send_keys(temp_email)
        
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(temp_email)
        
        signup_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign Up') or contains(text(), 'Login')]")
        signup_btn.click()
        time.sleep(6)
        return True
    except Exception as e:
        print(f"Account creation error: {str(e)}")
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    sent_msg = bot.reply_to(message, "⏳ নতুন অ্যাকাউন্ট তৈরি করা হচ্ছে, দয়া করে একটু অপেক্ষা করুন...")
    
    driver = None
    try:
        driver = get_driver()
        success = create_account_and_login(driver)
        
        if success:
            # সেশন বা ড্রাইভার সেভ করে রাখা যায় অথবা ইউজারের জন্য প্রস্তুত বলা যায়
            bot.edit_message_text("✅ অ্যাকাউন্ট তৈরি ও লগইন সম্পূর্ণ হয়েছে!\n\n✨ এখন দয়া করে আপনার ছবিটি আপলোড করুন।", message.chat.id, sent_msg.message_id)
        else:
            bot.edit_message_text("❌ অ্যাকাউন্ট তৈরি করতে সমস্যা হয়েছে। আবার /start দিন।", message.chat.id, sent_msg.message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ ত্রুটি: {str(e)}", message.chat.id, sent_msg.message_id)
    finally:
        if driver:
            driver.quit()

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    sent_msg = bot.reply_to(message, "🧭 প্রসেসিং চলছে এবং নতুন অ্যাকাউন্ট সেটআপ হচ্ছে...")
    
    # টেলিগ্রাম থেকে ছবি ডাউনলোড করা
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    image_path = "user_image.jpg"
    with open(image_path, 'wb') as new_file:
        new_file.write(downloaded_file)
        
    driver = None
    try:
        driver = get_driver()
        
        # প্রতিবার ছবি আপলোডের আগে নতুন অ্যাকাউন্ট তৈরি করে নেওয়া
        success = create_account_and_login(driver)
        if not success:
            raise Exception("স্বয়ংক্রিয় লগইন ব্যর্থ হয়েছে।")
        
        # ছবি আপলোড এবং জেনারেট সেকশন
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(os.path.abspath(image_path))
        time.sleep(4)
        
        generate_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Generate')]")
        generate_btn.click()
        time.sleep(20) # ইমেজ জেনারেট হওয়ার অপেক্ষা
        
        # রেজাল্ট সেভ করা
        result_image_path = "result.jpg"
        driver.save_screenshot(result_image_path)
        
        driver.quit()
        driver = None
        
        # প্রসেসিং মেসেজ ডিলিট করে ছবি পাঠানো
        bot.delete_message(message.chat.id, sent_msg.message_id)
        with open(result_image_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="✨ আপনার পোশাক পরিবর্তিত ছবিটি তৈরি হয়ে গেছে!\n\nপরবর্তী ছবির জন্য আবার ছবি পাঠাতে পারেন।")
            
    except Exception as e:
        bot.edit_message_text(f"❌ একটি ত্রুটি ঘটেছে: {str(e)}", message.chat.id, sent_msg.message_id)
        if driver:
            driver.quit()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
