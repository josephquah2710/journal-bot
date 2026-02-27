import os
import json
import random
from datetime import date

import psycopg
from psycopg.rows import dict_row

#====================
#get random entry function for /random command
#====================
def get_random_entry(user_id: int):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT entry_date, mood, events, reflections, created_at
                FROM journal_entries
                WHERE user_id = %s
                ORDER BY RANDOM()
                LIMIT 1
                """,
                (user_id,),
            )
            return cur.fetchone()

#====================
#put date time functions to read specific date journal entries, e.g. /entry 2024-06-01
#====================
from datetime import datetime, date
from typing import Optional

def parse_dd_mm_yyyy(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%d-%m-%Y").date()
    except ValueError:
        return None

def get_entry_by_date(user_id: int, entry_date: date):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT entry_date, mood, events, reflections, created_at
                FROM journal_entries
                WHERE user_id=%s AND entry_date=%s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, entry_date),
            )
            return cur.fetchone()

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =====================
# Environment variables
# =====================
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("TOKEN environment variable not set")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

# =====================
# Reflection questions
# =====================
REFLECTION_QUESTIONS = [
    "What was the best moment of today?",
    "What drained your energy today?",
    "What are you grateful for today?",
    "What is one thing you learned today?",
    "What could you do differently tomorrow?",
    "Where did you feel most at peace today?",
    "What was one small win today?",
    "What’s one thing you want to let go of?",
    "Who made a positive impact on your day?",
    "What’s one thing you want to remember from today?",
]

QUESTIONS_PER_SESSION = 3

# =====================
# In-memory user state
# =====================
user_states: dict[int, dict] = {}

# =====================
# Step 4 — Initialise DB
# =====================
def init_db():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    entry_date DATE NOT NULL,
                    mood TEXT,
                    events TEXT,
                    reflections JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_date
                ON journal_entries (user_id, entry_date);
            """)
        conn.commit()

init_db()

# =====================
# Step 5 — Save journal
# =====================
def save_entry(user_id: int, mood: str, events: str, qa_pairs: list[dict]):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO journal_entries
                (user_id, entry_date, mood, events, reflections)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    date.today(),
                    mood,
                    events,
                    json.dumps(qa_pairs),
                ),
            )
        conn.commit()

# =====================
# Step 6 — Read today
# =====================
def get_today_entry(user_id: int):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT entry_date, mood, events, reflections
                FROM journal_entries
                WHERE user_id=%s AND entry_date=%s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, date.today()),
            )
            return cur.fetchone()

# =====================
# Step 7 - Download command
# =====================        
from io import BytesIO

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Accept: /download or /download DD-MM-YYYY
    if len(context.args) == 0:
        target_date = date.today()
    else:
        target_date = parse_dd_mm_yyyy(context.args[0])
        if not target_date:
            await update.message.reply_text("Use: /download DD-MM-YYYY (example: /download 26-02-2026)")
            return

    entry = get_entry_by_date(user_id, target_date)
    if not entry:
        await update.message.reply_text(f"No journal found for {target_date}.")
        return

    lines = []
    lines.append(f"Date: {entry['entry_date']}")
    lines.append(f"Saved: {entry['created_at']}")
    lines.append("")
    lines.append(f"Mood: {entry['mood']}")
    lines.append("")
    lines.append("What happened:")
    lines.append(entry["events"] or "")
    lines.append("")
    lines.append("Reflections:")
    for item in entry["reflections"]:
        lines.append(f"- Q: {item['q']}")
        lines.append(f"  A: {item['a']}")
        lines.append("")

    content = "\n".join(lines)

    buf = BytesIO(content.encode("utf-8"))
    buf.name = f"journal_{entry['entry_date']}.txt"

    await update.message.reply_document(document=buf, filename=buf.name)        

# =====================
# Bot commands
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Time to journal 🙏\n\nHow are you feeling today?")
    user_states[update.effective_user.id] = {"step": "mood"}

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    entry = get_today_entry(user_id)

    if not entry:
        await update.message.reply_text("No journal found for today yet.")
        return

    text = (
        f"🗓 {entry['entry_date']}\n\n"
        f"Mood: {entry['mood']}\n\n"
        f"What happened:\n{entry['events']}\n\n"
        "Reflections:\n"
    )

    for item in entry["reflections"]:
        text += f"- {item['q']}\n  {item['a']}\n"

    await update.message.reply_text(text[:4000])

async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id 

 # Accept: /view or /view DD-MM-YYYY
    if len(context.args) == 0:
        target_date = date.today()
    else:
        target_date = parse_dd_mm_yyyy(context.args[0])
        if not target_date:
            await update.message.reply_text("Use: /view DD-MM-YYYY (example: /view 26-02-2026)")
            return

    entry = get_entry_by_date(user_id, target_date)
    if not entry:
        await update.message.reply_text(f"No journal found for {target_date}.")
        return

    text = (
        f"🗓 {entry['entry_date']} (latest)\n\n"
        f"Mood: {entry['mood']}\n\n"
        f"What happened:\n{entry['events']}\n\n"
        "Reflections:\n"
    )
    for item in entry["reflections"]:
        text += f"- {item['q']}\n  {item['a']}\n"

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    entry = get_random_entry(user_id)

    if not entry:
        await update.message.reply_text("No journal entries found yet. Write one with /start 🙂")
        return

    text = (
        f"🎲 Random Journal Entry\n"
        f"🗓 {entry['entry_date']}\n\n"
        f"Mood: {entry['mood']}\n\n"
        f"What happened:\n{entry['events']}\n\n"
        "Reflections:\n"
    )

    for item in entry["reflections"]:
        text += f"- {item['q']}\n  {item['a']}\n"

    await update.message.reply_text(text[:4000])

 # Telegram limit safety
    await update.message.reply_text(text[:4000])

# =====================
# Journal flow
# =====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_states:
        await update.message.reply_text("Type /start to begin journaling.")
        return

    state = user_states[user_id]

    if state["step"] == "mood":
        state["mood"] = text
        state["step"] = "events"
        await update.message.reply_text("What happened today?")
        return

    if state["step"] == "events":
        state["events"] = text

        picked = random.sample(
            REFLECTION_QUESTIONS,
            k=min(QUESTIONS_PER_SESSION, len(REFLECTION_QUESTIONS)),
        )

        state["picked"] = picked
        state["answers"] = []
        state["index"] = 0
        state["step"] = "reflection"

        await update.message.reply_text(picked[0])
        return

    if state["step"] == "reflection":
        state["answers"].append(text)
        state["index"] += 1

        if state["index"] < len(state["picked"]):
            await update.message.reply_text(state["picked"][state["index"]])
            return

        qa_pairs = [
            {"q": q, "a": a}
            for q, a in zip(state["picked"], state["answers"])
        ]

        save_entry(
            user_id=user_id,
            mood=state["mood"],
            events=state["events"],
            qa_pairs=qa_pairs,
        )

        await update.message.reply_text("Journal saved ✅\nUse /today to read it.")
        del user_states[user_id]

# =====================
# App wiring
# =====================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today_command))
app.add_handler(CommandHandler("view", view_command))
app.add_handler(CommandHandler("download", download_command))
app.add_handler(CommandHandler("random", random_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()