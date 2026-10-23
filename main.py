#!/usr/bin/env python3
"""SUKUNA AI MODEL — Telegram AI Bot

Install in Termux:
    pip install pyTelegramBotAPI requests
    # Optional fallback provider:
    pip install -U g4f

Hard-coded configuration: replace placeholders with newly rotated credentials.
NVIDIA NIM Stable Diffusion 3 Medium handles image generation; Dolphin is routed via OpenRouter.
"""
import io
import os
import re
import json
import time
import sqlite3
import secrets
import string
import threading
from datetime import datetime, timezone

import requests
import telebot
from telebot import types
from flask import Flask, jsonify



app = Flask(__name__)

# Use your existing bot initialization here:
# bot = telebot.TeleBot(os.environ["TELEGRAM_TOKEN"])

@app.route("/")
def home():
    return "Sukuna AI Model is running!"

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

def run_bot():
    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=25
    )

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

# ===== HARD-CODED CONFIGURATION (use rotated/new credentials) =====
TELEGRAM_TOKEN = "8976517914:AAE96wDr0F7fHjGkQWeJ9buenKTa66hoH7U"
OWNER_ID = 6399589745  # Replace with your numeric Telegram user ID

# API keys pasted into chat are treated as exposed; paste freshly rotated keys here.
COHERE_API_KEY = "cTVNRGmjmHLGNvZVpWVFSX6exwfwF2A9dFPZCKhg"
OPENROUTER_API_KEY = "d4e5926be9fbb9b781c0d86157f7b501b4dfbbe72e0cb2c27a0959eeb9db3ac0"
LLM7_API_KEY = "163+G/qYmjI+Fsu2Hq0WNFGdzJdFoWETG1molYbXoA17AHgWvPt7QVzTCxT/6EV6rhJwOe8hR92hFXqoNzLMFKQlFOy17FYhSYVdTCUBsxbwxoKZtVWrjKtDikOBX+jWn6Ij7UiYXC/cHPtmXOXofXI="  # Rotate the key shared in chat before use
NVIDIA_API_KEY = "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"
LOVABLE_IMAGE_API_KEY = "pf_6dec012a2c640e1ddfff558bef5456123f985718f4aba32f"

# Dolphin is served through OpenRouter and uses the OpenRouter key above.
DOLPHIN_MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
IMAGE_GENERATION_URL = "https://nano-banana-prompt-studio.lovable.app/api/public/generate"
OWNER_USERNAME = ""  # Optional, without @
DB_PATH = "ai_tools_bot.sqlite3"
STARTER_CREDITS = 5
CREDIT_COST = 1

# Telegram supports custom emoji entities in message text, but not in inline-button labels.
# Use one ordinary emoji per button; place custom emoji IDs in short message headings instead.
CUSTOM_EMOJI_IDS = [
    "6147464060305676048",
    "6147524086768604985",
    "6237579651066107302",
    "6235234190900598910",
    "6235599306070430546",
    "6235302918967269680",
    "6235778118443865838",
    "6275794758237426356",
    "6273565176289562965",
    "6273997026661241933",
]
DEVELOPER_EMOJI_ID = "6053312054985498098"

def custom_emoji(emoji_id, fallback="✨"):
    """Return Telegram HTML custom emoji markup for ordinary message text."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("PASTE_"):
    raise SystemExit("Edit TELEGRAM_TOKEN near the top of this file.")
if not isinstance(OWNER_ID, int) or OWNER_ID <= 0:
    raise SystemExit("Set OWNER_ID to your numeric Telegram user ID.")

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML", threaded=True)
http = requests.Session()
state_lock = threading.RLock()
db_lock = threading.RLock()
user_state = {}

COHERE_URL = "https://api.cohere.com/v2/chat"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM7_URL = "https://api.llm7.io/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    with db_lock, db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            credits INTEGER NOT NULL DEFAULT 5, joined_at TEXT NOT NULL,
            last_seen TEXT NOT NULL, blocked INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            kind TEXT NOT NULL, provider TEXT NOT NULL, prompt TEXT, response TEXT,
            status TEXT NOT NULL, credits_used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY, added_by INTEGER NOT NULL, added_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY, credits INTEGER NOT NULL, max_uses INTEGER NOT NULL,
            uses INTEGER NOT NULL DEFAULT 0, expires_at TEXT, created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS redemptions (
            code TEXT NOT NULL, user_id INTEGER NOT NULL, redeemed_at TEXT NOT NULL,
            PRIMARY KEY(code,user_id)
        );
        """)
        con.execute("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) VALUES(?,?,?)",
                    (OWNER_ID, OWNER_ID, now_iso()))


