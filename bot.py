import os
import re
import time
import asyncio
import logging
import threading
import requests

from bs4 import BeautifulSoup
from flask import Flask

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)

from telegram.constants import ParseMode

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from html import escape


# ==================================================
# 1. BOT CONFIGURATION
# ==================================================

# Pydroid 3 ব্যবহার করলে এখানে নতুন BotFather Token বসাও।
# Render ব্যবহার করলে TOKEN Environment Variable থেকে নেবে।

TOKEN = os.getenv(
    "TOKEN",
    "9292780706:AAGZxHc8VNWswzljqREYTFr1_8Rnbe3qVg8"
)

BASE_URL = "https://hscresult.bise-ctg.gov.bd"

REFERER = (
    BASE_URL +
    "/h22_31_x1_26/individual/index.php"
)

RESULT_URL = (
    BASE_URL +
    "/h22_31_x1_26/individual/"
    "result_mark_details.php"
)

TIMEOUT = 30
COOLDOWN = 5

user_cooldowns = {}


# ==================================================
# 2. LOGGING
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ==================================================
# 3. FLASK KEEP ALIVE
# ==================================================

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "HSC RESULT 2026 BOT RUNNING!"


@flask_app.route("/health")
def health():
    return {"status": "online"}


def run_flask():

    flask_app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        debug=False,
        use_reloader=False
    )


def keep_alive():

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()


# ==================================================
# 4. WEBSITE HEADERS
# ==================================================

def get_headers():

    return {

        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/156.0.0.0 Safari/537.36"
        ),

        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),

        "Accept-Language": "en-US,en;q=0.9",

        "Cache-Control": "max-age=0",

        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),

        "Origin": BASE_URL,

        "Referer": REFERER,

        "Upgrade-Insecure-Requests": "1"
    }


# ==================================================
# 5. BOARD REQUEST
# ==================================================

