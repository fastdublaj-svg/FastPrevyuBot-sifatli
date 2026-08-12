import telebot
import sqlite3
import random
import time
from telebot import types

# --- SOZLAMALAR ---
TOKEN = "8638068274:AAGK4Uz37q0D_TiU9s37HW8aiOFDVMuTczk" # @BotFather dan olgan token

bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 7543852010
ADMIN_USERNAME = "@Fast_gamer_uz"

# Majburiy obuna kanali
REQUIRED_CHANNEL = "@Fast_gamer_mod"
# Vazifalar uchun kanallar
TASK_CHANNELS = [
    "https://t.me/Fast_gamer_mod",
    "https://t.me/Fast_prevyu",
    "https://t.me/FAST_MODS_BOT",
    "https://t.me/PHPVaPython"
]

# --- DATABASE ---
db = sqlite3.connect("users.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, 
    username TEXT, 
    balance INTEGER DEFAULT 0, 
    previews_count INTEGER DEFAULT 0, 
    referred_by INTEGER,
    last_task_time INTEGER DEFAULT 0)""")
db.commit()

# --- FUNKSIYALAR ---
def check_sub(user_id):
    try:
        status = bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def get_menu(user_id):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("⭐ Prevyu yasash ⭐")
    m.add("💸Pulga Prevyu buyurtma qilish💸")
    m.add("💬 Vazifalar 💬", "👥 Referal tizimi")
    m.add("🎁 Promo kod 🎁", "©️ Reyting")
    # Admin tekshiruvi
    if user_id == ADMIN_ID:
        m.add("⛓️‍💥 Sozlamalari")
    return m

# --- START VA OBUNA ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Referal tizimi
    args = message.text.split()
    referrer = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (id, username, balance, referred_by) VALUES(?,?,?,?)", 
                       (user_id, username, 0, referrer))
        db.commit()
        if referrer and referrer != user_id:
            cursor.execute("UPDATE users SET balance = balance + 10 WHERE id=?", (referrer,))
            db.commit()
            try: bot.send_message(referrer, "🎉 Yangi referal! +10 balans.")
            except: pass

    if not check_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔒 Obuna boʻlish", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
        markup.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="verify"))
        bot.send_message(user_id, f"Salom {message.from_user.first_name}\n\n@Fast_prevyu_bot ga xush kelibsiz! Botdan foydalanish uchun kanalga a'zo bo'ling.", reply_markup=markup)
    else:
        bot.send_message(user_id, f"Salom @{username}\n\n@Fast_prevyu_bot ga xush kelibsiz\nIltimos asosiy menyuga kiring va o‘z prevyuyingozni tayyorlang", reply_markup=get_menu(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify(call):
    if check_sub(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.from_user.id, "✅ Tasdiqlandi! Xush kelibsiz.", reply_markup=get_menu(call.from_user.id))
    else:
        bot.answer_callback_query(call.id, "❌ Hali ham obuna bo'lmagansiz!", show_alert=True)

# --- VAZIFALAR ---
@bot.message_handler(func=lambda m: m.text == "💬 Vazifalar 💬")
def tasks(message):
    user_id = message.from_user.id
    cursor.execute("SELECT last_task_time FROM users WHERE id=?", (user_id,))
    last_time = cursor.fetchone()[0]
    
    if int(time.time()) - last_time < 300:
        bot.send_message(user_id, "⏳ Iltimos 5-10 daqiqadan keyin yangi kanallar ochiladi, hozircha kiravering.")
        return

    target = random.choice(TASK_CHANNELS)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔒 Obuna boʻlish", url=target))
    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_task"))
    bot.send_message(user_id, "Salom balans ishlash uchun ushbu kanalga obuna boʻling va 5 balans oling", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_task")
def check_task_callback(call):
    cursor.execute("UPDATE users SET balance = balance + 5, last_task_time = ? WHERE id=?", (int(time.time()), call.from_user.id))
    db.commit()
    bot.edit_message_text("✅ +5 balans qo'shildi! Keyingi vazifa 5 daqiqadan so'ng.", call.message.chat.id, call.message.message_id)

# --- REYTING VA PROFIL ---
@bot.message_handler(func=lambda m: m.text == "©️ Reyting")
def rating_menu(message):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("👥 Oʻrinlar", "📊 Foydalanuvchilar soni")
    m.add("⬅️ Orqaga")
    bot.send_message(message.chat.id, "Reyting bo'limi:", reply_markup=m)

@bot.message_handler(func=lambda m: m.text == "👥 Oʻrinlar")
def top_10(message):
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    users = cursor.fetchall()
    text = "🏆 TOP 10 FOYDALANUVCHILAR:\n\n"
    for i, u in enumerate(users, 1):
        text += f"{i}. @{u[0]} — {u[1]} balans\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['profil'])
def profil(message):
    cursor.execute("SELECT balance, previews_count FROM users WHERE id=?", (message.from_user.id,))
    res = cursor.fetchone()
    bot.send_message(message.chat.id, f"👤 Ism: {message.from_user.first_name}\n🆔 ID: {message.from_user.id}\n💰 Balans: {res[0]}\n🖼 Prevyular: {res[1]}")

# --- ADMIN SOZLAMALARI ---
@bot.message_handler(func=lambda m: m.text == "⛓️‍💥 Sozlamalari")
def admin_settings(message):
    if message.from_user.id == ADMIN_ID:
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("🆔 Balans berish", callback_data="admin_add"))
        bot.send_message(ADMIN_ID, "Admin panel:", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add")
def admin_add(call):
    msg = bot.send_message(ADMIN_ID, "Foydalanuvchi ID va miqdorni yozing (Masalan: 7543852010 500):")
    bot.register_next_step_handler(msg, save_balance)

def save_balance(message):
    try:
        uid, amnt = map(int, message.text.split())
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amnt, uid))
        db.commit()
        bot.send_message(ADMIN_ID, "✅ Bajarildi!")
    except: bot.send_message(ADMIN_ID, "❌ Xato format.")

# --- BOSHQA TUGMALAR ---
@bot.message_handler(func=lambda m: m.text == "💸Pulga Prevyu buyurtma qilish💸")
def order(message):
    bot.send_message(ADMIN_ID, f"💸 Buyurtma: @{message.from_user.username} (ID: {message.from_user.id})")
    bot.send_message(message.chat.id, f"✅ Buyurtma yuborildi. Admin: {ADMIN_USERNAME}")

@bot.message_handler(func=lambda m: m.text == "🎁Promo kod🎁")
def promo(message):
    msg = bot.send_message(message.chat.id, "Promo kodni kiriting:")
    bot.register_next_step_handler(msg, check_promo)

def check_promo(message):
    if message.text in ["Fast", "NEW2026","Fast_gamer_uz","FastPrevyu" ]:
        cursor.execute("UPDATE users SET balance = balance + 5 WHERE id=?", (message.from_user.id,))
        db.commit()
        bot.send_message(message.chat.id, "✅ +5 balans qo'shildi!")
    else: bot.send_message(message.chat.id, "❌ Xato kod.")

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga")
def back(message):
    bot.send_message(message.chat.id, "Asosiy menyu", reply_markup=get_menu(message.from_user.id))

print("Bot Python yordamida ishlamoqda...")
bot.infinity_polling()
