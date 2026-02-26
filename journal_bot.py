from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import date

TOKEN = "8605494964:AAGSYV_PeM_Q7lPY1PreBL5EByb1tuSco6U"

user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Time to journal 🙏\n\nHow are you feeling today?"
    )
    user_states[update.effective_user.id] = {"step": 1}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state["step"] == 1:
        state["mood"] = text
        state["step"] = 2
        await update.message.reply_text("What happened today?")

    elif state["step"] == 2:
        state["events"] = text
        state["step"] = 3
        await update.message.reply_text("Any reflections?")

    elif state["step"] == 3:
        state["reflection"] = text
        
        today = date.today()
        filename = str(today) + ".txt"

        with open(filename, "a") as file:
            file.write(f"Date: {today}\n")
            file.write(f"Mood: {state['mood']}\n")
            file.write(f"What happened: {state['events']}\n")
            file.write(f"Reflection: {state['reflection']}\n")
            file.write("\n-----------------\n")

        await update.message.reply_text("Journal saved ✅")

        del user_states[user_id]

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()