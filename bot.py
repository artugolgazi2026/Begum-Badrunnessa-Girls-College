import os
import io
import re
import time
import requests
import urllib3
from threading import Thread
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ফ্লাস্ক অংশ
app = Flask('')
@app.route('/')
def home(): return "Scanner & Comilla Master Bot is Online!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# বটের টোকেন ও চ্যানেল আইডিগুলো
BOT_TOKEN = "9222118493:AAGc4Fi8IXRyQknNGqwHI0nwEml06KjYyHo"
CTG_CHANNEL_ID = "@SSC_2026_Ctg"        # চট্টগ্রাম বোর্ডের মাস্টার রেজাল্টের চ্যানেল আইডি
COMILLA_CHANNEL_ID = "@SSC_2026_Comilla" # কুমিল্লা বোর্ডের মাস্টার রেজাল্টের আলাদা চ্যানেল আইডি (আপনার ইচ্ছামতো পরিবর্তন করে নিন)

session = requests.Session()
headers_xi = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://billpay.sonalibank.com.bd/XIClassAdmission/Fee/"
}

headers_res = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://billpay.sonalibank.com.bd/BoardRescrutiny/Home/Search"
}

BOARDS = [
    "Dhaka Board", "Barisal Board", "Chattogram Board", 
    "Comilla Board", "Dinajpur Board", "Jessore Board", 
    "Mymensingh Board", "Rajshahi Board", "Sylhet Board", 
    "Madrasah Board", "BTEB"
]

current_search_id = 0
user_modes = {}
user_states = {}
comilla_sessions = {}