def get_result(roll):

    session = requests.Session()

    headers = get_headers()

    try:

        # First GET: Create PHP session

        initial = session.get(
            REFERER,
            headers=headers,
            timeout=TIMEOUT
        )

        logger.info(
            "Initial GET Status: %s",
            initial.status_code
        )

        if initial.status_code != 200:

            logger.error(
                "Index Response: %s",
                initial.text[:1000]
            )

            return None, "INDEX_ERROR"

        # POST: Submit Roll Number

        payload = {
            "roll": roll,
            "button2": ""
        }

        response = session.post(
            RESULT_URL,
            data=payload,
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        logger.info(
            "Board HTTP Status: %s",
            response.status_code
        )

        logger.info(
            "Response URL: %s",
            response.url
        )

        logger.info(
            "Content Type: %s",
            response.headers.get("Content-Type")
        )

        if response.status_code != 200:

            logger.error(
                "Board Error: %s",
                response.text[:1000]
            )

            return None, "HTTP_ERROR"

        if not response.text.strip():

            return None, "EMPTY"

        # Detect website error pages

        if re.search(
            r"<title>\s*404|<h1>\s*Not Found",
            response.text,
            re.IGNORECASE
        ):

            logger.error(
                "Board returned 404 page"
            )

            return None, "NOT_FOUND"

        return response.text, "OK"

    except requests.Timeout:

        logger.exception("Website timeout")

        return None, "TIMEOUT"

    except requests.RequestException:

        logger.exception("Website connection error")

        return None, "NETWORK"

    finally:

        session.close()


# ==================================================
# 6. TEXT CLEANING
# ==================================================

def clean_text(value):

    return re.sub(
        r"\s+",
        " ",
        str(value or "")
    ).strip()


def title_text(value):

    return clean_text(value).title()


def normalize_key(value):

    return re.sub(
        r"[^a-z0-9]",
        "",
        clean_text(value).lower()
    )


# ==================================================
# 7. RESULT PARSER
# ==================================================

def parse_result(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    info = soup.select_one(".info")

    if not info:

        logger.error(
            "Student information section not found"
        )

        return None

    fields = {}

    elements = info.find_all(
        "div",
        recursive=False
    )

    for i in range(0, len(elements) - 1, 2):

        key = clean_text(
            elements[i].get_text(" ", strip=True)
        )

        value = clean_text(
            elements[i + 1].get_text(" ", strip=True)
        )

        if key:

            fields[normalize_key(key)] = value

    def get_field(*names):

        for name in names:

            key = normalize_key(name)

            if key in fields:

                return fields[key]

        return "Not Available"

    # Student information

    name = get_field("Name")

    if name == "Not Available":

        return None

    # Subject-wise marks

    subjects = []

    marks_table = soup.select_one(
        "table.marks"
    )

    if marks_table:

        rows = marks_table.select(
            "tbody tr"
        )

        for row in rows:

            cells = row.find_all(
                "td",
                recursive=False
            )

            if len(cells) < 2:

                continue

            subject_name = clean_text(
                cells[0].get_text(" ", strip=True)
            )

            subject_marks = clean_text(
                cells[1].get_text(" ", strip=True)
            )

            if subject_name and subject_marks:

                subjects.append({

                    "name": subject_name,

                    "marks": subject_marks

                })

    data = {

        "name": title_text(name),

        "father": title_text(
            get_field("Father's Name")
        ),

        "mother": title_text(
            get_field("Mother's Name")
        ),

        "roll": get_field("Roll No"),

        "registration": get_field("Reg. NO"),

        "board": title_text(
            get_field("Board")
        ),

        "group": title_text(
            get_field("Group")
        ),

        "session": get_field("Session"),

        "type": title_text(
            get_field("Type")
        ),

        "result": get_field("Result").upper(),

        "gpa": get_field("GPA"),

        "institute": title_text(
            get_field("Institute")
        ),

        "subjects": subjects

    }

    return data


# ==================================================
# 8. STUDENT INFORMATION MESSAGE
# ==================================================

def format_student_information(data):

    return (

        "🧑‍🎓 STUDENT INFORMATION\n"

        "━━━━━━━━━━━━━━\n\n"

        f"👤 Name: {data['name']}\n"

        f"👨 Father: {data['father']}\n"

        f"👩 Mother: {data['mother']}\n\n"

        "━━━━━━━━━━━━━━\n"

        "📘 HSC RESULT 2026\n"

        "━━━━━━━━━━━━━━\n\n"

        f"🆔 Roll No: {data['roll']}\n"

        f"📄 Registration No: {data['registration']}\n\n"

        f"🏫 Board: {data['board']}\n"

        f"📚 Group: {data['group']}\n\n"

        f"📊 Result: {data['result']}\n"

        f"⭐ GPA: {data['gpa']}\n\n"

        f"🏫 Institute: {data['institute']}"

    )


# ==================================================
# 9. SUBJECT MONOSPACE MARKSHEET
# ==================================================

def format_subject_marks(data):

    if not data["subjects"]:

        return None

    lines = []

    for subject in data["subjects"]:

        name = subject["name"]

        marks = subject["marks"]

        lines.append(
            f"{name} → {marks}"
        )

    subject_text = "\n".join(lines)

    return (

        "📊 <b>SUBJECT-WISE MARKS</b>\n\n"

        "<pre>"

        + escape(subject_text)

        + "</pre>"

    )


# ==================================================
# 10. SEND SUBJECTS WITH COPY CODE
# ==================================================

async def send_subjects(update, data):

    if not data["subjects"]:

        await update.message.reply_text(
            "⚠️ Subject details unavailable."
        )

        return

    # Telegram HTML message limit is 4096 characters.
    # Keep enough space for the HTML wrapper.

    chunks = []
    current_lines = []
    current_length = 0

    for subject in data["subjects"]:

        line = (
            f"{subject['name']} → "
            f"{subject['marks']}"
        )

        line_length = len(line) + 1

        if current_length + line_length > 3500:

            chunks.append(
                "\n".join(current_lines)
            )

            current_lines = []
            current_length = 0

        current_lines.append(line)

        current_length += line_length

    if current_lines:

        chunks.append(
            "\n".join(current_lines)
        )

    for index, chunk in enumerate(chunks):

        heading = (
            "📊 <b>SUBJECT-WISE MARKS</b>\n\n"
            if index == 0
            else "📊 <b>CONTINUED</b>\n\n"
        )

        message = (
            heading
            + "<pre>"
            + escape(chunk)
            + "</pre>"
        )

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML
        )


# ==================================================
# 11. START COMMAND
# ==================================================

async def start(update, context):

    keyboard = [
        ["🚀 Start"]
    ]

    await update.message.reply_text(

        "🏫 CHATTOGRAM EDUCATION BOARD\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "📘 HSC RESULT 2026\n\n"

        "Please send your HSC Roll Number.\n\n"

        "Example: 520081\n\n"

        "📖 Use /help for instructions.",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )

    )