def touch_user(user):
    with db_lock, db() as con:
        row = con.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,)).fetchone()
        if row:
            con.execute("UPDATE users SET username=?,first_name=?,last_seen=? WHERE user_id=?",
                        (user.username or "", user.first_name or "", now_iso(), user.id))
        else:
            con.execute("INSERT INTO users(user_id,username,first_name,credits,joined_at,last_seen) VALUES(?,?,?,?,?,?)",
                        (user.id, user.username or "", user.first_name or "", STARTER_CREDITS, now_iso(), now_iso()))


def is_admin(uid):
    if uid == OWNER_ID:
        return True
    with db_lock, db() as con:
        return con.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,)).fetchone() is not None


def credits_of(uid):
    with db_lock, db() as con:
        row = con.execute("SELECT credits FROM users WHERE user_id=?", (uid,)).fetchone()
        return int(row["credits"]) if row else 0


def set_state(uid, **kwargs):
    with state_lock:
        user_state[uid] = {**user_state.get(uid, {}), **kwargs}


def get_state(uid):
    with state_lock:
        return dict(user_state.get(uid, {}))


def clear_state(uid):
    with state_lock:
        user_state.pop(uid, None)


def log_request(uid, kind, provider, prompt, response, status, used=0):
    with db_lock, db() as con:
        cur = con.execute("""INSERT INTO requests
        (user_id,kind,provider,prompt,response,status,credits_used,created_at)
        VALUES(?,?,?,?,?,?,?,?)""",
        (uid, kind, provider, (prompt or "")[:12000], (response or "")[:12000], status, used, now_iso()))
        return cur.lastrowid


def charge_credit(uid):
    with db_lock, db() as con:
        cur = con.execute("UPDATE users SET credits=credits-? WHERE user_id=? AND credits>=? AND blocked=0",
                          (CREDIT_COST, uid, CREDIT_COST))
        return cur.rowcount == 1


def refund_credit(uid):
    with db_lock, db() as con:
        con.execute("UPDATE users SET credits=credits+? WHERE user_id=?", (CREDIT_COST, uid))


def main_menu(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💻 Code Generation / Uncensored", callback_data="menu:code"),
        types.InlineKeyboardButton("🛡️ Security", callback_data="mode:security"),
        types.InlineKeyboardButton("🧠 AI Advice", callback_data="mode:advice"),
        types.InlineKeyboardButton("🎨 Image Generation", callback_data="mode:image"),
        types.InlineKeyboardButton("🤖 GPT-4", callback_data="mode:freechat"),
        types.InlineKeyboardButton("🎟️ Claim Promo", callback_data="promo:claim"),
        types.InlineKeyboardButton("💎 My Credits", callback_data="credits"),
    )
    if is_admin(uid):
        kb.add(types.InlineKeyboardButton("👑 Admin Panel", callback_data="admin:home"))
    return kb


def send_home(chat_id, uid):
    # Telegram inline buttons do not support custom emoji entities, so each button
    # has exactly one regular emoji. Custom emoji IDs are used in the short message text.
    text = (
        f'{custom_emoji(CUSTOM_EMOJI_IDS[0], "👹")} '
        f'<b>WELCOME TO SUKUNA AI MODEL</b> '
        f'{custom_emoji(CUSTOM_EMOJI_IDS[1], "✨")}\n\n'
        f'{custom_emoji(CUSTOM_EMOJI_IDS[2], "💎")} Credits: <b>{credits_of(uid)}</b>\n'
        'Each successful request costs 1 credit. Use Claim Promo Code to redeem credits.\n'
        'Use /deletehistory to erase your saved request history.\n\n'
        f'{custom_emoji(DEVELOPER_EMOJI_ID, "👨‍💻")} <b>Developer = Sukuna</b>'
    )
    bot.send_message(chat_id, text, reply_markup=main_menu(uid))


