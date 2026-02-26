# reflection-questions-enabled
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

# ✅ Your question bank (edit freely)
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

QUESTIONS_PER_SESSION = 3  # change this to 1, 2, 5, etc.

user_states = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Time to journal 🙏\n\nHow are you feeling today?")
    user_states[update.effective_user.id] = {"step": "mood"}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_states:
        # If user didn't type /start, guide them.
        await update.message.reply_text("Type /start to begin your journal 🙂")
        return

    state = user_states[user_id]

    # Step 1: Mood
    if state["step"] == "mood":
        state["mood"] = text
        state["step"] = "events"
        await update.message.reply_text("What happened today?")
        return

    # Step 2: Events
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

    # Step 3: Reflection questions loop
    if state["step"] == "reflection_q":
        # Save answer to current question
        state["answers"].append(text)
        state["q_index"] += 1

        # Ask next question, or finish
        if state["q_index"] < len(state["picked_questions"]):
            next_q = state["picked_questions"][state["q_index"]]
            await update.message.reply_text(next_q)
            return

        # Finish: write everything to file
        today = date.today()
        os.makedirs("journals", exist_ok=True)
        filename = f"journals/{today}.txt"

        with open(filename, "a", encoding="utf-8") as file:
            file.write(f"Date: {today}\n")
            file.write(f"Mood: {state['mood']}\n")
            file.write(f"What happened: {state['events']}\n")
            file.write("Reflections:\n")
            for q, a in zip(state["picked_questions"], state["answers"]):
                file.write(f"- Q: {q}\n")
                file.write(f"  A: {a}\n")
            file.write("\n-----------------\n")

        await update.message.reply_text("Journal saved ✅")
        del user_states[user_id]
        return

async def today_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    filename = f"journals/{today}.txt"

    if not os.path.exists(filename):
        await update.message.reply_text("No journal found for today.")
        return

    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()

    # Telegram message limit safety
    if len(content) > 4000:
        content = content[:4000] + "\n\n(Truncated)"

    await update.message.reply_text(content)

app.add_handler(CommandHandler("today", today_journal))
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()