from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIGURAZIONE ---
TOKEN = "8405365834:AAFtpRwrjpN_Q1hcjLTcmlOElp73we0_GwM"
ADMIN_ID = 7079846866
DB_PATH = "abbonati.db"

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        data_iscrizione TEXT,
        data_scadenza TEXT
    )''')
    conn.commit()
    conn.close()

def aggiungi_utente(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    oggi = datetime.now()
    scadenza = oggi + timedelta(days=30)
    c.execute("REPLACE INTO utenti VALUES (?, ?, ?, ?)",
              (user_id, username, oggi.strftime("%Y-%m-%d"), scadenza.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def rinnova_utente(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    oggi = datetime.now()
    nuova_scadenza = oggi + timedelta(days=30)
    c.execute("UPDATE utenti SET data_scadenza = ? WHERE username = ?", (nuova_scadenza.strftime("%Y-%m-%d"), username))
    conn.commit()
    conn.close()
    return c.rowcount > 0

def utenti_in_scadenza():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    oggi = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT username, data_scadenza FROM utenti WHERE data_scadenza <= ?", (oggi,))
    risultati = c.fetchall()
    conn.close()
    return risultati

# --- COMANDI BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono il bot di gestione abbonamenti 💳")

async def entra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    aggiungi_utente(user.id, user.username or user.full_name)
    await update.message.reply_text(f"✅ Registrato {user.username or user.full_name}. Abbonamento valido 30 giorni.")

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Solo l'amministratore può usare questo comando.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, data_scadenza FROM utenti")
    utenti = c.fetchall()
    conn.close()
    if not utenti:
        await update.message.reply_text("Nessun utente registrato.")
        return
    testo = "\n".join([f"@{u[0]} → scadenza: {u[1]}" for u in utenti])
    await update.message.reply_text("📋 Lista utenti:\n" + testo)

async def rinnova(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Solo l'amministratore può rinnovare abbonamenti.")
        return
    if len(context.args) == 0:
        await update.message.reply_text("Uso corretto: /rinnova @username")
        return
    username = context.args[0].replace("@", "")
    if rinnova_utente(username):
        await update.message.reply_text(f"🔁 Abbonamento di @{username} rinnovato per altri 30 giorni!")
    else:
        await update.message.reply_text(f"⚠️ Utente @{username} non trovato nel database.")

# --- CONTROLLO SCADENZE ---
def controllo_scadenze(app):
    risultati = utenti_in_scadenza()
    if risultati:
        for username, data in risultati:
            app.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ L'abbonamento di @{username} è scaduto il {data}")

# --- MAIN ---
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("entra", entra))
    app.add_handler(CommandHandler("lista", lista))
    app.add_handler(CommandHandler("rinnova", rinnova))

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: controllo_scadenze(app), 'interval', days=1)
    scheduler.start()

    print("🤖 Bot avviato...")
    app.run_polling()

