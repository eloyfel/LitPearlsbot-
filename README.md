litPearls Balance Bot
Telegram bot that reports a wallet's litPearls (LITPEARLS / "Illuminated
Pearls") balance and the token's total supply, on the LitVM LiteForge
testnet.
Contract: 0xE67adF135ea6a3a658d0DC6aEEcbcA916eBfB49E (verified ERC-20,
18 decimals).
Three ways to use it
Just send a wallet address — in a DM to the bot, it replies
automatically with the balance + total supply. No command needed.
Inline mode (works in ANY Telegram chat, no need to add the bot):
Type @YourBotName 0xWalletAddress in any chat, tap the result, and it
posts the balance + total supply.
Direct command (DM or groups where the bot is added):
/balance 0xWalletAddress
Setup
Create a bot with @BotFather if you haven't
already, and grab the bot token.
Enable inline mode for your bot: message @BotFather →
/setinline → choose your bot → set a placeholder text
(e.g. "Enter a wallet address...").
For groups, to have the bot reply to a bare wallet address without
being @-mentioned first: message @BotFather → /setprivacy → choose
your bot → Disable. (Not needed for DMs — this only affects
group chats.)
Copy .env.example to .env and fill in TELEGRAM_BOT_TOKEN.
Install dependencies:
Bash
Run it:
Bash
The bot polls Telegram for updates — no public URL/webhook needed, so you
can run it from your own machine or any always-on server.
Notes
Balances and total supply are read live from the LitVM LiteForge RPC
(https://liteforge.rpc.caldera.xyz/http) on every query — no caching of
balances, so the numbers are always current on-chain.
If you ever redeploy the token to a new address, just update
LITPEARLS_CONTRACT_ADDRESS in .env.
