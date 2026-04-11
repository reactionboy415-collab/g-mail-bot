import telebot
import requests
import re
import time
import threading
import os
import uuid
from flask import Flask
from telebot import types
from urllib.parse import unquote

# --- CONFIGURATION ---
TOKEN = "8330596269:AAFD-NNRBfLZ8Vl_1FZ-lHasXtVKUiFdxp8"
bot = telebot.TeleBot(TOKEN)
ADMIN_IDS = [7840042951]
REQUIRED_CHANNELS = ["@CatalystMystery"]
DEV_USERNAME = "@dev2dex"

# Global Storage
user_sessions = {}
system_data = {"users": {}, "total_gen": 0, "total_rec": 0}

server = Flask(__name__)

# --- CORE GMAIL ENGINE (Direct Integration) ---
class TitanGmailEngine:
    def __init__(self):
        self.base_url = "https://www.emailnator.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12; LAVA Blaze) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }

    def get_session(self):
        """Fresh session aur XSRF-TOKEN fetch karne ke liye"""
        s = requests.Session()
        try:
            s.get(self.base_url, timeout=10)
            token = s.cookies.get('XSRF-TOKEN')
            if token:
                headers = self.headers.copy()
                headers['X-XSRF-TOKEN'] = unquote(token)
                return s, headers
        except: pass
        return None, None

    def clean_html(self, raw_html):
        clean = re.sub(r'<(script|style).*?>.*?</\1>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<.*?>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

engine = TitanGmailEngine()

# --- UI UTILITIES ---
def get_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🆕 Generate Gmail", callback_data="gen_new"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="check_inbox")
    )
    markup.add(types.InlineKeyboardButton("📢 Channel", url="https://t.me/CatalystMystery"))
    return markup

def is_subscribed(uid):
    for ch in REQUIRED_CHANNELS:
        try:
            if bot.get_chat_member(ch, uid).status in ['left', 'kicked']: return False
        except: continue
    return True

# --- MONITORING WORKER ---
def titan_monitor(chat_id, email):
    print(f"[TITAN] Monitoring: {email}")
    session, headers = engine.get_session()
    if not session: return

    while chat_id in user_sessions and user_sessions[chat_id]['email'] == email:
        try:
            url = f"{engine.base_url}/message-list"
            resp = session.post(url, json={"email": email}, headers=headers, timeout=15)
            
            if resp.status_code == 200:
                messages = resp.json().get('messageData', [])
                # Filter out system ads
                valid_msgs = [m for m in messages if m['from'] != "AI TOOLS"]
                
                for m in valid_msgs:
                    m_id = m['messageID']
                    if m_id not in user_sessions[chat_id]['seen_ids']:
                        # Fetch Body
                        body_resp = session.post(url, json={"email": email, "messageID": m_id}, headers=headers)
                        clean_body = engine.clean_html(body_resp.text)
                        otp = re.search(r'(\d{4,6})', clean_body)
                        
                        msg = (
                            f"📩 *NEW MAIL RECEIVED*\n"
                            f"━━━━━━━━━━━━━━\n"
                            f"👤 *From:* `{m['from']}`\n"
                            f"📋 *Subject:* `{m['subject']}`\n\n"
                            f"📝 *Content:* \n`{clean_body[:600]}...`\n\n"
                            f"{'🎯 *OTP:* `' + otp.group(1) + '`' if otp else '🚫 No OTP Found'}\n"
                            f"━━━━━━━━━━━━━━\n"
                            f"🛠 *Powered by:* {DEV_USERNAME}"
                        )
                        bot.send_message(chat_id, msg, parse_mode="Markdown")
                        user_sessions[chat_id]['seen_ids'].add(m_id)
                        system_data['total_rec'] += 1
            
            elif resp.status_code == 419: # Token expired
                session, headers = engine.get_session()
                
        except: pass
        time.sleep(7)

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    system_data['users'][uid] = message.from_user.username
    
    if not is_subscribed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url="https://t.me/CatalystMystery"))
        markup.add(types.InlineKeyboardButton("🔄 Joined - Verify", callback_data="verify_sub"))
        return bot.send_message(message.chat.id, "❌ *Access Restricted*\n\nJoin our channel to use the unlimited Gmail bot.", parse_mode="Markdown", reply_markup=markup)

    welcome = (
        f"💎 *TITAN GMAIL GENERATOR* 💎\n"
        f"━━━━━━━━━━━━━━\n"
        f"Welcome back, `{message.from_user.first_name}`!\n"
        f"Generate high-quality Gmail addresses for your bypasses and signups."
    )
    bot.send_message(message.chat.id, welcome, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    chat_id = call.message.chat.id
    
    if call.data == "gen_new":
        if not is_subscribed(call.from_user.id):
            return bot.answer_callback_query(call.id, "Join channel first!", show_alert=True)
            
        bot.edit_message_text("⚡ *Generating Secure Address...*", chat_id, call.message.message_id, parse_mode="Markdown")
        
        s, h = engine.get_session()
        if s:
            res = s.post(f"{engine.base_url}/generate-email", json={"email": ["plusGmail", "dotGmail"]}, headers=h).json()
            email = res['email'][0]
            
            user_sessions[chat_id] = {'email': email, 'seen_ids': set()}
            system_data['total_gen'] += 1
            
            success_msg = (
                f"✅ *Gmail Ready To Use*\n\n"
                f"📧 Email: `{email}`\n\n"
                f"🚀 *Status:* Monitoring Live...\n"
                f"Sent any OTP/Mail to this address."
            )
            bot.edit_message_text(success_msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
            
            # Start direct thread
            threading.Thread(target=titan_monitor, args=(chat_id, email), daemon=True).start()
        else:
            bot.send_message(chat_id, "❌ API Error. Try again.")

    elif call.data == "verify_sub":
        if is_subscribed(call.from_user.id):
            bot.delete_message(chat_id, call.message.message_id)
            start(call)
        else:
            bot.answer_callback_query(call.id, "Subscription not found!", show_alert=True)

# Admin Stats
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id in ADMIN_IDS:
        msg = f"📊 *TITAN STATS*\n\nUsers: {len(system_data['users'])}\nEmails: {system_data['total_gen']}\nInbox: {system_data['total_rec']}"
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@server.route('/')
def health(): return "Titan Alive", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: server.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    bot.infinity_polling()
