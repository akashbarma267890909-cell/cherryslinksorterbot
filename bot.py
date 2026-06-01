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

async def check_telegram_link(session, url, index):
    """Check Telegram invite/channel links using Telegram's own API."""
    try:
        # Extract invite hash from t.me/+HASH or t.me/joinchat/HASH
        invite_match = re.search(r't\.me/\+([A-Za-z0-9_-]+)', url)
        joinchat_match = re.search(r't\.me/joinchat/([A-Za-z0-9_-]+)', url)
        username_match = re.search(r't\.me/([A-Za-z0-9_]+)$', url)

        if invite_match or joinchat_match:
            hash_val = invite_match.group(1) if invite_match else joinchat_match.group(1)
            api_url = f"https://api.telegram.org/bot{TOKEN}/checkChatInviteLink"
            async with session.post(api_url, json={"invite_link": f"https://t.me/+{hash_val}"}, ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return (index, url, True)
                else:
                    return (index, url, False)

        elif username_match:
            username = username_match.group(1)
            # Skip common non-channel paths
            if username.lower() in ["addlist", "share", "joinchat"]:
                return (index, url, False)
            api_url = f"https://api.telegram.org/bot{TOKEN}/getChat"
            async with session.post(api_url, json={"chat_id": f"@{username}"}, ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return (index, url, True)
                else:
                    return (index, url, False)

        else:
            # For addlist or unknown t.me formats, do a plain HTTP check
            headers = {"User-Agent": "Mozilla/5.0"}
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True, ssl=False, headers=headers) as response:
                if response.status < 400:
                    return (index, url, True)
                return (index, url, False)

    except Exception as e:
        logger.error(f"Error checking {url}: {e}")
        return (index, url, False)

async def check_regular_link(session, url, index):
    """Check non-Telegram links."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0 Safari/537.36"}
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True, ssl=False, headers=headers) as response:
            if response.status in [404, 410, 500, 502, 503, 504]:
                return (index, url, False)
            elif response.status < 400:
                return (index, url, True)
            else:
                return (index, url, False)
    except Exception:
        return (index, url, False)

async def check_link(session, url, index):
    if "t.me" in url:
        return await check_telegram_link(session, url, index)
    else:
        return await check_regular_link(session, url, index)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to Link Checker Bot!\n\n"
        "Send me any Telegram links and I'll check which ones are actually working ✅\n\n"
        "I'll reply with only the valid/active links!"
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
        reply += f"❌ Dead/Expired: {len(dead)}/{total}"

    await status_msg.edit_text(reply)

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_links))
    application.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()
