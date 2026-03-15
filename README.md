
# tg-profile-valuator

A Telegram bot that calculates the total value of any Telegram account — collectible usernames, unique gifts, floor prices, and historical TON data.

---

## Features

- **Username Valuation** — fetches the purchase price of every collectible username on a profile using Fragment's API
- **Historical TON Price** — shows what each username was bought for at the time of purchase, not just today's price
- **Current Value** — also shows what those same usernames are worth right now
- **Collectible Gift Prices** — for every unique gift (Plush Pepe, Snoop Dogg, Khabib etc.), shows:
  - Price set by the user
  - Floor price (cheapest listed on the market)
  - Last sale price and date
  - Whether that specific serial is currently listed for sale
- **Regular Gift Summary** — groups all non-collectible gifts by type with total star count
- **Full Profile Summary** — total value two ways: by user-set value and by floor price, in TON and USD
- **Admin-only Login** — only the bot owner can connect a Telegram account via phone + OTP + 2FA
- **Expandable Sections** — usernames, collectibles and regular gifts each collapsed in a blockquote, tap to expand
- **Anyone Can Check** — just send @username, no commands needed

---

## How It Works

The bot uses a Telethon userbot (your personal Telegram account) running alongside a regular bot token. The userbot makes MTProto API calls that a normal bot token cannot — specifically `fragment.GetCollectibleInfo` for username prices and `payments.GetUniqueStarGiftValueInfo` for gift data.

---

## Setup

### 1. Get your credentials

| Credential | Where to get it |
|---|---|
| Bot token | [@BotFather](https://t.me/BotFather) → /newbot |
| API ID + API Hash | [my.telegram.org](https://my.telegram.org) → API development tools |
| Admin ID | [@userinfobot](https://t.me/userinfobot) |

### 2. Configure `.env`

```env
BOT_TOKEN=your_bot_token
API_ID=12345678
API_HASH=your_api_hash
ADMIN_ID=your_telegram_user_id
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python bot.py
```

### 5. Login via the bot

Send `/start` to your bot → tap **Admin Panel** → tap **Login Account** → follow the steps.

Session is saved as `userbot_session.session` — you only need to login once.

---

## Usage

Send any `@username` directly to the bot. No commands needed.

```
@dope        → full profile breakdown
@summonmrx   → full profile breakdown
```

---

## Tech Stack

- [Telethon](https://github.com/LonamiWebs/Telethon) — MTProto userbot for API calls
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — bot interface
- [CryptoCompare API](https://min-api.cryptocompare.com) — historical TON price data
- [CoinGecko API](https://coingecko.com) — live TON/USD price

---

## Project Structure

```
tg-profile-valuator/
├── bot.py              # main bot logic
├── .env                # credentials (never commit this)
├── requirements.txt    # dependencies
└── userbot_session.session  # auto-generated after login
```

---

## Notes

- Using a userbot technically violates Telegram's ToS. For low-volume personal use the risk is minimal, but be aware.
- Never share or commit your `.env` file or `.session` file.
- Historical gift value data requires `GetUniqueStarGiftValueInfoRequest` which is a Telegram internal API method — may change without notice.