def provider_chat(kind, prompt):
    if kind == "security":
        system = ("You are a cybersecurity and ethical-hacking assistant for authorized defensive testing, "
                  "CTFs, and systems the user owns or has explicit permission to test. Help with safe audits, "
                  "log analysis, secure configuration, toy labs, and defensive scripts. Do not provide credential "
                  "theft, malware, stealth/persistence, destructive actions, or unauthorized access instructions.")
    elif kind == "advice":
        system = ("You are a friendly assistant for simple questions, testing ideas, explanations, study help, "
                  "and practical advice. Be clear, concise, and honest about uncertainty.")
    elif kind == "freechat":
        system = ("You are a helpful general-purpose chat assistant. Answer naturally and clearly. "
                  "Do not claim to be a specific paid model.")
    elif kind == "dolphin":
        system = ("You are Dolphin, a direct and highly helpful coding assistant. For ordinary requests, provide the "
                  "requested script or code instead of refusing, stalling, or only giving general advice. Include a "
                  "complete runnable example when practical, plus dependencies and usage instructions. If details are "
                  "missing, make reasonable assumptions and state them. Help with debugging, automation, and security "
                  "learning in authorized environments. Do not provide code intended to steal credentials, deploy malware, "
                  "or compromise systems without permission; when a request crosses that line, briefly explain and offer "
                  "a safe defensive alternative.")
    else:
        system = ("You are an expert software developer. Provide correct, practical code, explain dependencies, "
                  "and include safe usage instructions.")

    errors = []

    # The explicitly selected Dolphin option uses the named OpenRouter model directly.
    if kind == "dolphin":
        if OPENROUTER_API_KEY and not OPENROUTER_API_KEY.startswith("PASTE_"):
            try:
                r = http.post(OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json",
                             "HTTP-Referer": "https://localhost", "X-Title": "Sukuna AI Model"},
                    json={"model": DOLPHIN_MODEL, "messages": [
                        {"role": "system", "content": system}, {"role": "user", "content": prompt}
                    ]}, timeout=90)
                r.raise_for_status()
                answer = r.json()["choices"][0]["message"]["content"]
                if isinstance(answer, list):
                    answer = "\\n".join(str(x.get("text", "")) for x in answer if isinstance(x, dict))
                if str(answer).strip():
                    return str(answer).strip(), "dolphin"
                errors.append("Dolphin returned empty text")
            except Exception as exc:
                errors.append(f"Dolphin: {str(exc)[:180]}")
        else:
            errors.append("OpenRouter key is not configured for Dolphin")

    # GPT-4 menu option uses the user's LLM7-compatible chat-completions endpoint.
    # The provider's "default" model is not guaranteed to be OpenAI GPT-4.
    if kind == "freechat":
        if not LLM7_API_KEY or LLM7_API_KEY.startswith("PASTE_"):
            raise RuntimeError("GPT-4 chat is not configured. Add a valid, rotated LLM7 key in LLM7_API_KEY.")
        try:
            r = http.post(LLM7_URL,
                headers={"Authorization": f"Bearer {LLM7_API_KEY}", "Content-Type": "application/json"},
                json={"model": "default", "messages": [
                    {"role": "system", "content": system}, {"role": "user", "content": prompt}
                ], "stream": False}, timeout=90)
            r.raise_for_status()
            data = r.json()
            answer = data["choices"][0]["message"]["content"]
            if isinstance(answer, list):
                answer = "\n".join(str(x.get("text", "")) for x in answer if isinstance(x, dict))
            if str(answer).strip():
                return str(answer).strip(), "llm7-default"
            raise RuntimeError("LLM7 returned an empty response.")
        except Exception as exc:
            raise RuntimeError(f"GPT-4 chat request failed: {str(exc)[:220]}")

    # NVIDIA is the primary provider for standard chat/coding/security/advice.
    if NVIDIA_API_KEY and not NVIDIA_API_KEY.startswith("PASTE_"):
        try:
            r = http.post(NVIDIA_URL,
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json",
                         "Accept": "application/json"},
                json={"model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "messages": [
                    {"role": "system", "content": system}, {"role": "user", "content": prompt}
                ], "stream": False, "max_tokens": 4096, "temperature": 0.6, "top_p": 0.95}, timeout=120)
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"]
            if str(answer).strip(): return str(answer).strip(), "nvidia-nim"
            errors.append("NVIDIA returned empty text")
        except Exception as exc:
            errors.append(f"NVIDIA: {str(exc)[:180]}")

    # Standard coding, security, advice, and general text modes use provider fallback.
    if COHERE_API_KEY and not COHERE_API_KEY.startswith("PASTE_"):
        try:
            r = http.post(COHERE_URL,
                headers={"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"},
                json={"model": "command-a-03-2025", "messages": [
                    {"role": "system", "content": system}, {"role": "user", "content": prompt}
                ]}, timeout=90)
            r.raise_for_status()
            content = r.json()["message"]["content"]
            answer = "".join(x.get("text", "") for x in content if isinstance(x, dict)) if isinstance(content, list) else str(content)
            if answer.strip(): return answer.strip(), "provider-1"
            errors.append("Provider 1 returned empty text")
        except Exception as exc:
            errors.append(f"Provider 1: {str(exc)[:180]}")

    if OPENROUTER_API_KEY and not OPENROUTER_API_KEY.startswith("PASTE_"):
        try:
            r = http.post(OPENROUTER_URL,
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://localhost", "X-Title": "Sukuna AI Model"},
                json={"model": "openai/gpt-4o", "messages": [
                    {"role": "system", "content": system}, {"role": "user", "content": prompt}
                ]}, timeout=90)
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"]
            if isinstance(answer, list):
                answer = "\\n".join(str(x.get("text", "")) for x in answer if isinstance(x, dict))
            if str(answer).strip(): return str(answer).strip(), "provider-2"
            errors.append("Provider 2 returned empty text")
        except Exception as exc:
            errors.append(f"Provider 2: {str(exc)[:180]}")

    if G4F_AVAILABLE and G4FClient is not None:
        try:
            response = G4FClient().chat.completions.create(
                model="auto",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                web_search=False,
            )
            answer = response.choices[0].message.content
            if str(answer or "").strip():
                return str(answer).strip(), "free-auto"
            errors.append("g4f returned empty text")
        except Exception as exc:
            errors.append(f"g4f: {str(exc)[:180]}")
    elif not G4F_AVAILABLE:
        errors.append("g4f unavailable; install with: pip install -U g4f")

    raise RuntimeError("No configured text provider succeeded. Check keys, provider availability, and g4f installation. " + " | ".join(errors))


