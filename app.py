# app.py - Bot Telegram per gestione abbonamenti
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
import os
import asyncio

# === CONFIG ===
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === DATABASE ===
def init_db():
    conn = sqlite3.connect("members.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            join_date TEXT,
            expiry_date TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_member(username, join_date=None):
    conn = sqlite3.connect("members.db")
    c = conn.cursor()
    now = datetime.now() if not join_date else datetime.strptime(join_date, "%Y-%m-%d")
    expiry = now + timedelta(days=30)
    c.execute("""
        INSERT OR REPLACE INTO members (username, join_date, expiry_date)
        VALUES (?, ?, ?)
    """, (username, now.strftime("%Y-%m-%d"), expiry.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def renew_member(username):
    conn = sqlite3.connect("members.db")
    c = conn.cursor()
    expiry = datetime.now() + timedelta(days=30)
    c.execute("UPDATE members SET expiry_date = ? WHERE username = ?", (expiry.strftime("%Y-%m-%d"), username))
    conn.commit()
    conn.close()

def remove_member(username):
    conn = sqlite3.connect("members.db")
    c = conn.cursor()
    c.execute("DELETE FROM members WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def get_expired_members():
    conn = sqlite3.connect("members.db")
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT username FROM members WHERE expiry_date <= ?", (today,))
    expired = [row[0] for row in c.fetchall()]
    conn.close()
    return expired

# === COMANDI ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Benvenuto!\n"
        "Usa /registra <username> [YYYY-MM-DD] per aggiungere un utente\n"
        "Usa /rinnova <username> per rinnovare\n"
        "Usa /rimuovi <username> per rimuovere\n"
        "Usa /lista per vedere tutti gli utenti."
    )

async def registra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Usa: /registra <username> [YYYY-MM-DD]")
        return
    username = context.args[0].replace("@", "")
    join_date = context.args[1] if len(context.args) > 1 else None
    add_member(username, join_date)
    await update.message.reply_text(f"✅ Utente @{username} registrato con scadenza tra 30 giorni.")

async def rinnova(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usa: /rinnova <username>")
        return
    username = context.args[0].replace("@", "")
    renew_member(username)
    await update.message.reply_text(f"🔁 Abbonamento di @{username} rinnovato per altri 30 giorni.")

async def rimuovi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usa: /rimuovi <username>")
        return
    username = context.args[0].replace("@", "")
    remove_member(username)
    await update.message.reply_text(f"❌ Utente @{username} rimosso dalla lista.")

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("members.db")
    c = conn.cursor()
    c.execute("SELECT username, expiry_date FROM members")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 Nessun utente registrato.")
        return

    text = "\n".join([f"@{u} → scade il {d}" for u, d in rows])
    await update.message.reply_text("📋 Lista utenti:\n" + text)

# === SCHEDULER ===
async def avvisa_scadenze(app):
    expired = get_expired_members()
    if expired and ADMIN_CHAT_ID:
        text = "⚠️ Utenti con abbonamento scaduto:\n" + "\n".join([f"@{u}" for u in expired])
        await app.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)

def start_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: asyncio.run(avvisa_scadenze(app)), "interval", days=1)
    scheduler.start()

# === MAIN ===
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("registra", registra))
    app.add_handler(CommandHandler("rinnova", rinnova))
    app.add_handler(CommandHandler("rimuovi", rimuovi))
    app.add_handler(CommandHandler("lista", lista))

    start_scheduler(app)

    print("🤖 Bot avviato correttamente su Render.")
    app.run_polling()
