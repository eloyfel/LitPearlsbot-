"""
litPearls Balance Bot
----------------------
A Telegram bot that reports a wallet's litPearls (LITPEARLS) balance
and the token's total supply on the LitVM LiteForge testnet.

Works two ways:
  1. Inline mode  -> type "@YourBotName 0xAddress..." in ANY chat,
     even ones the bot was never added to.
  2. Direct command -> "/balance 0xAddress..." in a DM or in a group
     where the bot has been added.

Set your config in a .env file (see .env.example) before running.
"""

import logging
import os
import re
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)
from web3 import Web3

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RPC_URL = os.environ.get("LITVM_RPC_URL", "https://liteforge.rpc.caldera.xyz/http")
TOKEN_CONTRACT_ADDRESS = os.environ.get(
    "LITPEARLS_CONTRACT_ADDRESS", "0xE67adF135ea6a3a658d0DC6aEEcbcA916eBfB49E"
)
TOKEN_NAME = "litPearls"
LOGO_PATH = os.environ.get(
    "LITPEARLS_LOGO_PATH",
    os.path.join(os.path.dirname(__file__), "assets", "litpearls_logo.jpg"),
)
# Public raw URL for the logo, used in inline mode (Telegram requires a public
# URL or a previously-uploaded file_id — a local file path won't work there).
LOGO_URL = os.environ.get(
    "LITPEARLS_LOGO_URL",
    "https://raw.githubusercontent.com/eloyfel/LitPearlsbot-/main/assets/litpearls_logo.jpg",
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Minimal ERC-20 ABI: just the read-only calls we need.
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
token = w3.eth.contract(
    address=Web3.to_checksum_address(TOKEN_CONTRACT_ADDRESS), abi=ERC20_ABI
)

ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")

# Cache decimals once, they never change.
_decimals_cache = None


def get_decimals() -> int:
    global _decimals_cache
    if _decimals_cache is None:
        _decimals_cache = token.functions.decimals().call()
    return _decimals_cache


def format_amount(raw_amount: int, decimals: int) -> str:
    """Turn a raw on-chain integer amount into a human-readable string."""
    value = Decimal(raw_amount) / (Decimal(10) ** decimals)
    # Show up to 4 decimal places, trim trailing zeros, keep thousands separators.
    quantized = value.quantize(Decimal("1.0000")) if value != value.to_integral() else value
    text = f"{quantized:,.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def fetch_balance_and_supply(address: str):
    """Returns (balance_str, supply_str, symbol) for a given wallet address."""
    checksum_address = Web3.to_checksum_address(address)
    decimals = get_decimals()

    raw_balance = token.functions.balanceOf(checksum_address).call()
    raw_supply = token.functions.totalSupply().call()
    symbol = token.functions.symbol().call()

    balance_str = format_amount(raw_balance, decimals)
    supply_str = format_amount(raw_supply, decimals)

    return balance_str, supply_str, symbol


def build_caption(address: str) -> str:
    try:
        balance_str, supply_str, symbol = fetch_balance_and_supply(address)
    except Exception as exc:  # noqa: BLE001 - surface any RPC/contract error to the user
        logger.exception("Failed to fetch balance for %s", address)
        return f"⚠️ Couldn't fetch balance for `{address}`.\nError: {exc}"

    return (
        f"💎 *{TOKEN_NAME} Balance*\n"
        f"Wallet: `{address}`\n"
        f"Balance: *{balance_str} {symbol}*\n\n"
        f"🌐 *Total Supply*: {supply_str} {symbol}"
    )


async def send_balance_card(message, address: str):
    """Sends the litPearls logo image with the balance/supply as its caption."""
    caption = build_caption(address)
    try:
        with open(LOGO_PATH, "rb") as photo:
            await message.reply_photo(photo=photo, caption=caption, parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        logger.warning("Logo image not found at %s, falling back to text-only reply", LOGO_PATH)
        await message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I report *litPearls* balances on the LitVM LiteForge testnet.\n\n"
        "Just send me a wallet address and I'll reply with its balance and "
        "the token's total supply — no command needed.\n\n"
        "You can also:\n"
        "• Use /balance <wallet address>\n"
        "• Type @{bot} <wallet address> in *any* Telegram chat (inline mode) — "
        "no need to add me to the group!".format(bot=context.bot.username),
        parse_mode=ParseMode.MARKDOWN,
    )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /balance <wallet address>\nExample: /balance 0x1234...abcd"
        )
        return

    address = context.args[0]
    if not ADDRESS_RE.fullmatch(address):
        await update.message.reply_text("That doesn't look like a valid wallet address.")
        return

    await send_balance_card(update.message, address)


async def address_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Replies with the balance whenever a message contains a wallet address —
    no /balance command or @mention needed. Works automatically in DMs.
    In groups, this only fires if the bot's privacy mode is disabled via
    @BotFather (/setprivacy -> Disable), otherwise Telegram only forwards
    messages that mention the bot or reply to it."""
    message = update.effective_message
    if not message or not message.text:
        return

    match = ADDRESS_RE.search(message.text)
    if not match:
        return  # not an address, ignore silently (don't spam the chat)

    await send_balance_card(message, match.group(0))


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles @BotName 0xAddress typed in ANY chat, even without adding the bot."""
    query = update.inline_query.query.strip()
    match = ADDRESS_RE.search(query)

    if not match:
        await update.inline_query.answer(
            [
                InlineQueryResultArticle(
                    id="help",
                    title="Type or paste a wallet address",
                    description="e.g. 0x1234...abcd",
                    input_message_content=InputTextMessageContent(
                        "Type a valid wallet address after my name to check its "
                        "litPearls balance, e.g. `@{bot} 0x1234...abcd`".format(
                            bot=context.bot.username
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                    ),
                )
            ],
            cache_time=1,
        )
        return

    address = match.group(0)

    try:
        balance_str, supply_str, symbol = fetch_balance_and_supply(address)
        title = f"{balance_str} {symbol}"
        description = f"Total supply: {supply_str} {symbol}"
        caption = build_caption(address)

        await update.inline_query.answer(
            [
                InlineQueryResultPhoto(
                    id=address,
                    photo_url=LOGO_URL,
                    thumbnail_url=LOGO_URL,
                    title=title,
                    description=description,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
            ],
            cache_time=10,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Inline query failed for %s", address)
        await update.inline_query.answer(
            [
                InlineQueryResultArticle(
                    id=address,
                    title="Couldn't fetch balance",
                    description=str(exc),
                    input_message_content=InputTextMessageContent(
                        f"⚠️ Couldn't fetch balance for `{address}`.\nError: {exc}",
                        parse_mode=ParseMode.MARKDOWN,
                    ),
                )
            ],
            cache_time=1,
        )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, address_message))

    logger.info("litPearls bot starting (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
