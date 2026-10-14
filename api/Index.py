
import os
import re
import secrets
from decimal import Decimal

import requests
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
DATABASE_URL = os.environ["DATABASE_URL"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

API = f"https://api.telegram.org/bot{TOKEN}"
BONUS = 10000000  # 0.01 TON in nanotons
MIN_WITHDRAW = 100000000  # 0.1 TON


def db():
    return psycopg2.connect(
        DATABASE_URL, connect_timeout=5
    )


def init_db():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    referrer BIGINT,
                    balance BIGINT NOT NULL DEFAULT 0,
                    referrals INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    amount BIGINT NOT NULL,
                    wallet TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)


def send(chat_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }
    if keyboard:
        data["reply_markup"] = {
            "inline_keyboard": keyboard
        }
    requests.post(
        f"{API}/sendMessage",
        json=data,
        timeout=5
    ).raise_for_status()


def ton(amount):
    return str(Decimal(amount) / Decimal(10**9))


def menu():
    return [
        [{"text": "🔗 Referal linkim",
          "callback_data": "ref"}],
        [{"text": "💰 Balansım",
          "callback_data": "balance"}],
        [{"text": "💸 TON çıxar",
          "callback_data": "withdraw"}]
    ]


def register(user_id, referrer=None):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE id=%s",
                (user_id,)
            )
            if cur.fetchone():
                return

            valid_ref = None
            if referrer and referrer != user_id:
                cur.execute(
                    "SELECT id FROM users WHERE id=%s",
                    (referrer,)
                )
                if cur.fetchone():
                    valid_ref = referrer

            cur.execute("""
                INSERT INTO users (id, referrer)
                VALUES (%s, %s)
            """, (user_id, valid_ref))


def balance(user_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance, referrals FROM users WHERE id=%s",
                (user_id,)
            )
            return cur.fetchone() or (0, 0)


def approve_ref(user_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT referrer FROM users
                WHERE id=%s FOR UPDATE
            """, (user_id,))
            row = cur.fetchone()

            if not row or not row[0]:
                return None

            referrer = row[0]

            # Clear referral atomically so it cannot
            # be approved twice.
            cur.execute("""
                UPDATE users SET referrer=NULL
                WHERE id=%s
            """, (user_id,))

            cur.execute("""
                UPDATE users
                SET balance=balance+%s,
                    referrals=referrals+1
                WHERE id=%s
            """, (BONUS, referrer))

            return referrer


def create_withdrawal(user_id, wallet):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT balance FROM users
                WHERE id=%s FOR UPDATE
            """, (user_id,))
            row = cur.fetchone()

            if not row or row[0] < MIN_WITHDRAW:
                return None

            amount = row[0]
            cur.execute("""
                UPDATE users SET balance=0
                WHERE id=%s
            """, (user_id,))

            cur.execute("""
                INSERT INTO withdrawals
                    (user_id, amount, wallet)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (user_id, amount, wallet))

            return cur.fetchone()[0], amount


def process_withdrawal(wid, action):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, amount, status
                FROM withdrawals
                WHERE id=%s FOR UPDATE
            """, (wid,))
            row = cur.fetchone()

            if not row or row[2] != "pending":
                return None

            user_id, amount, _ = row

            if action == "reject":
                cur.execute("""
                    UPDATE users
                    SET balance=balance+%s
                    WHERE id=%s
                """, (amount, user_id))
                status = "rejected"
            else:
                status = "paid"

            cur.execute("""
                UPDATE withdrawals SET status=%s
                WHERE id=%s
            """, (status, wid))

            return user_id, amount