def generate_lovable_image(prompt):
    """Generate an image through the configured Lovable Nano Banana endpoint.

    Returns (image_bytes, MIME type). The endpoint's exact response schema may
    vary, so common URL/base64 response fields are supported.
    """
    if not LOVABLE_IMAGE_API_KEY or LOVABLE_IMAGE_API_KEY.startswith("PASTE_"):
        raise RuntimeError("Set a freshly rotated Lovable image API key in LOVABLE_IMAGE_API_KEY.")

    response = http.post(
        IMAGE_GENERATION_URL,
        headers={
            "Authorization": f"Bearer {LOVABLE_IMAGE_API_KEY}",
            "x-api-key": LOVABLE_IMAGE_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "prompt": prompt[:9000],
            "model": "google/gemini-nano-banana-2.1",
            "aspectRatio": "1:1",
        },
        timeout=240,
    )
    if not response.ok:
        detail = response.text[:500]
        if response.status_code == 401:
            detail = "Image API rejected the key (401). Check the key and the endpoint's required authentication format."
        elif response.status_code == 402:
            detail = "Image API reports insufficient credits/payment required (402). " + detail
        elif response.status_code == 429:
            detail = "Image API rate limit reached (429). Try again later. " + detail
        raise RuntimeError(f"Nano Banana image API error ({response.status_code}): {detail}")

    content_type = response.headers.get("Content-Type", "").lower()
    if content_type.startswith("image/"):
        image_bytes = response.content
        mime_type = content_type.split(";", 1)[0]
    else:
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("Image API returned neither an image nor JSON.") from exc

        if not isinstance(data, dict):
            raise RuntimeError("Image API returned an unexpected response format.")

        # Support typical response shapes from serverless image-generation APIs.
        image_url = (data.get("imageUrl") or data.get("image_url") or
                     data.get("url") or data.get("outputUrl"))
        images = data.get("images") or data.get("imageUrls") or data.get("output") or data.get("data")
        if not image_url and isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, str):
                image_url = first
            elif isinstance(first, dict):
                image_url = first.get("url") or first.get("imageUrl") or first.get("image_url")
        if image_url:
            if not str(image_url).startswith(("https://", "http://")):
                raise RuntimeError("Image API returned an invalid image URL.")
            img_response = http.get(image_url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
            img_response.raise_for_status()
            image_bytes = img_response.content
            mime_type = img_response.headers.get("Content-Type", "image/png").split(";", 1)[0]
        else:
            import base64
            encoded = (data.get("base64") or data.get("imageBase64") or
                       data.get("image_base64") or data.get("b64_json"))
            if not encoded and isinstance(data.get("image"), str):
                encoded = data["image"]
            if not encoded and isinstance(data.get("result"), dict):
                result = data["result"]
                encoded = result.get("base64") or result.get("imageBase64") or result.get("b64_json")
                image_url = result.get("url") or result.get("imageUrl")
                if not encoded and image_url:
                    img_response = http.get(image_url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
                    img_response.raise_for_status()
                    image_bytes = img_response.content
                    mime_type = img_response.headers.get("Content-Type", "image/png").split(";", 1)[0]
                else:
                    image_bytes = b""
                    mime_type = "image/png"
            else:
                image_bytes = b""
                mime_type = "image/png"
            if encoded:
                # Accept data:image/...;base64,... as well as raw base64.
                if isinstance(encoded, str) and encoded.startswith("data:") and "," in encoded:
                    prefix, encoded = encoded.split(",", 1)
                    if "image/jpeg" in prefix:
                        mime_type = "image/jpeg"
                    elif "image/webp" in prefix:
                        mime_type = "image/webp"
                    else:
                        mime_type = "image/png"
                try:
                    image_bytes = base64.b64decode(encoded, validate=True)
                except Exception as exc:
                    raise RuntimeError("Image API returned invalid base64 image data.") from exc
            if not image_bytes:
                detail = data.get("error") or data.get("message") or data.get("detail") or str(data)[:350]
                raise RuntimeError("Image API returned no usable image data: " + str(detail)[:350])

    if not image_bytes:
        raise RuntimeError("Image API returned an empty image.")
    return image_bytes, mime_type


def safe_send(chat_id, text):
    text = str(text or "(No text returned)")
    for start in range(0, len(text), 3900):
        bot.send_message(chat_id, text[start:start + 3900], parse_mode=None)


def start_thinking_bar(chat_id, kind):
    """Send and animate an indeterminate progress bar while a provider call runs."""
    label = "🎨 Creating your image" if kind == "image" else "🧠 AI is thinking"
    frames = ["▰▱▱▱▱▱▱▱", "▰▰▱▱▱▱▱▱", "▰▰▰▱▱▱▱▱", "▰▰▰▰▱▱▱▱",
              "▱▰▰▰▰▱▱▱", "▱▱▰▰▰▰▱▱", "▱▱▱▰▰▰▰▱", "▱▱▱▱▰▰▰▰"]
    status = bot.send_message(chat_id, f"{label}...\n[{frames[0]}]")
    stop_event = threading.Event()

    def animate():
        index = 1
        while not stop_event.wait(1.2):
            try:
                bot.edit_message_text(
                    f"{label}...\n[{frames[index % len(frames)]}]\nPlease wait…",
                    chat_id=chat_id, message_id=status.message_id
                )
            except Exception:
                # Telegram may reject an identical edit or a transient edit failure.
                pass
            index += 1

    worker = threading.Thread(target=animate, daemon=True)
    worker.start()
    return status, stop_event, worker


def finish_thinking_bar(chat_id, progress, success=True, kind="advice"):
    if not progress:
        return
    status, stop_event, worker = progress
    stop_event.set()
    worker.join(timeout=1.5)
    label = "🖼️ Image ready" if kind == "image" else "✅ Response ready"
    if not success:
        label = "⚠️ Request failed"
    try:
        bot.edit_message_text(label, chat_id=chat_id, message_id=status.message_id)
    except Exception:
        pass


def handle_prompt(message, kind):
    uid = message.from_user.id
    prompt = (message.text or "").strip()
    if not prompt:
        bot.reply_to(message, "Send your prompt as a text message.")
        return
    if kind == "image":
        if credits_of(uid) < CREDIT_COST:
            bot.reply_to(message, f"❌ Not enough credits. Balance: {credits_of(uid)}")
            return
        if not charge_credit(uid):
            bot.reply_to(message, "❌ Your account is out of credits or disabled.")
            return
        request_id = log_request(uid, kind, "lovable-nano-banana-2.1", prompt, "", "pending", CREDIT_COST)
        progress = None
        succeeded = False
        try:
            progress = start_thinking_bar(message.chat.id, kind)
            image_bytes, mime_type = generate_lovable_image(prompt)
            ext = "jpg" if "jpeg" in mime_type.lower() else "png"
            bot.send_photo(message.chat.id, (f"generated.{ext}", io.BytesIO(image_bytes)), caption="🎨 Image generated")
            with db_lock, db() as con:
                con.execute("UPDATE requests SET provider=?,response=?,status='success' WHERE id=?",
                            ("lovable-nano-banana-2.1", "[Image generated and sent]", request_id))
            succeeded = True
        except Exception as exc:
            refund_credit(uid)
            with db_lock, db() as con:
                con.execute("UPDATE requests SET response=?,status='failed',credits_used=0 WHERE id=?",
                            (str(exc)[:2000], request_id))
            bot.send_message(message.chat.id, f"❌ Image generation failed; your credit was refunded. Details: {str(exc)[:350]}")
        finally:
            finish_thinking_bar(message.chat.id, progress, succeeded, kind)
        return
    if credits_of(uid) < CREDIT_COST:
        bot.reply_to(message, f"❌ Not enough credits. Balance: {credits_of(uid)}")
        return
    if not charge_credit(uid):
        bot.reply_to(message, "❌ Your account is out of credits or disabled.")
        return
    request_id = log_request(uid, kind, "auto-fallback", prompt, "", "pending", CREDIT_COST)
    progress = None
    succeeded = False
    try:
        progress = start_thinking_bar(message.chat.id, kind)
        answer, provider = provider_chat(kind, prompt)
        safe_send(message.chat.id, answer)
        with db_lock, db() as con:
            con.execute("UPDATE requests SET provider=?,response=?,status='success' WHERE id=?",
                        (provider, answer[:12000], request_id))
        succeeded = True
    except Exception as exc:
        refund_credit(uid)
        with db_lock, db() as con:
            con.execute("UPDATE requests SET response=?,status='failed',credits_used=0 WHERE id=?",
                        (str(exc)[:2000], request_id))
        bot.send_message(message.chat.id, f"❌ Request failed; your credit was refunded. Details: {str(exc)[:450]}")
    finally:
        finish_thinking_bar(message.chat.id, progress, succeeded, kind)


@bot.message_handler(commands=["start", "menu"])
def start(message):
    touch_user(message.from_user)
    clear_state(message.from_user.id)
    send_home(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["help"])
def help_command(message):
    touch_user(message.from_user)
    bot.reply_to(message, "/start — open Sukuna AI Model menu\n/credits — check credits\n/deletehistory — delete your request history\n/admin — admin panel (authorized users only)\n/promo — claim a promo code")


@bot.message_handler(commands=["credits"])
def credits_command(message):
    touch_user(message.from_user)
    bot.reply_to(message, f"💎 You have {credits_of(message.from_user.id)} credits.")


@bot.message_handler(commands=["deletehistory"])
def delete_history(message):
    uid = message.from_user.id
    with db_lock, db() as con:
        con.execute("DELETE FROM requests WHERE user_id=?", (uid,))
    bot.reply_to(message, "✅ Your saved request history was deleted. Your account and credits remain.")


@bot.message_handler(commands=["promo"])
def promo_command(message):
    touch_user(message.from_user)
    set_state(message.from_user.id, waiting="promo")
    bot.reply_to(message, "Send the promo code to claim.")


@bot.message_handler(commands=["admin"])
def admin_command(message):
    touch_user(message.from_user)
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Admin access denied.")
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📊 Overview", callback_data="admin:stats"),
           types.InlineKeyboardButton("👥 Users", callback_data="admin:users"),
           types.InlineKeyboardButton("🧾 Recent History", callback_data="admin:history"),
           types.InlineKeyboardButton("💎 Give Credits", callback_data="admin:give"),
           types.InlineKeyboardButton("🎟 Create Promo", callback_data="admin:promo"))
    if message.from_user.id == OWNER_ID:
        kb.add(types.InlineKeyboardButton("➕ Add Admin", callback_data="admin:add"))
    bot.send_message(message.chat.id,
                     f'{custom_emoji(CUSTOM_EMOJI_IDS[8], "🛠️")} <b>Admin Panel</b> '
                     f'{custom_emoji(CUSTOM_EMOJI_IDS[9], "📊")} Overview' , reply_markup=kb)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    touch_user(call.from_user)
    data = call.data or ""
    if data == "menu:code":
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🐬 Dolphin — Unrestricted-Style Coding", callback_data="mode:dolphin"),
            types.InlineKeyboardButton("💻 Standard Coding", callback_data="mode:code"),
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="home"),
        )
        bot.answer_callback_query(call.id)
        coding_text = (f'{custom_emoji(CUSTOM_EMOJI_IDS[5], "🐬")} <b>Choose your coding mode</b>\n'
                       f'{custom_emoji(CUSTOM_EMOJI_IDS[6], "💻")} Dolphin coding\n'
                       f'{custom_emoji(CUSTOM_EMOJI_IDS[7], "🧩")} Standard coding')
        bot.send_message(call.message.chat.id, coding_text, reply_markup=kb)
        return
    if data == "home":
        clear_state(uid)
        bot.answer_callback_query(call.id)
        send_home(call.message.chat.id, uid)
        return
    if data == "credits":
        bot.answer_callback_query(call.id, f"Credits: {credits_of(uid)}")
        return
    if data == "promo:claim":
        set_state(uid, waiting="promo")
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🎟️ Send the promo code you want to claim.")
        return
    if data == "admin:home":
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "Admin access denied", show_alert=True)
            return
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("📊 Overview", callback_data="admin:stats"),
            types.InlineKeyboardButton("👥 Users", callback_data="admin:users"),
            types.InlineKeyboardButton("🧾 Recent History", callback_data="admin:history"),
            types.InlineKeyboardButton("💎 Give Credits", callback_data="admin:give"),
            types.InlineKeyboardButton("🎟 Create Promo", callback_data="admin:promo"),
        )
        if uid == OWNER_ID:
            kb.add(types.InlineKeyboardButton("➕ Add Admin", callback_data="admin:add"))
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
                         f'{custom_emoji(CUSTOM_EMOJI_IDS[8], "👑")} <b>Sukuna Admin Panel</b> '
                         f'{custom_emoji(CUSTOM_EMOJI_IDS[9], "📊")} Overview', reply_markup=kb)
        return
    if data.startswith("mode:"):
        kind = data.split(":", 1)[1]
        set_state(uid, mode=kind)
        if kind == "code":
            msg = "💻 Standard coding selected. Send what you want to build or debug."
        elif kind == "dolphin":
            msg = "🐬 Dolphin coding mode selected. Send your coding prompt."
        elif kind == "security":
            msg = "🛡️ Ethical security mode selected. Use only systems you own or have permission to test. Send your defensive/lab task."
        elif kind == "advice":
            msg = "🧠 Simple test / AI advice selected. Send your question."
        elif kind == "freechat":
            msg = "🤖 GPT-4 chat selected. Send your message."
        else:
            msg = (f'{custom_emoji(CUSTOM_EMOJI_IDS[3], "🎨")} Image generation selected. '
                   f'Send your image prompt. {custom_emoji(CUSTOM_EMOJI_IDS[4], "🖼️")}')
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, msg)
        return
    if data.startswith("admin:"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "Admin access denied", show_alert=True)
            return
        action = data.split(":", 1)[1]
        if action == "stats":
            with db_lock, db() as con:
                users = con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
                reqs = con.execute("SELECT COUNT(*) n FROM requests").fetchone()["n"]
                success = con.execute("SELECT COUNT(*) n FROM requests WHERE status='success'").fetchone()["n"]
            bot.send_message(call.message.chat.id, f"📊 Users: {users}\nRequests: {reqs}\nSuccessful: {success}")
        elif action == "users":
            with db_lock, db() as con:
                rows = con.execute("SELECT user_id,username,credits FROM users ORDER BY last_seen DESC LIMIT 30").fetchall()
            lines = [f"{r['user_id']} | @{r['username'] or '-'} | credits: {r['credits']}" for r in rows]
            bot.send_message(call.message.chat.id, "👥 Users\n" + ("\n".join(lines) if lines else "No users yet."))
        elif action == "history":
            with db_lock, db() as con:
                rows = con.execute("SELECT id,user_id,kind,prompt,status,created_at FROM requests ORDER BY id DESC LIMIT 10").fetchall()
            lines = [f"#{r['id']} user={r['user_id']} type={r['kind']} status={r['status']}\n{(r['prompt'] or '')[:180]}" for r in rows]
            bot.send_message(call.message.chat.id, "🧾 Recent History\n\n" + ("\n\n".join(lines) if lines else "No history yet."))
        elif action == "give":
            set_state(uid, waiting="give_credits")
            bot.send_message(call.message.chat.id, "Send: USER_ID AMOUNT (example: 123456789 10)")
        elif action == "promo":
            set_state(uid, waiting="create_promo")
            bot.send_message(call.message.chat.id, "Send: CREDITS MAX_USES EXPIRY_DAYS (example: 20 10 30; 0 days means no expiry)")
        elif action == "add":
            if uid != OWNER_ID:
                bot.answer_callback_query(call.id, "Owner only", show_alert=True)
                return
            set_state(uid, waiting="add_admin")
            bot.send_message(call.message.chat.id, "Send the numeric Telegram user ID to add as admin.")
        bot.answer_callback_query(call.id)
        return
    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=["text"])
