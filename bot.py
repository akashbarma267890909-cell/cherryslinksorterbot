import logging
import asyncio
import aiohttp
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TOKEN = "8909435876:AAEYHG1GXb0fDop0rPdpd7wH5fEsRzNLgVk"

async def check_link(session, url, index):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True, ssl=False) as response:
            if response.status < 400:
                return (index, url, True)
            else:
                return (index, url, False)
    except Exception:
        return (index, url, False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to Link Checker Bot!\n\n"
        "Just send me any number of links (one per line or mixed in text) "
        "and I'll check which ones are working ✅\n\n"
        "I'll reply with all working links sorted by number!"
    )

async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    url_pattern = re.compile(r'(https?://[^\s<>"{}|\\^`\[\]]+)', re.IGNORECASE)
    urls = url_pattern.findall(text)

    if not urls:
        await update.message.reply_text("❌ No links found! Please send valid links starting with http:// or https://")
        return

    total = len(urls)
    status_msg = await update.message.reply_text(f"🔍 Checking {total} link(s)... Please wait!")

    async with aiohttp.ClientSession() as session:
        tasks = [check_link(session, url, i+1) for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks)

    working = [(index, url) for index, url, ok in sorted(results) if ok]
    dead = [(index, url) for index, url, ok in sorted(results) if not ok]

    if not working:
        await status_msg.edit_text(
            f"😔 Checked {total} link(s)\n\n"
            f"❌ No working links found! All {total} links are dead or unreachable."
        )
        return

    reply = f"✅ *Working Links* ({len(working)}/{total})\n"
    reply += "─" * 30 + "\n\n"
    for i, (orig_index, url) in enumerate(working, 1):
        reply += f"{i}. {url}\n\n"

    if dead:
        reply += f"\n❌ *Dead Links:* {len(dead)}/{total}"

    await status_msg.edit_text(reply, parse_mode="Markdown")

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_links))
    application.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()
