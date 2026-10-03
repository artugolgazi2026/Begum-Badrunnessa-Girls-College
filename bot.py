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

# একাধিক টেম্প মেইল সাইট থেকে স্বয়ংক্রিয়ভাবে ইমেইল সংগ্রহ করার ফলব্যাক ফাংশন
def get_temp_email(driver):
    sites = [
        {"url": "https://tempmailo.com/", "selector": "input[type='email'], #mail, .email"},
        {"url": "https://tempmail.id/", "selector": "input[type='email'], #mail, .email"},
        {"url": "https://10minutemail.com/", "selector": "input[type='email'], #mail, #mail_address"}
    ]
    
    for site in sites:
        try:
            print(f"Trying to fetch email from: {site['url']}")
            driver.get(site["url"])
            time.sleep(6)
            
            email_field = driver.find_element(By.CSS_SELECTOR, site["selector"])
            temp_email = email_field.get_attribute("value") or email_field.text
            
            if temp_email and "@" in temp_email:
                print(f"Successfully got email: {temp_email}")
                return temp_email
        except Exception as e:
            print(f"Failed with {site['url']}: {str(e)}")
            continue
            
    return None

# অ্যাকাউন্ট তৈরি ও লগইন করার মূল ফাংশন
def create_account_and_login(driver):
    try:
        temp_email = get_temp_email(driver)
        if not temp_email:
            raise Exception("কোনো টেম্প মেইল সাইট থেকে ইমেল পাওয়া যায়নি!")
            
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
    sent_msg = bot.reply_to(message, "⏳ ব্যাকআপ সার্ভার থেকে নতুন অ্যাকাউন্ট তৈরি করা হচ্ছে, দয়া করে একটু অপেক্ষা করুন...")
    
    driver = None
    try:
        driver = get_driver()
        success = create_account_and_login(driver)
        
        if success:
            bot.edit_message_text("✅ অ্যাকাউন্ট তৈরি ও লগইন সফল হয়েছে!\n\n✨ এখন দয়া করে আপনার ছবিটি আপলোড করুন।", message.chat.id, sent_msg.message_id)
        else:
            bot.edit_message_text("❌ অ্যাকাউন্ট তৈরি করতে সমস্যা হয়েছে। আবার /start দিন।", message.chat.id, sent_msg.message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ ত্রুটি: {str(e)}", message.chat.id, sent_msg.message_id)
    finally:
        if driver:
            driver.quit()

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    sent_msg = bot.reply_to(message, "🧭 নতুন অ্যাকাউন্ট সেটআপ করে ছবি প্রসেস করা হচ্ছে...")
    
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    image_path = "user_image.jpg"
    with open(image_path, 'wb') as new_file:
        new_file.write(downloaded_file)
        
    driver = None
    try:
        driver = get_driver()
        
        success = create_account_and_login(driver)
        if not success:
            raise Exception("স্বয়ংক্রিয় লগইন ব্যর্থ হয়েছে।")
        
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(os.path.abspath(image_path))
        time.sleep(4)
        
        generate_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Generate')]")
        generate_btn.click()
        time.sleep(20)
        
        result_image_path = "result.jpg"
        driver.save_screenshot(result_image_path)
        
        driver.quit()
        driver = None
        
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
