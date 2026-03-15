# tg-profile-valuator

A Telegram bot that calculates the total value of any Telegram account — collectible usernames, anonymous numbers, unique gifts, floor prices, and historical TON data.

---

## Features

- **Username Valuation** — fetches the purchase price of every collectible username on a profile
- **Anonymous Number Valuation** — detects and values +888 collectible phone numbers
- **Historical TON Price** — shows what each username/number was bought for at the actual purchase date, not today's price
- **Current Value** — also shows what those same assets are worth right now
- **Collectible Gift Prices** — for every unique gift (Plush Pepe, Snoop Dogg, Khabib etc.):
  - Floor price (cheapest listed on the market)
  - Last sale price and date
  - If that specific serial is currently listed for sale
- **Regular Gift Summary** — groups all non-collectible gifts by type with total star count
- **Full Profile Summary** — usernames, anonymous number, and gifts broken out separately with a clean total in TON and USD
- **Admin-only Login** — only the bot owner can connect a Telegram account via phone + OTP + 2FA password
- **Expandable Sections** — usernames, collectibles and regular gifts each collapsed in a blockquote, tap to expand
- **Anyone Can Check** — just send @username, no commands needed

---

## How It Works

The bot uses a Telethon userbot (your personal Telegram account) running alongside a regular bot token. The userbot makes MTProto API calls that a normal bot token cannot:

| Method | Purpose |
|---|---|
| `fragment.GetCollectibleInfo` | Username + anonymous number purchase price |
| `payments.GetSavedStarGifts` | All gifts on a profile |
| `payments.GetUniqueStarGiftValueInfo` | Floor price and last sale per gift |
| CryptoCompare API | Historical TON/USD price on purchase date |
| CoinGecko API | Live TON/USD price |

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
BOT_TOKEN=your_bot_token_from_botfather
API_ID=12345678
API_HASH=your_api_hash_from_my_telegram_org
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

Session is saved as `userbot_session.session` — you only login once.

---

## Usage

Send any `@username` directly to the bot. No commands needed.

The bot replies with 4 messages:

1. **Usernames & Numbers** — each username and anonymous number with bought price vs current value
2. **Collectible Gifts** — top 25 unique gifts with floor price, last sale, and listing status
3. **Regular Gifts** — all non-collectible gifts grouped by type
4. **Summary** — clean breakdown of total profile value in TON and USD

---

## Example Output

```
📊 @dope  —  Value Summary

🔤 Usernames
  Bought for    $38,521  (10050 TON)
  Current value $12,964

📱 Anonymous Number
  +88800000095
  Bought for    $6,452  (5000 TON)
  Current value $6,452

🎁 Gifts  (floor price)
  3578.5 TON  ·  $4,616

━━━━━━━━━━━━━━━━
💰 Total  13628.5 TON  ·  $17,581

1 TON = $1.29
```

---

## Project Structure

```
tg-profile-valuator/
├── bot.py                       # all bot logic
├── .env                         # credentials (never commit this)
├── requirements.txt             # dependencies
└── userbot_session.session      # auto-generated after first login
```

---

## Notes

- Using a userbot technically violates Telegram's ToS. For low-volume personal use the risk is minimal, but be aware.
- Never share or commit your `.env` or `.session` file.
- Anonymous number valuation only works if the number is visible on the profile (not hidden by privacy settings).
- Historical price data uses CryptoCompare's free tier — no API key required.
