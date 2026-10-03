import os
import time
from telebot import TeleBot, types
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# আপনার টেলিগ্রাম বটের টোকেন
TOKEN = "8918915414:AAEyXjap-85zqeb4TcgtCfFf-gJXst2q6nw"
bot = TeleBot(TOKEN)

def get_driver():
    options = Options()
    # options.add_argument("--headless") # পিসিতে টেস্ট করার সময় এটি কমেন্ট আউট রাখতে পারেন
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "দয়া করে ছবিটি আপলোড করুন")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    sent_msg = bot.reply_to(message, "🧭 Processing...")
    
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    image_path = "user_image.jpg"
    with open(image_path, 'wb') as new_file:
        new_file.write(downloaded_file)
        
    driver = None
    try:
        driver = get_driver()
        
        # ১. Temp Mail থেকে জিমেইল নেওয়া
        driver.get("https://temp-mail.org/en/")
        time.sleep(5)
        
        try:
            delete_btn = driver.find_element(By.XPATH, "//button[contains(., 'Delete')]")
            delete_btn.click()
            time.sleep(4)
        except Exception:
            pass
            
        email_field = driver.find_element(By.ID, "mail")
        temp_email = email_field.get_attribute("value")
        
        # ২. UndressAI ওয়েবসাইটে সাইন আপ বা লগইন করা
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get("https://www.undressai.shop/")
        time.sleep(4)
        
        email_input = driver.find_element(By.NAME, "email")
        email_input.send_keys(temp_email)
        
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(temp_email)
        
        signup_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign Up')]")
        signup_btn.click()
        time.sleep(6)
        
        # ৩. ছবি আপলোড এবং জেনারেট
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(os.path.abspath(image_path))
        time.sleep(4)
        
        generate_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Generate')]")
        generate_btn.click()
        time.sleep(20)
        
        # ৪. রেজাল্ট সেভ করা
        result_image_path = "result.jpg"
        driver.save_screenshot(result_image_path)
        
        driver.quit()
        driver = None
        
        bot.delete_message(message.chat.id, sent_msg.message_id)
        with open(result_image_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="✨ আপনার পোশাক পরিবর্তিত ছবিটি তৈরি হয়ে গেছে!")
            
    except Exception as e:
        bot.edit_message_text(f"❌ একটি ত্রুটি ঘটেছে: {str(e)}", message.chat.id, sent_msg.message_id)
        if driver:
            driver.quit()

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
