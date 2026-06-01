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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0 Safari/537.36"
        }
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=True,
            ssl=False,
            headers=headers
        ) as response:
            # 200-299 = working, 301/302 = redirect (follow), 403 = forbidden but exists
            # 404 = not found, 410 = gone, 5xx = server error
            if response.status in [404, 410, 500, 502, 503, 504]:
                return (index, url, False)
            elif response.status < 400:
                return (index, url, True)
            else:
                return (index, url, False)
    except asyncio.TimeoutError:
        return (index, url, False)
    except Exception:
        return (index, url, False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to Link Checker Bot!\n\n"
        "Just send me any number of links and I'll check which ones are working ✅\n\n"
        "I'll reply with only the working links sorted by number!"
    )

async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    url_pattern = re.compile(r'(https?://[^\s<>"{}|\\^`\[\]]+)', re.IGNORECASE)
    urls = url_pattern.findall(text)

    # Remove duplicates while keeping order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    urls = unique_urls

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
            f"😔 Checked {total} link(s)\n\n❌ No working links found!\nAll {total} links are dead or expired."
        )
        return

    reply = f"✅ Working Links ({len(working)}/{total})\n"
    reply += "──────────────────────\n\n"
    for i, (orig_index, url) in enumerate(working, 1):
        reply += f"{i}. {url}\n\n"

    if dead:
        reply += f"❌ Dead/Expired Links: {len(dead)}/{total}"

    await status_msg.edit_text(reply)

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_links))
    application.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()
