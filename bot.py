import os
import telebot
from telebot import types, apihelper
import sqlite3
import re

# ====== Environment Variables ======
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
KASPI_LINK = os.environ.get("KASPI_LINK")
HALYK_LINK = os.environ.get("HALYK_LINK")

# ====== Webhook өшіру ======
apihelper.delete_webhook(TOKEN)

bot = telebot.TeleBot(TOKEN)

# ====== SQLite деректер базасы ======
conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    phone TEXT,
    age INTEGER,
    services TEXT,
    total INTEGER
)
""")
conn.commit()

# ====== Бағалар ======
prices = {
    "🤖 Telegram бот": 7000,
    "🛒 Тапсырыс қабылдау": 3000,
    "📊 Баға есептейтін бот": 5000
}

user_cart = {}
user_state = {}
user_name = {}
user_phone = {}
user_age = {}

# ====== Басты меню ======
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for s in prices:
        markup.add(s)
    markup.add("📩 Жалғастыру", "🛒 Себет")
    bot.send_message(chat_id, "Қызметті таңдаңыз 👇", reply_markup=markup)

@bot.message_handler(commands=['start', '/menu'])
def start(message):
    chat_id = message.chat.id
    user_cart[chat_id] = []
    user_state[chat_id] = "select_service"
    main_menu(chat_id)

# ====== Себет көрсету ======
def show_cart(chat_id):
    if chat_id not in user_cart or not user_cart[chat_id]:
        bot.send_message(chat_id, "🛒 Сіздің себетіңіз бос")
    else:
        services = ", ".join(user_cart[chat_id])
        total = sum(prices[i] for i in user_cart[chat_id])
        bot.send_message(chat_id, f"🛒 Себет: {services}\n💰 Жалпы: {total} тг")

# ====== Төлем көрсету ======
def show_payment(chat_id, total):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Kaspi", url=KASPI_LINK))
    markup.add(types.InlineKeyboardButton("🏦 Halyk Bank", url=HALYK_LINK))
    bot.send_message(chat_id, f"💰 Төлем: {total} тг\nТөлем әдісін таңдаңыз 👇", reply_markup=markup)

    # Төлем аяқталғанын хабарлау батырмасы
    markup2 = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup2.add("Төлем аяқталды")
    bot.send_message(chat_id, "Төлемді аяқтағаннан кейін осы батырманы басыңыз", reply_markup=markup2)

    save_order(chat_id, total)

# ====== Тапсырысты сақтау ======
def save_order(chat_id, total):
    services = ", ".join(user_cart[chat_id])
    age = user_age.get(chat_id, 0)
    name = user_name.get(chat_id, "")
    phone = user_phone.get(chat_id, "")

    cursor.execute(
        "INSERT INTO orders (name, phone, age, services, total) VALUES (?, ?, ?, ?, ?)",
        (name, phone, age, services, total)
    )
    conn.commit()

    cursor.execute("SELECT last_insert_rowid()")
    order_id = cursor.fetchone()[0]

    bot.send_message(chat_id, f"✅ Тапсырыс қабылданды! Сіздің нөміріңіз: {order_id}")

    bot.send_message(ADMIN_ID,
        f"📥 ЖАҢА ТАПСЫРЫС #{order_id}\n"
        f"👤 {name}\n"
        f"📞 {phone}\n"
        f"🧒 Жасы: {age}\n"
        f"🛒 {services}\n"
        f"💰 {total} тг"
    )

    # Reset
    user_cart[chat_id] = []
    user_state[chat_id] = "select_service"

# ====== Бот хабарларын өңдеу ======
@bot.message_handler(func=lambda message: True)
def handle(message):
    chat_id = message.chat.id
    text = message.text

    # Себет
    if text == "🛒 Себет":
        show_cart(chat_id)
        return

    # Қызмет таңдау
    if user_state.get(chat_id) == "select_service":
        if text in prices:
            user_cart[chat_id].append(text)
            total = sum(prices[i] for i in user_cart[chat_id])
            bot.send_message(chat_id, f"✅ Қосылды: {text}\n💰 {total} тг")
        elif text == "📩 Жалғастыру":
            if not user_cart[chat_id]:
                bot.send_message(chat_id, "❗ Алдымен қызмет таңдаңыз")
                return
            user_state[chat_id] = "ask_name"
            bot.send_message(chat_id, "👤 Атыңызды жазыңыз:")

    # Атын сұрау
    elif user_state.get(chat_id) == "ask_name":
        user_name[chat_id] = text
        user_state[chat_id] = "ask_phone"
        bot.send_message(chat_id, "📞 Телефон номеріңізді жазыңыз:")

    # Телефон сұрау
    elif user_state.get(chat_id) == "ask_phone":
        if not re.match(r'^\+7\d{10}$', text):
            bot.send_message(chat_id, "⚠️ Телефонды +7XXXXXXXXXX форматында жазыңыз")
            return
        user_phone[chat_id] = text
        user_state[chat_id] = "ask_age"
        bot.send_message(chat_id, "Қанша жастасыз? (санмен)")

    # Жас сұрау
    elif user_state.get(chat_id) == "ask_age":
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Санмен жазыңыз")
            return
        age = int(text)
        if age <= 0 or age > 120:
            bot.send_message(chat_id, "⚠️ Дұрыс жас жазыңыз")
            return
        user_age[chat_id] = age
        total = sum(prices[i] for i in user_cart[chat_id])

        if age < 18:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("ИӘ", "ЖОҚ")
            user_state[chat_id] = "parent_pay"
            bot.send_message(chat_id,
                "Сіз 18-ге толмағансыз.\nАта-анаңыздың картасынан төлейсіз бе?",
                reply_markup=markup)
        else:
            show_payment(chat_id, total)

    # Ата-ана төлемі
    elif user_state.get(chat_id) == "parent_pay":
        total = sum(prices[i] for i in user_cart[chat_id])
        if text == "ИӘ":
            show_payment(chat_id, total)
        else:
            bot.send_message(chat_id,
                "📩 Тапсырысыңыз қабылданды.\nАдмин сізбен хабарласады.")
            save_order(chat_id, total)

# ====== Админ командалары ======
@bot.message_handler(commands=['orders'])
def admin_orders(message):
    if message.chat.id != ADMIN_ID:
        return
    cursor.execute("SELECT id, name, phone, total FROM orders")
    orders = cursor.fetchall()
    if not orders:
        bot.send_message(ADMIN_ID, "Тапсырыстар жоқ")
    else:
        text = "\n".join([f"#{o[0]} {o[1]} | {o[2]} | {o[3]} тг" for o in orders])
        bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=['search'])
def admin_search(message):
    if message.chat.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(ADMIN_ID, "Қолдану: /search <phone>")
        return
    phone = parts[1]
    cursor.execute("SELECT * FROM orders WHERE phone=?", (phone,))
    orders = cursor.fetchall()
    if not orders:
        bot.send_message(ADMIN_ID, "Тапсырыс табылмады")
    else:
        text = "\n".join([f"#{o[0]} {o[1]} | {o[2]} | {o[3]} тг | {o[4]} | {o[5]} тг" for o in orders])
        bot.send_message(ADMIN_ID, text)

# ====== 24/7 POLLING ======
bot.polling(non_stop=True)
