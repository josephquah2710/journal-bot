import os
import random
from datetime import date

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable not set")

# ===== Your question bank =====
REFLECTION_QUESTIONS = [
    "What was the best moment of today?",
    "What drained your energy today?",
    "What are you grateful for today?",
    "What is one thing you learned today?",
    "What could you do differently tomorrow?",
    "Where did you feel most at peace today?",
    "What was one small win today?",
    "What’s one thing you want to let go of?",
    "What did you avoid today, and why?",
    "Who did you impact today (even a little)?",
]
QUESTIONS_PER_SESSION = 3

# ===== In-memory session state (per user) =====
user_states: dict[int, dict] = {}

# ===== Helpers =====
def ensure_journals_dir() -> None:
    os.makedirs("journals", exist_ok=True)

def journal_filename(user_id: int, day: date) -> str:
    # Separate files per user to avoid mixing everyone's entries
    return f"journals/{user_id}_{day.isoformat()}.txt"

def safe_truncate_for_telegram(text: str, limit: int = 4000) -> str:
    # Telegram message limit is ~4096 chars; keep a buffer
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n(Truncated — use /download for the full file.)"


# ===== Commands =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Time to journal 🙏\n\nHow are you feeling today?")
    user_states[update.effective_user.id] = {"step": "mood"}

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 *Journal Bot Commands*\n\n"
        "/start – Start a new journaling session\n"
        "/today – View today’s saved journal (text)\n"
        "/download – Download today’s journal as a file\n"
        "/help – Show this help message\n",
        parse_mode="Markdown",
    )

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_journals_dir()
    user_id = update.effective_user.id
    today = date.today()
    filename = journal_filename(user_id, today)

    if not os.path.exists(filename):
        await update.message.reply_text("No journal found for today yet. Type /start to write one 🙂")
        return

    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    await update.message.reply_text(safe_truncate_for_telegram(content))

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_journals_dir()
    user_id = update.effective_user.id
    today = date.today()
    filename = journal_filename(user_id, today)

    if not os.path.exists(filename):
        await update.message.reply_text("No journal found for today yet. Type /start to write one 🙂")
        return

    # Send as a file attachment
    with open(filename, "rb") as f:
        await update.message.reply_document(document=f, filename=os.path.basename(filename))


# ===== Message handler (journal flow) =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    if user_id not in user_states:
        await update.message.reply_text("Type /start to begin, or /help to see commands 🙂")
        return

    state = user_states[user_id]

    # Step 1: mood
    if state["step"] == "mood":
        state["mood"] = text
        state["step"] = "events"
        await update.message.reply_text("What happened today?")
        return

    # Step 2: events
    if state["step"] == "events":
        state["events"] = text

        # Pick random questions (no repeats)
        n = min(QUESTIONS_PER_SESSION, len(REFLECTION_QUESTIONS))
        picked = random.sample(REFLECTION_QUESTIONS, k=n)

        state["picked_questions"] = picked
        state["answers"] = []
        state["q_index"] = 0
        state["step"] = "reflection_q"

        await update.message.reply_text(picked[0])
        return

    # Step 3: reflections loop
    if state["step"] == "reflection_q":
        state["answers"].append(text)
        state["q_index"] += 1

        if state["q_index"] < len(state["picked_questions"]):
            await update.message.reply_text(state["picked_questions"][state["q_index"]])
            return

        # Finished: write to journal file
        ensure_journals_dir()
        today = date.today()
        filename = journal_filename(user_id, today)

        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"Date: {today.isoformat()}\n")
            f.write(f"Mood: {state['mood']}\n")
            f.write(f"What happened: {state['events']}\n")
            f.write("Reflections:\n")
            for q, a in zip(state["picked_questions"], state["answers"]):
                f.write(f"- Q: {q}\n")
                f.write(f"  A: {a}\n")
            f.write("\n-----------------\n\n")

        await update.message.reply_text(
            "Journal saved ✅\n\n"
            "Use /today to read it here, or /download to get the file."
        )
        del user_states[user_id]
        return


# ===== App wiring =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("today", today_command))
app.add_handler(CommandHandler("download", download_command))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()