# ==================================================
# 12. HELP COMMAND
# ==================================================

async def help_command(update, context):

    await update.message.reply_text(

        "📘 HSC RESULT 2026 HELP\n\n"

        "1. Press 🚀 Start\n"

        "2. Send your HSC Roll Number\n"

        "3. Wait for the result\n"

        "4. Use Next for the next roll\n\n"

        "Example: 520081"

    )


# ==================================================
# 13. MESSAGE HANDLER
# ==================================================

async def handle_message(update, context):

    if not update.message:

        return

    text = update.message.text.strip()

    user_id = update.effective_user.id

    # Start button

    if text == "🚀 Start":

        await update.message.reply_text(

            "📥 Please send your HSC Roll Number.",

            reply_markup=ReplyKeyboardRemove()

        )

        return

    # Next button

    if text.startswith("➡️ Next"):

        match = re.search(
            r"\d+",
            text
        )

        if not match:

            return

        text = match.group()

    # Roll validation

    if not re.fullmatch(r"[0-9]{4,8}", text):

        await update.message.reply_text(

            "❌ Invalid Roll Number!\n\n"

            "Please send a valid numeric Roll Number."

        )

        return

    # Cooldown

    now = time.monotonic()

    previous = user_cooldowns.get(
        user_id,
        0
    )

    if now - previous < COOLDOWN:

        await update.message.reply_text(
            "⏳ Please wait a few seconds."
        )

        return

    user_cooldowns[user_id] = now

    wait_msg = await update.message.reply_text(

        "🔎 Searching Chattogram Board...\n\n"

        "⏳ Please wait."

    )

    try:

        # Website request in background thread

        html, error = await asyncio.to_thread(
            get_result,
            text
        )

        if error != "OK":

            error_messages = {

                "INDEX_ERROR":
                    "⚠️ Board index page could not be opened.",

                "HTTP_ERROR":
                    "⚠️ Board website returned an HTTP error.",

                "NOT_FOUND":
                    "⚠️ Board URL returned 404 Not Found.",

                "TIMEOUT":
                    "⏳ Board website request timed out.",

                "NETWORK":
                    "🌐 Website connection failed.",

                "EMPTY":
                    "❌ Empty response received."

            }

            await wait_msg.edit_text(
                error_messages.get(
                    error,
                    "⚠️ Unable to retrieve result."
                )
            )

            return

        # Parse response

        data = parse_result(html)

        if not data:

            await wait_msg.edit_text(

                "❌ Result information not found!\n\n"

                "Please check the Board website."

            )

            return

        # Verify Roll Number

        if data["roll"] != text:

            await wait_msg.edit_text(
                "⚠️ Roll Number mismatch!"
            )

            return

        # Delete waiting message

        await wait_msg.delete()

        # Send Student Information normally

        student_message = format_student_information(
            data
        )

        await update.message.reply_text(
            student_message
        )

        # Send ONLY subjects in Monospace Code Box

        await send_subjects(
            update,
            data
        )

        # Next Roll Button

        next_roll = str(
            int(text) + 1
        )

        keyboard = [[
            f"➡️ Next ({next_roll})"
        ]]

        await update.message.reply_text(

            "👉 Next করতে নিচের বাটনে চাপ দাও।",

            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=True
            )

        )

        logger.info(
            "Result successfully sent for Roll: %s",
            text
        )

    except Exception:

        logger.exception(
            "Message handler error"
        )

        try:

            await wait_msg.edit_text(
                "⚠️ Something went wrong. Please try again."
            )

        except Exception:

            pass


# ==================================================
# 14. MAIN
# ==================================================

def main():

    if (
        not TOKEN
        or TOKEN == "PASTE_YOUR_NEW_BOT_TOKEN_HERE"
    ):

        raise ValueError(
            "Please add a new BotFather Token!"
        )

    keep_alive()

    application = (

        ApplicationBuilder()

        .token(TOKEN)

        .build()

    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(

        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )

    )

    print("===================================")
    print("HSC RESULT 2026 BOT STARTED")
    print("CHATTOGRAM EDUCATION BOARD")
    print("===================================")

    application.run_polling(
        drop_pending_updates=True
    )


# ==================================================
# 15. RUN
# ==================================================

if __name__ == "__main__":

    main()
