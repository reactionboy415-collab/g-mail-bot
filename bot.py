import telebot
import requests
import re
import time
import threading
import os
from flask import Flask
from telebot import types

# --- CONFIGURATION ---
TOKEN = "8330596269:AAFD-NNRBfLZ8Vl_1FZ-lHasXtVKUiFdxp8" # Updated Token
bot = telebot.TeleBot(TOKEN)
API_BASE_URL = "https://paid-gmailnator-api.vercel.app" # Your Vercel API

# Admin & Channel Config
ADMIN_IDS = [7840042951]
REQUIRED_CHANNELS = ["@CatalystMystery"] # Updated Channel
DEV_USERNAME = "@dev2dex" # Developer handle

# Stats tracking in RA
system_data = {
    "users": {},      
    "total_gen": 0,   
    "total_rec": 0    
}

user_sessions = {}
server = Flask(__name__)

@server.route('/')
def health_check():
    return "Bot is active and monitoring.", 200

# --- CORE UTILITIES ---
def is_user_subscribed(user_id):
    for channel in REQUIRED_CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status in ['left', 'kicked']: return False
        except: continue
    return True

def get_subscription_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(REQUIRED_CHANNELS, 1):
        markup.add(types.InlineKeyboardButton(f"📢 Join Catalyst Mystery", url=f"https://t.me/CatalystMystery"))
    markup.add(types.InlineKeyboardButton("🔄 Verify Subscription", callback_data="verify_sub"))
    return markup

def get_control_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🔄 Refresh Inbox", callback_data="check_inbox"),
               types.InlineKeyboardButton("🆕 New Email", callback_data="gen_new"))
    return markup

# --- MONITORING LOGIC ---
def inbox_monitor_worker(chat_id, email):
    print(f"[THREAD] Monitoring started for {email}")
    while chat_id in user_sessions and user_sessions[chat_id]['email'] == email:
        try:
            # Hit your Vercel API
            resp = requests.get(f"{API_BASE_URL}/inbox", params={"email": email}, timeout=15)
            if resp.status_code == 200:
                inbox = resp.json().get('inbox', [])
                session = user_sessions[chat_id]
                
                for mail in inbox:
                    mail_id = f"{mail['from']}_{mail['subject']}"
                    if mail_id not in session['seen_ids']:
                        otp_text = f"\n\n🎯 *OTP:* `{mail['otp']}`" if mail['otp'] else ""
                        msg = (
                            f"📩 *NEW MAIL DETECTED!*\n\n"
                            f"👤 *From:* `{mail['from']}`\n"
                            f"📋 *Subject:* `{mail['subject']}`\n"
                            f"📝 *body:* \n`{mail['body'][:800]}`"
                            f"{otp_text}\n\n"
                            f"🛠 *Dev:* {DEV_USERNAME}"
                        )
                        bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=get_control_panel())
                        session['seen_ids'].add(mail_id)
                        system_data['total_rec'] += 1
        except Exception as e:
            print(f"Monitor Error: {e}")
        time.sleep(8) # Check every 8 seconds

# --- BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def start_command(message):
    uid = str(message.from_user.id)
    system_data['users'][uid] = message.from_user.username or "PrivateUser"
    
    if is_user_subscribed(message.from_user.id):
        welcome_msg = (
            f"🔥 *UNLIMITED GMAIL BOT* 🔥\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Developer: {DEV_USERNAME}\n\n"
            f"Get a professional Gmail address instantly. "
            f"Click the button below to generate."
        )
        bot.send_message(message.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=get_control_panel())
    else:
        bot.send_message(message.chat.id, "🚫 *Access Denied*\n\nYou must join our channel to use this bot.", 
                         parse_mode="Markdown", reply_markup=get_subscription_menu())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    if not is_user_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "Please join the channel first!", show_alert=True)
        return

    if call.data == "gen_new":
        bot.answer_callback_query(call.id, "Generating Email...")
        try:
            res = requests.get(f"{API_BASE_URL}/generate").json()
            email = res['email']
            user_sessions[chat_id] = {'email': email, 'seen_ids': set()}
            system_data['total_gen'] += 1
            
            bot.send_message(chat_id, f"✅ *Gmail Generated*\n\n📧 `{email}`\n\nI am now monitoring this inbox. Any incoming mail will be sent here automatically.", 
                             parse_mode="Markdown", reply_markup=get_control_panel())
            # Start background monitoring thread
            threading.Thread(target=inbox_monitor_worker, args=(chat_id, email), daemon=True).start()
        except:
            bot.send_message(chat_id, "❌ *API Error*\nUnable to connect to the email server.")

    elif call.data == "check_inbox":
        if chat_id not in user_sessions:
            bot.answer_callback_query(call.id, "No active session. Generate an email first!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Checking for updates...")

    elif call.data == "verify_sub":
        if is_user_subscribed(call.from_user.id):
            bot.delete_message(chat_id, call.message.message_id)
            start_command(call)
        else:
            bot.answer_callback_query(call.id, "❌ Subscription not found!", show_alert=True)

# --- ADMIN FUNCTIONS ---
@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id in ADMIN_IDS:
        stats_text = (
            f"📊 *Bot Status Report*\n"
            f"━━━━━━━━━━━━━━\n"
            f"👥 Total Users: `{len(system_data['users'])}`\n"
            f"📧 Generated: `{system_data['total_gen']}`\n"
            f"📥 Received: `{system_data['total_rec']}`"
        )
        bot.send_message(message.chat.id, stats_text, parse_mode="Markdown")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    print(f"[SYSTEM] Bot by {DEV_USERNAME} is starting...")
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
