import os
import threading
import time
import requests
from flask import Flask
import telebot
from telebot import types

TOKEN = '8636909610:AAEPBzT3QvTjCgTU6sNoTqnXCqrSyygNorA'
bot = telebot.TeleBot(TOKEN)

# Flask অ্যাপ তৈরি করা (Render-এর জন্য দরকার)
app = Flask(__name__)


@app.route('/')
def home():
  return 'Telegram Result Bot is running successfully!'


# ইউজারদের ডেটা সাময়িকভাবে সংরক্ষণ করার জন্য
user_data = {}


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
  bot.reply_to(
      message,
      'স্বাগতম! টেলিগ্রামের মাধ্যমে রেজাল্ট জানতে /result কমান্ডটি ব্যবহার করুন।',
  )


@bot.message_handler(commands=['result'])
def get_result_start(message):
  chat_id = message.chat.id
  user_data[chat_id] = {}

  markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
  markup.add('dhaka', 'barisal', 'chittagong', 'comilla')
  markup.add('jessore', 'rajshahi', 'sylhet', 'dinajpur', 'madrasah')

  msg = bot.send_message(
      chat_id, 'বোর্ডের নাম সিলেক্ট করুন বা লিখুন (যেমন: dhaka):', reply_markup=markup
  )
  bot.register_next_step_handler(msg, process_board_step)


def process_board_step(message):
  chat_id = message.chat.id
  user_data[chat_id]['board'] = message.text.lower()

  markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
  markup.add('ssc', 'hsc', 'jsc')
  msg = bot.send_message(
      chat_id, 'পরীক্ষার নাম সিলেক্ট করুন (যেমন: ssc):', reply_markup=markup
  )
  bot.register_next_step_handler(msg, process_exam_step)


def process_exam_step(message):
  chat_id = message.chat.id
  user_data[chat_id]['exam'] = message.text.lower()

  msg = bot.send_message(chat_id, 'পাশের বছর লিখুন (যেমন: 2026):')
  bot.register_next_step_handler(msg, process_year_step)


def process_year_step(message):
  chat_id = message.chat.id
  user_data[chat_id]['year'] = message.text

  msg = bot.send_message(chat_id, 'রোল নম্বর লিখুন:')
  bot.register_next_step_handler(msg, process_roll_step)


def process_roll_step(message):
  chat_id = message.chat.id
  user_data[chat_id]['roll'] = message.text

  msg = bot.send_message(chat_id, 'রেজিস্ট্রেশন নম্বর লিখুন:')
  bot.register_next_step_handler(msg, process_reg_step)


def process_reg_step(message):
  chat_id = message.chat.id
  user_data[chat_id]['reg'] = message.text

  bot.send_message(
      chat_id, 'ক্যাপচা লোড করা হচ্ছে, দয়া করে একটু অপেক্ষা করুন...'
  )

  try:
    session = requests.Session()
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like'
            ' Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
        ),
        'Referer': 'https://eboardresults.com/v2/home',
        'Origin': 'https://eboardresults.com',
    }

    session.get('https://eboardresults.com/v2/home', headers=headers)

    timestamp_captcha = str(int(time.time() * 1000))
    captcha_url = (
        f'https://eboardresults.com/v2/captcha?t={timestamp_captcha}'
    )

    captcha_res = session.get(captcha_url, headers=headers)
    captcha_path = f'captcha_{chat_id}.jpg'

    with open(captcha_path, 'wb') as f:
      f.write(captcha_res.content)

    user_data[chat_id]['session'] = session
    user_data[chat_id]['timestamp'] = timestamp_captcha

    with open(captcha_path, 'rb') as photo:
      msg = bot.send_photo(
          chat_id,
          photo,
          caption=(
              'নিচের ছবিতে থাকা **ক্যাপচা কোডটি** দেখে এখানে শুধু সংখ্যাগুলো'
              ' লিখে পাঠান:'
          ),
      )

    if os.path.exists(captcha_path):
      os.remove(captcha_path)

    bot.register_next_step_handler(msg, process_captcha_step)

  except Exception as e:
    bot.send_message(
        chat_id, f'ক্যাপচা লোড করতে সমস্যা হয়েছে: {str(e)}'
    )


def process_captcha_step(message):
  chat_id = message.chat.id
  captcha_text = message.text.strip()
  data = user_data.get(chat_id)

  if not data:
    bot.send_message(
        chat_id, 'সেশন মেয়াদোত্তীর্ণ হয়ে গেছে। দয়া করে আবার /result লিখুন।'
    )
    return

  bot.send_message(chat_id, 'রেজাল্ট যাচাই করা হচ্ছে...')

  payload = {
      'board': data['board'],
      'exam': data['exam'],
      'year': data['year'],
      'result_type': '1',
      'roll': data['roll'],
      'reg': data['reg'],
      'eiin': '',
      'dcode': '',
      'ccode': '',
      'captcha': captcha_text,
  }

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like'
          ' Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
      ),
      'Referer': 'https://eboardresults.com/v2/home',
      'Origin': 'https://eboardresults.com',
  }

  try:
    session = data['session']
    response = session.post(
        'https://eboardresults.com/v2/getres', data=payload, headers=headers
    )
    res_json = response.json()

    if res_json.get('status') == 0:
      res_info = res_json.get('res', {})

      name = res_info.get('name', 'N/A')
      father_name = res_info.get('fname', 'N/A')
      mother_name = res_info.get('mname', 'N/A')
      gpa = res_info.get('res_details', 'N/A')
      institute = res_info.get('inst_name', 'N/A')

      reply_text = (
          f"🎓 **রেজাল্ট বিবরণী**\n\n"
          f"👤 নাম: {name}\n"
          f"👨‍👧 পিতার নাম: {father_name}\n"
          f"👩‍👧 মাতার নাম: {mother_name}\n"
          f"🏫 প্রতিষ্ঠান: {institute}\n"
          f"📊 ফলাফল / GPA: {gpa}\n"
      )
      bot.send_message(chat_id, reply_text, parse_mode='Markdown')
    else:
      bot.send_message(
          chat_id,
          '❌ ভুল ক্যাপচা অথবা তথ্য মিলছে না! আবার নতুন করে চেষ্টার জন্য'
          ' /result লিখুন।',
      )

  except Exception as e:
    bot.send_message(chat_id, f'একটি ত্রুটি ঘটেছে: {str(e)}')


# টেলিগ্রাম বট ব্যাকগ্রাউন্ড থ্রেডে রান করার ফাংশন
def run_bot():
  print('Telegram Bot is starting...')
  bot.infinity_polling()


if __name__ == '__main__':
  # বটকে আলাদা থ্রেডে চালু করা যাতে Flask সার্ভার একসাথে পোর্ট ধরতে পারে
  t = threading.Thread(target=run_bot)
  t.start()

  # Render এর দেওয়া পোর্ট অথবা ডিফল্ট 5000 পোর্টে ফ্লাস্ক সার্ভার রান করা
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