# =========================================================
# DATA FETCHING FUNCTIONS
# =========================================================
def get_xi_admission_data(tid):
    url = f"https://billpay.sonalibank.com.bd/XIClassAdmission/Home/Voucher/{tid}"
    try:
        r = session.get(url, headers=headers_xi, timeout=15, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        d = {"id": tid, "date": "N/A", "fee_type": "N/A", "name": "N/A", "contact": "N/A", "roll": "N/A", "board": "N/A", "year": "N/A", "amount": "0.00"}
        tds = soup.find_all("td")
        for i, td in enumerate(tds):
            txt = td.get_text(strip=True).replace(":", "")
            if i+1 < len(tds):
                val = tds[i+1].get_text(strip=True)
                if "Transaction Id" == txt: d["id"] = val
                elif "Date" == txt: d["date"] = val
                elif "Fee Type" == txt: d["fee_type"] = val
                elif "Student Name" == txt: d["name"] = val
                elif "Contact No" == txt: d["contact"] = val
                elif "Roll" == txt: d["roll"] = val
                elif "Board" == txt: d["board"] = val
                elif "Year" == txt: d["year"] = val
                elif "Fee Amount" == txt: d["amount"] = val
        return d
    except: return None

def get_rescrutiny_data(tid):
    url = f"https://billpay.sonalibank.com.bd/BoardRescrutiny/Home/Voucher/{tid}"
    try:
        r = session.get(url, headers=headers_res, timeout=15, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        d = {"id": tid, "date": "N/A", "name": "N/A", "contact": "N/A", "roll": "N/A", "board": "N/A", "year": "N/A", "amount": "0.00"}
        
        txn_match = re.search(r"Transaction\s*Id\s*[:\-]?\s*([A-Za-z0-9]+)", text, re.I)
        if txn_match: d["id"] = txn_match.group(1)
        date_match = re.search(r"Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text, re.I)
        if date_match: d["date"] = date_match.group(1)
        name_match = re.search(r"Name\s*[:\-]?\s*([A-Za-z.\s]+?)(?=\s+Roll|\s+Board|\s+Year)", text, re.I)
        if name_match: d["name"] = name_match.group(1).strip()
        roll_match = re.search(r"Roll\s*[:\-]?\s*(\d+)", text, re.I)
        if roll_match: d["roll"] = roll_match.group(1)
        board_match = re.search(r"Board\s*[:\-]?\s*([A-Za-z]+)", text, re.I)
        if board_match: d["board"] = board_match.group(1)
        year_match = re.search(r"Year\s*[:\-]?\s*(\d{4})", text, re.I)
        if year_match: d["year"] = year_match.group(1)
        mobile_match = re.search(r"(?:Mobile|Mobile\s*No|Phone)\s*[:\-]?\s*(01\d{9})", text, re.I)
        if mobile_match: d["contact"] = mobile_match.group(1)
        amount_match = re.search(r"Fee\s*Amount\s*(?:\(BDT\))?\s*[:\-]?\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
        if amount_match: d["amount"] = amount_match.group(1)
        return d
    except: return None

def fetch_ctg(roll):
    url = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php"
    headers2 = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/"
    }
    try:
        r = requests.post(url, data={"roll": roll, "button2": "Submit"}, headers=headers2, timeout=15, verify=False)
        if r.status_code != 200 or "Name" not in r.text: return None, None
        soup = BeautifulSoup(r.text, "html.parser")
        info = {}
        all_tds = soup.find_all("td")
        for i, td in enumerate(all_tds):
            text = td.get_text(strip=True)
            if "Name" == text: info['name'] = all_tds[i+1].get_text(strip=True)
            elif "Father's Name" == text: info['father'] = all_tds[i+1].get_text(strip=True)
            elif "Mother's Name" == text: info['mother'] = all_tds[i+1].get_text(strip=True)
            elif "Reg. NO" == text: info['reg'] = all_tds[i+1].get_text(strip=True)
            elif "DATE OF BIRTH" == text: info['dob'] = all_tds[i+1].get_text(strip=True)
            elif "Group" == text: info['group'] = all_tds[i+1].get_text(strip=True)
            elif "GPA" in text: info['gpa'] = text.split("=")[-1].strip()
            elif "Institute" == text: info['institute'] = all_tds[i+1].get_text(strip=True)

        subjects = []
        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) == 3 and cols[0].get_text(strip=True).isdigit() and len(cols[0].get_text(strip=True)) == 3:
                subjects.append(f"{cols[0].get_text(strip=True)} → {cols[1].get_text(strip=True)} → {cols[2].get_text(strip=True)}")
        return info, subjects
    except: return None, None

def fetch_comilla_raw(exam: str, roll: str, year: str):
    url = "https://certificate.comillaboard.gov.bd/find/duplicate"
    params = {"exam": exam, "roll": roll, "year": year}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://certificate.comillaboard.gov.bd/",
    }
    try:
        sess = requests.Session()
        sess.get("https://certificate.comillaboard.gov.bd/", headers=headers, timeout=10, verify=False)
        res = sess.get(url, params=params, headers=headers, timeout=15, verify=False)

        if res.status_code != 200: return None
        soup = BeautifulSoup(res.text, "html.parser")

        def get_val(name_attr):
            elem = soup.find("input", {"name": name_attr})
            if elem and elem.get("value"): return elem.get("value").strip()
            elem = soup.find("input", {"id": name_attr})
            if elem and elem.get("value"): return elem.get("value").strip()
            return None

        data = {}
        for row in soup.find_all("div", class_="form-group"):
            label = row.find("label")
            inp = row.find("input")
            if label and inp and inp.get("value"):
                data[label.text.strip()] = inp.get("value").strip()

        name = get_val("name") or data.get("Name")
        if not name: return None

        info = {
            "name": name,
            "father": get_val("father_name") or data.get("Father's Name", "N/A"),
            "mother": get_val("mother_name") or data.get("Mother's Name", "N/A"),
            "reg": get_val("reg_no") or data.get("Registration Number", "N/A"),
            "session": get_val("session") or data.get("Session", "N/A"),
            "dob": get_val("dob") or data.get("Date of Birth", "N/A"),
            "gpa": get_val("gpa") or data.get("GPA", "N/A"),
            "sex": get_val("sex") or data.get("Sex", "N/A")
        }
        return info
    except: return None

# =========================================================
# OUTPUT & NOTIFICATIONS (শুধুমাত্র বটের চ্যাটে পাঠাবে, চ্যানেলে নয়)
# =========================================================
async def process_xi_results(update_or_query, context, data_list, institution_name="N/A"):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    final_output = f"🏛️ <b>XI Admission Fee Result</b>\n\n"
    phones = []
    for i, data in enumerate(data_list, 1):
        final_output += (
            f"🎯 <b>Result {i}</b>\n"
            f"<pre>"
            f"🆔 Transaction Id: {data['id']}\n"
            f"👤 Student Name: {data['name']}\n"
            f"🔢 Roll: {data['roll']}\n"
            f"🏫 Board: {data['board']}\n"
            f"🏫 Institute: {institution_name}\n"
            f"📆 Year: {data['year']}\n"
            f"📳 Contact No: {data['contact']}\n"
            f"📝 Fee Type: {data['fee_type']}\n"
            f"💰 Fee Amount: {data['amount']}\n"
            f"📅 Date: {data['date']}"
            f"</pre>\n\n"
        )
        p = data["contact"].strip()[-11:]
        if len(p) >= 11 and p not in phones: phones.append(p)

    keyboard = []
    for ph in phones:
        keyboard.append([
            InlineKeyboardButton("🟢 WhatsApp", url=f"https://wa.me/88{ph}"),
            InlineKeyboardButton("🔵 Telegram", url=f"https://t.me/+88{ph}")
        ])
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await msg_source.reply_text(final_output, parse_mode="HTML", reply_markup=reply_markup)

async def send_rescrutiny_result(update_or_query, context, data_list, institution_name="N/A"):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    final_output = "🏦 <b>Sonali Bank - Board Rescrutiny Result</b>\n\n"
    phones = []
    for i, data in enumerate(data_list, 1):
        final_output += (
            f"🎯 Result {i}\n"
            f"<pre>"
            f"🆔 Transaction Id: {data['id']}\n"
            f"👤 Student Name : {data['name']}\n"
            f"🔢 Roll         : {data['roll']}\n"
            f"🏫 Board        : {data['board']}\n"
            f"🏫 Institute    : {institution_name}\n"
            f"📆 Year         : {data['year']}\n"
            f"📳 Mobile No    : {data['contact']}\n"
            f"💰 Fee Amount   : {data['amount']} BDT\n"
            f"📅 Date         : {data['date']}"
            f"</pre>\n\n"
        )
        p = data["contact"].strip()[-11:]
        if len(p) >= 11 and p.isdigit() and p not in phones: phones.append(p)

    keyboard = []
    for ph in phones:
        keyboard.append([
            InlineKeyboardButton("🟢 WhatsApp", url=f"https://wa.me/88{ph}"),
            InlineKeyboardButton("🔵 Telegram", url=f"https://t.me/+88{ph}")
        ])
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await msg_source.reply_text(final_output, parse_mode="HTML", reply_markup=reply_markup)

async def send_ssc_result(update_or_query, context, roll, marksheet):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    info, subjects = marksheet
    sub_text = "\n".join(subjects)
    final_msg = (
        f"🧑‍🎓 <b>STUDENT INFORMATION</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"👤 Name: {info.get('name')}\n"
        f"👨 Father: {info.get('father')}\n"
        f"👩 Mother: {info.get('mother')}\n"
        f"📅 Date of Birth: {info.get('dob')}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📘 <b>SSC RESULT 2026</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🔢 Roll No: {roll}\n"
        f"📄 Registration No: {info.get('reg')}\n"
        f"🏫 Board: CHATTOGRAM\n"
        f"📚 Group: {info.get('group')}\n"
        f"📊 Result: GPA: {info.get('gpa')}\n\n"
        f"🏫 Institute: {info.get('institute')}\n\n"
        f"📊 <b>SUBJECTS</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<pre>{sub_text}</pre>"
    )
    await msg_source.reply_text(final_msg, parse_mode="HTML")

# =========================================================
# CTG & COMILLA MASTER OUTPUT (শুধুমাত্র এগুলো চ্যানেলে ব্যাকআপ যাবে)
# =========================================================
async def send_master_result(update_or_query, context, sonali_data, marksheet, fee_source_title):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    info, subjects = marksheet
    sub_text = "\n".join(subjects)

    final_output = (
        f"🧑‍🎓 <b>STUDENT INFORMATION ({fee_source_title})</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🆔 Transaction Id: {sonali_data['id']}\n"
        f"👤 Name: {info.get('name')}\n"
        f"👨 Father: {info.get('father')}\n"
        f"👩 Mother: {info.get('mother')}\n"
        f"📅 Date of Birth: {info.get('dob')}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📘 <b>SSC RESULT 2026 (CHATTOGRAM)</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🔢 Roll No: {sonali_data['roll']}\n"
        f"📄 Registration No: {info.get('reg')}\n"
        f"🏫 Board: CHATTOGRAM\n"
        f"📚 Group: {info.get('group')}\n"
        f"📆 Year: {sonali_data['year']}\n"
        f"📊 Result: GPA: {info.get('gpa')}\n"
        f"📳 Contact No: {sonali_data['contact']}\n"
        f"💰 Fee Amount: {sonali_data.get('amount', 'N/A')}\n"
        f"📅 Date: {sonali_data['date']}\n\n"
        f"🏫 Institute: {info.get('institute')}\n\n"
        f"📊 <b>SUBJECTS</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<pre>{sub_text}</pre>"
    )

    p = sonali_data["contact"].strip()[-11:]
    keyboard = []
    if len(p) >= 11 and p.isdigit():
        keyboard.append([
            InlineKeyboardButton("🟢 WhatsApp", url=f"https://wa.me/88{p}"),
            InlineKeyboardButton("🔵 Telegram", url=f"https://t.me/+88{p}")
        ])
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # ব্যবহারকারীকে দেখাবে
    await msg_source.reply_text(final_output, parse_mode="HTML", reply_markup=reply_markup)
    # চট্টগ্রাম বোর্ডের মাস্টার রেজাল্ট চ্যানেলে পাঠাবে
    try:
        await context.bot.send_message(chat_id=CTG_CHANNEL_ID, text=final_output, parse_mode="HTML", reply_markup=reply_markup)
    except Exception: pass

async def send_comilla_master_result(update_or_query, context, sonali_data, comilla_info, fee_source_title):
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query

    final_output = (
        f"🎓 কুমিল্লা বোর্ড শিক্ষার্থীর তথ্য (SSC - 2026) [{fee_source_title}]\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Transaction Id: {sonali_data['id']}\n"
        f"👤 Name: {comilla_info.get('name')}\n"
        f"👨‍👦 Father: {comilla_info.get('father')}\n"
        f"👩‍👦 Mother: {comilla_info.get('mother')}\n"
        f"🆔 Roll No: {sonali_data['roll']}\n"
        f"📝 Registration: {comilla_info.get('reg')}\n"
        f"📳 Contact No: {sonali_data['contact']}\n"
        f"🎂 Date of Birth: {comilla_info.get('dob')}\n"
        f"📅 Session: {comilla_info.get('session')}\n"
        f"📆 Year: {comilla_info.get('year')}\n"
        f"⚧️ Sex: {comilla_info.get('sex')}\n"
        f"📊 GPA: {comilla_info.get('gpa')}\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )

    p = sonali_data["contact"].strip()[-11:]
    keyboard = []
    if len(p) >= 11 and p.isdigit():
        keyboard.append([
            InlineKeyboardButton("🟢 WhatsApp", url=f"https://wa.me/88{p}"),
            InlineKeyboardButton("🔵 Telegram", url=f"https://t.me/+88{p}")
        ])
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # ব্যবহারকারীকে দেখাবে
    await msg_source.reply_text(final_output, parse_mode="HTML", reply_markup=reply_markup)
    # কুমিল্লা বোর্ডের মাস্টার রেজাল্ট নির্দিষ্ট ব্যাকআপ চ্যানেলে পাঠাবে
    try:
        await context.bot.send_message(chat_id=COMILLA_CHANNEL_ID, text=final_output, parse_mode="HTML", reply_markup=reply_markup)
    except Exception: pass

# =========================================================
# SEARCH RUNNER
# =========================================================
async def run_search(update_or_query, context, s_r, e_r, mode):
    global current_search_id
    this_id = current_search_id 
    
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    status_msg = await msg_source.reply_text("⏳ <b>Scanning...</b>", parse_mode="HTML")
    context.user_data["current_end"] = e_r
    
    found_students = 0
    total_range = e_r - s_r + 1
    
    chat_id = msg_source.chat.id
    state_info = user_states.get(chat_id, {})
    selected_board = state_info.get("board", "ALL")
    institution_name = state_info.get("institute", "N/A")

    selected_board_keyword = selected_board.split()[0].upper() if selected_board != "ALL" else ""

    for i, roll in enumerate(range(s_r, e_r + 1), 1):
        if this_id != current_search_id: return 

        try:
            if mode == "recheck":
                if i == 1: session.get("https://billpay.sonalibank.com.bd/BoardRescrutiny/Home/Search", headers=headers_res, verify=False)
                search_url = f"https://billpay.sonalibank.com.bd/BoardRescrutiny/Home/Search?searchStr={roll}"
                r = session.get(search_url, headers=headers_res, timeout=12, verify=False)
                ids = re.findall(r'/BoardRescrutiny/Home/Voucher/([A-Za-z0-9_-]+)', r.text, re.I)

                if ids:
                    v_list = []
                    for tid in set(ids):
                        d = get_rescrutiny_data(tid)
                        if d and d["name"] != "N/A":
                            if selected_board == "ALL": v_list.append(d)
                            else:
                                server_board = d["board"].upper()
                                if not server_board or server_board == "N/A" or selected_board_keyword in server_board or server_board in selected_board_keyword:
                                    v_list.append(d)
                    if v_list:
                        found_students += 1
                        await send_rescrutiny_result(update_or_query, context, v_list, institution_name)

            elif mode == "sonali":
                if i == 1: session.get("https://billpay.sonalibank.com.bd/XIClassAdmission/Fee/", headers=headers_xi, verify=False)
                search_url = f"https://billpay.sonalibank.com.bd/XIClassAdmission/Home/Search?searchStr={roll}"
                r = session.get(search_url, headers=headers_xi, timeout=10, verify=False)
                ids = re.findall(r'Voucher/([A-Za-z0-9\-]+)', r.text)

                if ids:
                    v_list = []
                    for tid in set(ids):
                        d = get_xi_admission_data(tid)
                        if d and d["name"] != "N/A":
                            if selected_board == "ALL": v_list.append(d)
                            else:
                                server_board = d["board"].upper()
                                if not server_board or server_board == "N/A" or selected_board_keyword in server_board or server_board in selected_board_keyword:
                                    v_list.append(d)
                    if v_list:
                        found_students += 1
                        await process_xi_results(update_or_query, context, v_list, institution_name)

            elif mode == "ctg_ssc":
                marksheet = fetch_ctg(str(roll))
                if marksheet and marksheet[0]:
                    found_students += 1
                    await send_ssc_result(update_or_query, context, roll, marksheet)

            elif mode == "ctg_master":
                matched_sonali = None
                fee_source_title = ""

                r_xi = session.get(f"https://billpay.sonalibank.com.bd/XIClassAdmission/Home/Search?searchStr={roll}", headers=headers_xi, timeout=8, verify=False)
                xi_ids = re.findall(r'Voucher/([A-Za-z0-9\-]+)', r_xi.text)
                for tid in set(xi_ids):
                    d = get_xi_admission_data(tid)
                    if d and d["name"] != "N/A" and d["board"].strip().lower() in ["chittagong", "chattogram"]:
                        matched_sonali = d
                        fee_source_title = "XI Admission"
                        break

                if not matched_sonali:
                    r_res = session.get(f"https://billpay.sonalibank.com.bd/BoardRescrutiny/Home/Search?searchStr={roll}", headers=headers_res, timeout=8, verify=False)
                    res_ids = re.findall(r'/BoardRescrutiny/Home/Voucher/([A-Za-z0-9_-]+)', r_res.text, re.I)
                    for tid in set(res_ids):
                        d = get_rescrutiny_data(tid)
                        if d and d["name"] != "N/A" and d["board"].strip().upper() in ["CHITTAGONG", "CHATTOGRAM"]:
                            matched_sonali = d
                            fee_source_title = "Board Rescrutiny"
                            break

                if matched_sonali:
                    marksheet = fetch_ctg(str(matched_sonali["roll"]))
                    if marksheet and marksheet[0]:
                        found_students += 1
                        await send_master_result(update_or_query, context, matched_sonali, marksheet, fee_source_title)

            elif mode == "comilla_master":
                matched_sonali = None
                fee_source_title = ""

                r_xi = session.get(f"https://billpay.sonalibank.com.bd/XIClassAdmission/Home/Search?searchStr={roll}", headers=headers_xi, timeout=8, verify=False)
                xi_ids = re.findall(r'Voucher/([A-Za-z0-9\-]+)', r_xi.text)
                for tid in set(xi_ids):
                    d = get_xi_admission_data(tid)
                    if d and d["name"] != "N/A" and d["board"].strip().lower() in ["comilla", "cumilla", "কুমিল্লা"]:
                        matched_sonali = d
                        fee_source_title = "XI Admission"
                        break

                if not matched_sonali:
                    r_res = session.get(f"https://billpay.sonalibank.com.bd/BoardRescrutiny/Home/Search?searchStr={roll}", headers=headers_res, timeout=8, verify=False)
                    res_ids = re.findall(r'/BoardRescrutiny/Home/Voucher/([A-Za-z0-9_-]+)', r_res.text, re.I)
                    for tid in set(res_ids):
                        d = get_rescrutiny_data(tid)
                        if d and d["name"] != "N/A" and d["board"].strip().upper() in ["COMILLA", "CUMILLA", "কুমিল্লা"]:
                            matched_sonali = d
                            fee_source_title = "Board Rescrutiny"
                            break

                if matched_sonali:
                    comilla_info = fetch_comilla_raw("ssc", str(matched_sonali["roll"]), "2026")
                    if comilla_info:
                        found_students += 1
                        await send_comilla_master_result(update_or_query, context, matched_sonali, comilla_info, fee_source_title)

            if i % 5 == 0 or i == total_range:
                await status_msg.edit_text(f"⏳ <b>Processing</b>\n🔢 Roll: {roll}\n📊 Found: {found_students}\n✅ Progress: {i}/{total_range}", parse_mode="HTML")
            await asyncio.sleep(0.1)
        except: continue

    await status_msg.delete()
    await msg_source.reply_text(f"✅ Done!\n📊 Found Students: {found_students}", 
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👉 Next 500?", callback_data="next_500")]]))

# =========================================================
# BOT COMMANDS & HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_search_id
    current_search_id += 1 
    
    keyboard = [
        ["1️⃣ Sonali Recheck", "2️⃣ Sonali Result"],
        ["3️⃣ Ctg Board", "4️⃣ Comilla Board"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🚀 <b>CHATTOGRAM & COMILLA MASTER BOT</b>\n\nদয়া করে নিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশন সিলেক্ট করুন:", 
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_search_id
    text = update.message.text.strip()
    chat_id = update.message.chat.id

    if text == "1️⃣ Sonali Recheck":
        user_modes[chat_id] = "recheck"
        user_states[chat_id] = {"step": "selecting_board"}
        keyboard = [[InlineKeyboardButton("🌐 ALL Board", callback_data="board_ALL")]]
        for board in BOARDS:
            keyboard.append([InlineKeyboardButton(board, callback_data=f"board_{board}")])
        
        await update.message.reply_text(
            "🏦 <b>Sonali Board Rescrutiny Mode</b>\n\nদয়া করে নিচে থেকে বোর্ড সিলেক্ট করুন অথবা সরাসরি <b>ALL Board</b> এ ক্লিক করুন:",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return

    elif text == "2️⃣ Sonali Result":
        user_modes[chat_id] = "sonali"
        user_states[chat_id] = {"step": "selecting_board"}
        keyboard = [[InlineKeyboardButton("🌐 ALL Board", callback_data="board_ALL")]]
        for board in BOARDS:
            keyboard.append([InlineKeyboardButton(board, callback_data=f"board_{board}")])
        
        await update.message.reply_text(
            "🏛️ <b>Sonali XI Admission Mode</b>\n\nদয়া করে নিচে থেকে বোর্ড সিলেক্ট করুন অথবা সরাসরি <b>ALL Board</b> এ ক্লিক করুন:",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return

    elif text == "3️⃣ Ctg Board":
        user_modes[chat_id] = "ctg_menu"
        user_states.pop(chat_id, None)
        keyboard = [
            [InlineKeyboardButton("📘 SSC Result", callback_data="ctg_ssc_btn")],
            [InlineKeyboardButton("⭐ Master Result", callback_data="ctg_master_btn")]
        ]
        await update.message.reply_text(
            "🌊 <b>Ctg Board Menu</b>\n\nঅনুগ্রহ করে চট্টগ্রাম বোর্ডের কোন রেজাল্ট দেখতে চান তা নির্বাচন করুন:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif text == "4️⃣ Comilla Board":
        user_modes[chat_id] = "comilla_menu"
        user_states.pop(chat_id, None)
        keyboard = [
            [InlineKeyboardButton("📘 SSC Result", callback_data="comilla_ssc_btn")],
            [InlineKeyboardButton("⭐ Master Result", callback_data="comilla_master_btn")]
        ]
        await update.message.reply_text(
            "🏛️ <b>Comilla Board Menu</b>\n\nঅনুগ্রহ করে কুমিল্লা বোর্ডের কোন রেজাল্ট দেখতে চান তা নির্বাচন করুন:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    current_mode = user_modes.get(chat_id)
    if current_mode == "comilla_roll":
        if not text.isdigit():
            await update.message.reply_text("⚠️ অনুগ্রহ করে শুধুমাত্র সঠিক রোল নম্বর লিখুন।")
            return
        comilla_sessions[chat_id] = {"roll": text}
        user_modes[chat_id] = "comilla_exam"
        
        keyboard = [
            [
                InlineKeyboardButton("SSC", callback_data="comilla_exam_ssc"),
                InlineKeyboardButton("HSC", callback_data="comilla_exam_hsc"),
            ]
        ]
        await update.message.reply_text(
            f"রোল: *{text}*\nএখন পরীক্ষার ধরন নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if current_mode == "comilla_master":
        current_search_id += 1
        try:
            if "-" in text:
                s, e = map(int, text.split("-"))
                if e - s > 2000:
                    await update.message.reply_text("❌ Maximum Range 2000")
                    return
                await run_search(update, context, s, e, "comilla_master")
            elif text.isdigit():
                roll = int(text)
                await run_search(update, context, roll, roll, "comilla_master")
            else:
                await update.message.reply_text("❌ সঠিক রোল বা রেঞ্জ দিন।", parse_mode="HTML")
        except: pass
        return

    state_info = user_states.get(chat_id, {})
    if current_mode in ["recheck", "sonali"]:
        step = state_info.get("step")
        if text == "🏫 Institute Name":
            await update.message.reply_text("দয়া করে নতুন **ইনস্টিটিউশনের নাম (Institution Name)** ম্যানুয়ালি টাইপ করে পাঠান:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
            return

        if step == "getting_institution":
            state_info["institute"] = text
            state_info["step"] = "getting_roll"
            reply_kb = ReplyKeyboardMarkup([[KeyboardButton("🏫 Institute Name")]], resize_keyboard=True)
            await update.message.reply_text(f"ইনস্টিটিউশনের নাম সংরক্ষিত হয়েছে: <b>{text}</b>\n\nএখন শিক্ষার্থীর রোল নম্বর বা রোল রেঞ্জ দিন (উদা: <code>128926</code> অথবা <code>128926-128930</code>):", parse_mode="HTML", reply_markup=reply_kb)
            return

        elif step == "getting_roll":
            current_search_id += 1
            try:
                if "-" in text:
                    s, e = map(int, text.split("-"))
                    if e - s > 2000:
                        await update.message.reply_text("❌ Maximum Range 2000")
                        return
                    await run_search(update, context, s, e, current_mode)
                elif text.isdigit():
                    roll = int(text)
                    await run_search(update, context, roll, roll, current_mode)
                else:
                    await update.message.reply_text("❌ সঠিক রোল বা রেঞ্জ দিন।", parse_mode="HTML")
            except: pass
            return

    if current_mode in ["ctg_ssc", "ctg_master"]:
        current_search_id += 1
        try:
            if "-" in text:
                s, e = map(int, text.split("-"))
                if e - s > 2000:
                    await update.message.reply_text("❌ Maximum Range 2000")
                    return
                await run_search(update, context, s, e, current_mode)
            elif text.isdigit():
                roll = int(text)
                await run_search(update, context, roll, roll, current_mode)
            else:
                await update.message.reply_text("❌ সঠিক রোল বা রেঞ্জ দিন।", parse_mode="HTML")
        except: pass
        return

    await update.message.reply_text("❌ প্রথমে মেনু থেকে রেজাল্ট মোড সিলেক্ট করুন।")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_search_id
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    data = query.data

    if data.startswith("board_"):
        board_name = data.split("_", 1)[1]
        if chat_id not in user_states: user_states[chat_id] = {}
        user_states[chat_id]["board"] = board_name

        try: await query.message.delete()
        except Exception: pass

        if board_name == "ALL":
            user_states[chat_id]["step"] = "getting_roll"
            await query.message.reply_text("🌐 <b>ALL Board Selected</b>\n\nএখন কোনো ইনস্টিটিউটের নাম ছাড়াই সরাসরি শিক্ষার্থীর রোল নম্বর বা রোল রেঞ্জ দিন (উদা: <code>557421</code>):", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        else:
            user_states[chat_id]["step"] = "getting_institution"
            reply_kb = ReplyKeyboardMarkup([[KeyboardButton("🏫 Institute Name")]], resize_keyboard=True)
            await query.message.reply_text(f"আপনি সিলেক্ট করেছেন: <b>{board_name}</b>\n\nএখন ইনস্টিটিউটের নাম টাইপ করে পাঠান অথবা নিচের <b>'🏫 Institute Name'</b> বাটনে ক্লিক করুন:", parse_mode="HTML", reply_markup=reply_kb)
        return

    elif data == "ctg_ssc_btn":
        user_modes[chat_id] = "ctg_ssc"
        try: await query.message.delete()
        except Exception: pass
        await query.message.reply_text("📘 <b>Ctg SSC Result Mode Activated</b>\n\n📌 চট্টগ্রাম বোর্ডের রোল বা রোল রেঞ্জ পাঠান:", parse_mode="HTML")
        return

    elif data == "ctg_master_btn":
        user_modes[chat_id] = "ctg_master"
        try: await query.message.delete()
        except Exception: pass
        await query.message.reply_text("⭐ <b>Ctg Master Result Mode Activated</b>\n\n📌 চট্টগ্রাম বোর্ডের রোল বা রোল রেঞ্জ পাঠান:", parse_mode="HTML")
        return

    elif data == "comilla_ssc_btn":
        user_modes[chat_id] = "comilla_roll"
        comilla_sessions[chat_id] = {}
        try: await query.message.delete()
        except Exception: pass
        await query.message.reply_text(
            "📘 <b>Comilla Board SSC Result Mode Activated</b>\n\nস্বাগতম! শিক্ষার্থীর **রোল নম্বর** লিখে পাঠান:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    elif data == "comilla_master_btn":
        user_modes[chat_id] = "comilla_master"
        try: await query.message.delete()
        except Exception: pass
        await query.message.reply_text(
            "⭐ <b>Comilla Board Master Mode Activated (SSC 2026 Fixed)</b>\n\n📌 কুমিল্লা বোর্ডের রোল নম্বর বা রোল রেঞ্জ পাঠান:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    elif data.startswith("comilla_exam_"):
        exam_type = data.split("_")[2]
        if chat_id not in comilla_sessions: comilla_sessions[chat_id] = {}
        comilla_sessions[chat_id]["exam"] = exam_type

        years = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]
        keyboard = []
        row = []
        for y in years:
            row.append(InlineKeyboardButton(y, callback_data=f"comilla_year_{y}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)

        await query.edit_message_text(
            f"পরীক্ষা: *{exam_type.upper()}*\nপাশের বছর (Passing Year) নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    elif data.startswith("comilla_year_"):
        year = data.split("_")[2]
        if chat_id not in comilla_sessions:
            await query.edit_message_text("⚠️ সেশন মেয়াদোত্তীর্ণ হয়েছে। /start দিয়ে আবার শুরু করুন।")
            return

        roll = comilla_sessions[chat_id].get("roll")
        exam = comilla_sessions[chat_id].get("exam")

        await query.edit_message_text("⏳ কুমিল্লা বোর্ডের সার্ভার থেকে তথ্য খোঁজা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")

        comilla_info = fetch_comilla_raw(exam, roll, year)
        if not comilla_info:
            result_text = f"❌ রোল: *{roll}*, বছর: *{year}* ({exam.upper()}) এর কোনো তথ্য পাওয়া যায়নি।"
        else:
            result_text = (
                f"🎓 *কুমিল্লা বোর্ড শিক্ষার্থীর তথ্য ({exam.upper()} - {year})*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *নাম:* `{comilla_info.get('name')}`\n"
                f"👨‍👦 *পিতার নাম:* `{comilla_info.get('father')}`\n"
                f"👩‍👦 *মাতার নাম:* `{comilla_info.get('mother')}`\n"
                f"🆔 *রোল নম্বর:* `{roll}`\n"
                f"📝 *রেজিস্ট্রেশন:* `{comilla_info.get('reg')}`\n"
                f"📅 *সেশন:* `{comilla_info.get('session')}`\n"
                f"🎂 *জন্ম তারিখ:* `{comilla_info.get('dob')}`\n"
                f"⚧️ *লিঙ্গ:* `{comilla_info.get('sex')}`\n"
                f"📊 *GPA:* `{comilla_info.get('gpa')}`\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )

        await query.edit_message_text(result_text, parse_mode="Markdown")

        comilla_sessions.pop(chat_id, None)
        user_modes.pop(chat_id, None)
        return

    if data == "next_500":
        current_search_id += 1
        mode = user_modes.get(chat_id)
        last_end = context.user_data.get("current_end", 0)
        await run_search(query, context, last_end + 1, last_end + 500, mode)

if __name__ == "__main__":
    keep_alive()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Chattogram & Comilla Master Bot is running...")
    application.run_polling(drop_pending_updates=True)