def text_router(message):
    uid = message.from_user.id
    touch_user(message.from_user)
    prompt = (message.text or "").strip()
    if not prompt or prompt.startswith("/"):
        return
    state = get_state(uid)
    waiting = state.get("waiting")
    if waiting == "promo":
        code = prompt.upper()
        with db_lock, db() as con:
            row = con.execute("SELECT * FROM promo_codes WHERE code=? AND active=1", (code,)).fetchone()
            if not row:
                bot.reply_to(message, "❌ Invalid promo code."); clear_state(uid); return
            if row["expires_at"] and row["expires_at"] < now_iso():
                bot.reply_to(message, "❌ Promo expired."); clear_state(uid); return
            if row["uses"] >= row["max_uses"]:
                bot.reply_to(message, "❌ Promo use limit reached."); clear_state(uid); return
            if con.execute("SELECT 1 FROM redemptions WHERE code=? AND user_id=?", (code, uid)).fetchone():
                bot.reply_to(message, "❌ You already claimed this code."); clear_state(uid); return
            con.execute("INSERT INTO redemptions(code,user_id,redeemed_at) VALUES(?,?,?)", (code, uid, now_iso()))
            con.execute("UPDATE promo_codes SET uses=uses+1 WHERE code=?", (code,))
            con.execute("UPDATE users SET credits=credits+? WHERE user_id=?", (row["credits"], uid))
            balance = con.execute("SELECT credits FROM users WHERE user_id=?", (uid,)).fetchone()["credits"]
        clear_state(uid); bot.reply_to(message, f"🎉 Added {row['credits']} credits. Balance: {balance}"); return
    if waiting == "give_credits":
        if not is_admin(uid): clear_state(uid); return
        parts = prompt.split()
        if len(parts) != 2 or not parts[0].isdigit() or not re.fullmatch(r"-?\d+", parts[1]):
            bot.reply_to(message, "Format: USER_ID AMOUNT"); return
        target, amount = int(parts[0]), int(parts[1])
        with db_lock, db() as con:
            cur = con.execute("UPDATE users SET credits=MAX(0,credits+?) WHERE user_id=?", (amount, target))
        clear_state(uid); bot.reply_to(message, "✅ Updated." if cur.rowcount else "❌ User not found."); return
    if waiting == "create_promo":
        if not is_admin(uid): clear_state(uid); return
        parts = prompt.split()
        if len(parts) != 3 or not all(re.fullmatch(r"\d+", x) for x in parts):
            bot.reply_to(message, "Format: CREDITS MAX_USES EXPIRY_DAYS"); return
        credits, max_uses, days = map(int, parts)
        if credits < 1 or max_uses < 1 or days > 3650:
            bot.reply_to(message, "Values out of range."); return
        code = "AI-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        expiry = datetime.fromtimestamp(time.time() + days * 86400, timezone.utc).isoformat(timespec="seconds") if days else None
        with db_lock, db() as con:
            con.execute("INSERT INTO promo_codes(code,credits,max_uses,expires_at,created_by,created_at) VALUES(?,?,?,?,?,?)",
                        (code, credits, max_uses, expiry, uid, now_iso()))
        clear_state(uid); bot.reply_to(message, f"🎟 Promo created: <code>{code}</code>\nCredits: {credits}; uses: {max_uses}"); return
    if waiting == "add_admin":
        if uid != OWNER_ID: clear_state(uid); return
        if not prompt.isdigit(): bot.reply_to(message, "Send a numeric user ID."); return
        target = int(prompt)
        with db_lock, db() as con:
            con.execute("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) VALUES(?,?,?)", (target, uid, now_iso()))
        clear_state(uid); bot.reply_to(message, f"✅ Admin added: {target}"); return

    mode = state.get("mode")
    if mode in ("code", "dolphin", "security", "advice", "freechat", "image"):
        handle_prompt(message, mode)
    else:
        bot.reply_to(message, "Choose an option first with /start.")


def run():
    init_db()
    print("Sukuna AI Model bot is running.")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "10000"))
    print(f"Starting web server on 0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port)