def handle_message(msg):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if msg["chat"]["type"] != "private":
        return

    if text.startswith("/start"):
        parts = text.split()
        referrer = None
        if len(parts) > 1 and parts[1].isdigit():
            referrer = int(parts[1])

        register(user_id, referrer)
        send(
            chat_id,
            "🐳 TON Referral Bot\n\n"
            "Dostlarını dəvət et və TON bonusu qazan!\n"
            "1 təsdiqlənmiş dost = 0.01 TON\n"
            "Minimum çıxarış = 0.1 TON\n\n"
            "Bonuslar admin yoxlamasından keçir.",
            menu()
        )
        return

    if user_id == ADMIN_ID and text.startswith(
        "/approve_ref "
    ):
        try:
            target = int(text.split()[1])
            ref = approve_ref(target)
            if ref:
                send(chat_id, "✅ Referal təsdiqləndi.")
                send(
                    ref,
                    "🎉 Referal bonusu: +0.01 TON"
                )
            else:
                send(chat_id, "Referal tapılmadı.")
        except (ValueError, IndexError):
            send(chat_id, "İstifadə: /approve_ref USER_ID")
        return

    if user_id == ADMIN_ID and text.startswith(
        "/paid "
    ):
        try:
            wid = int(text.split()[1])
            result = process_withdrawal(wid, "paid")
            if result:
                send(chat_id, "✅ Ödəniş qeyd edildi.")
                send(
                    result[0],
                    f"✅ {ton(result[1])} TON ödənildi."
                )
            else:
                send(chat_id, "Sorğu tapılmadı.")
        except (ValueError, IndexError):
            send(chat_id, "İstifadə: /paid ID")
        return

    if user_id == ADMIN_ID and text.startswith(
        "/reject "
    ):
        try:
            wid = int(text.split()[1])
            result = process_withdrawal(wid, "reject")
            if result:
                send(chat_id, "Sorğu rədd edildi.")
                send(
                    result[0],
                    "❌ Çıxarış rədd edildi. "
                    "Balans geri qaytarıldı."
                )
            else:
                send(chat_id, "Sorğu tapılmadı.")
        except (ValueError, IndexError):
            send(chat_id, "İstifadə: /reject ID")
        return

    if text.startswith("/withdraw "):
        wallet = text.split(maxsplit=1)[1].strip()

        # Basic TON address format check.
        if not re.fullmatch(
            r"(EQ|UQ)[A-Za-z0-9_-]{46}", wallet
        ):
            send(
                chat_id,
                "Yanlış TON ünvanı. "
                "EQ və ya UQ ilə başlayan "
                "48 simvollu ünvan daxil et."
            )
            return

        register(user_id)
        result = create_withdrawal(user_id, wallet)

        if not result:
            send(
                chat_id,
                "Minimum çıxarış 0.1 TON-dur."
            )
            return

        wid, amount = result
        send(
            chat_id,
            f"✅ Çıxarış sorğusu #{wid} yaradıldı.\n"
            f"Məbləğ: {ton(amount)} TON\n"
            "Admin yoxlaması gözlənilir."
        )
        send(
            ADMIN_ID,
            f"💸 Yeni çıxarış #{wid}\n"
            f"İstifadəçi: {user_id}\n"
            f"Məbləğ: {ton(amount)} TON\n"
            f"Ünvan: {wallet}\n\n"
            f"Ödənişi həqiqətən göndərdikdən "
            f"sonra /paid {wid}\n"
            f"Rədd etmək: /reject {wid}"
        )
        return

    send(chat_id, "Menyudan seçim et:", menu())


def handle_callback(call):
    user_id = call["from"]["id"]
    chat_id = call["message"]["chat"]["id"]
    action = call["data"]

    register(user_id)

    if action == "ref":
        username = os.environ["BOT_USERNAME"].lstrip("@")
        send(
            chat_id,
            f"🔗 Sənin referal linkin:\n"
            f"https://t.me/{username}?start={user_id}\n\n"
            "Hər təsdiqlənmiş dost: 0.01 TON"
        )

    elif action == "balance":
        amount, count = balance(user_id)
        send(
            chat_id,
            f"💰 Balans: {ton(amount)} TON\n"
            f"👥 Təsdiqlənmiş referallar: {count}"
        )

    elif action == "withdraw":
        send(
            chat_id,
            "💸 Çıxarış üçün belə yaz:\n"
            "/withdraw TON_UNVANIN\n\n"
            "Minimum: 0.1 TON"
        )

    requests.post(
        f"{API}/answerCallbackQuery",
        json={"callback_query_id": call["id"]},
        timeout=5
    )


@app.route("/api/index", methods=["POST"])
@app.route("/telegram", methods=["POST"])
def webhook():
    if request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    ) != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 403

    update = request.get_json(silent=True) or {}

    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_callback(update["callback_query"])

    return jsonify({"ok": True})


@app.route("/api/index", methods=["GET"])
@app.route("/telegram", methods=["GET"])
def health():
    return jsonify({"status": "running"})


# Database tables are created during deployment
# initialization, not on every webhook request.
