import os
from flask import Flask, request
import telebot

# Vercel Environment Variables daxilindən bot tokenini oxuyuruq
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# 1. Telegram-dan gələn sorğuları qəbul edən əsas webhook ünvanı (POST)
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Forbidden', 403

# 2. Brauzerdən domenə daxil olduqda botun işlədiyini göstərən səhifə (GET)
@app.route('/', methods=['GET'])
def index():
    return "Honeyfarm Bot işlək vəziyyətdədir!", 200


# ==========================================
# BOTUN ƏMRLƏRİ VƏ CAVABLARI
# ==========================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Salam! Honeyfarm botuna xoş gəldiniz. 🍯 Botumuz aktivdir.")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    bot.reply_to(message, f"Mesajınız qəbul olundu: {message.text}")
