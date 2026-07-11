import json
import os
import re
from datetime import datetime
import speech_recognition as sr
from pydub import AudioSegment
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 📍 YOUR ACTUAL TOKEN FROM BOTFATHER
TOKEN = "8808729776:AAF0lgkAeAUdEkr_jrRjTSrlVvgViI0Afpg"
JSON_FILE = "expenses.json"

def save_expense(user_id, amount, category):
    data = {}
    if os.path.exists(JSON_FILE) and os.path.getsize(JSON_FILE) > 0:
        try:
            with open(JSON_FILE, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    
    user_str = str(user_id)
    if user_str not in data:
        data[user_str] = []
        
    expense_entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "category": category
    }
    data[user_str].append(expense_entry)
    with open(JSON_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Streamlined parser: extracts numbers and decimals, ignores leading text
def process_expense_text(text, user_id):
    text = text.strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(.+)$", text)
    
    if not match:
        return f"Could not parse expense from: \"{text}\". Please make sure it contains a number. (Example: `10.55 Lunch` or `10.55咖啡`)"
        
    try:
        amount = float(match.group(1))
        category = match.group(2).strip()
        
        save_expense(user_id, amount, category)
        return f"✅ Recorded: ${amount:.2f} for {category}!"
    except Exception as e:
        return f"❌ Error saving expense: {e}"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! You can now type OR send a voice note for your expenses.\n\n"
        "**Format:** `[Amount] [Category]`\n"
        "**English Example:** Speak or type `10.55 Lunch`\n"
        "**Mandarin Example:** Speak or type `10.55咖啡`\n\n"
        "💡 **Commands (Type or Speak them):**\n"
        "▫️ Balance / 总额 - Check total spent\n"
        "▫️ Summary / 总结 - Check breakdown by category",
        parse_mode="Markdown"
    )

# 💰 /balance functionality
async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    total_spent = 0.0
    
    if os.path.exists(JSON_FILE) and os.path.getsize(JSON_FILE) > 0:
        try:
            with open(JSON_FILE, 'r') as f:
                data = json.load(f)
            if user_id in data:
                for entry in data[user_id]:
                    total_spent += float(entry.get("amount", 0))
        except Exception as e:
            await update.message.reply_text(f"❌ Error reading history: {e}")
            return

    await update.message.reply_text(f"📊 **Your Total Expenses Balance:**\n\n💰 Total Spent: **${total_spent:.2f}**", parse_mode="Markdown")

# 📋 /summary functionality
async def check_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    category_totals = {}
    total_spent = 0.0
    
    if os.path.exists(JSON_FILE) and os.path.getsize(JSON_FILE) > 0:
        try:
            with open(JSON_FILE, 'r') as f:
                data = json.load(f)
                
            if user_id in data and len(data[user_id]) > 0:
                for entry in data[user_id]:
                    amt = float(entry.get("amount", 0))
                    cat = entry.get("category", "Unknown").strip()
                    
                    total_spent += amt
                    category_totals[cat] = category_totals.get(cat, 0.0) + amt
            else:
                await update.message.reply_text("You haven't recorded any expenses yet!")
                return
        except Exception as e:
            await update.message.reply_text(f"❌ Error reading summary: {e}")
            return

    summary_text = "📊 **Expense Breakdown Summary:**\n\n"
    for category, total in category_totals.items():
        summary_text += f"▪️ {category}: **${total:.2f}**\n"
        
    summary_text += f"\n📉 Grand Total: **${total_spent:.2f}**"
    await update.message.reply_text(summary_text, parse_mode="Markdown")

# Handles normal typed text messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = process_expense_text(update.message.text, update.message.from_user.id)
    await update.message.reply_text(response)

# Handles voice notes and routes keywords dynamically
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    status_message = await update.message.reply_text("🗣️ Processing voice message...")
    
    ogg_path = f"voice_{user_id}.ogg"
    wav_path = f"voice_{user_id}.wav"
    
    try:
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        await voice_file.download_to_drive(ogg_path)
        
        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(wav_path, format="wav")
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source)
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="zh-CN")
            
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(wav_path): os.remove(wav_path)
        
        await status_message.edit_text(f"📝 Transcribed: \"{text}\"")
        
        # Check if the transcription matches voice command keywords
        clean_text = text.lower().strip()
        
        if "summary" in clean_text or "总结" in clean_text:
            await check_summary(update, context)
            return
            
        if "balance" in clean_text or "结算" in clean_text or "总额" in clean_text:
            await check_balance(update, context)
            return
            
        # Process as regular expense if no command word matches
        response = process_expense_text(text, user_id)
        await update.message.reply_text(response)
        
    except sr.UnknownValueError:
        await status_message.edit_text("😢 Sorry, I couldn't recognize the audio clearly.")
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(wav_path): os.remove(wav_path)
    except Exception as e:
        await status_message.edit_text(f"❌ Error processing voice: {e}")
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(wav_path): os.remove(wav_path)

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Registered Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", check_balance))
    app.add_handler(CommandHandler("summary", check_summary))
    
    # Message listeners
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    print("Bot is starting up locally with full Voice & Commands support...")
    app.run_polling()

if __name__ == '__main__':
    main()