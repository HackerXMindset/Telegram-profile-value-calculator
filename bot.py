import logging
import os
import re
import calendar
from html import escape as he
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes,
)
from telethon import TelegramClient, functions
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.functions.fragment import GetCollectibleInfoRequest
from telethon.tl.types import InputCollectibleUsername, InputCollectiblePhone
import httpx

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID    = int(os.getenv("API_ID"))
API_HASH  = os.getenv("API_HASH")
ADMIN_ID  = int(os.getenv("ADMIN_ID"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PHONE, OTP, PASSWORD = range(3)

client = TelegramClient("userbot_session", API_ID, API_HASH)

# ── Price helpers ─────────────────────────────────────────────────────────────

async def get_ton_price_now() -> float:
    try:
        async with httpx.AsyncClient() as h:
            r = await h.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "the-open-network", "vs_currencies": "usd"},
                timeout=10,
            )
            return r.json()["the-open-network"]["usd"]
    except Exception:
        return 3.5

async def get_ton_price_on_date(date: datetime) -> float | None:
    """Fetch historical TON/USD daily close price from CryptoCompare (free, no key needed)."""
    try:
        # Convert date to Unix timestamp (end of that day)
        ts = int(calendar.timegm(date.timetuple()))
        async with httpx.AsyncClient() as h:
            r = await h.get(
                "https://min-api.cryptocompare.com/data/v2/histoday",
                params={
                    "fsym": "TON",
                    "tsym": "USD",
                    "limit": 1,
                    "toTs": ts,
                },
                timeout=10,
            )
            data = r.json()
            if data.get("Response") == "Success":
                return data["Data"]["Data"][-1]["close"]
    except Exception as e:
        logger.debug(f"Historical price error: {e}")
    return None

# ── Misc helpers ──────────────────────────────────────────────────────────────

def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

def extract_usernames(bio: str) -> list:
    return re.findall(r'@([a-zA-Z0-9_]{4,})', bio or "")

def split_message(text: str, limit: int = 4000) -> list:
    """Split at newline boundaries, but never inside a <blockquote> block."""
    chunks, current = [], ""
    in_blockquote = False

    for line in text.split("\n"):
        addition = line + "\n"

        # Track blockquote boundaries
        if "<blockquote" in line:
            in_blockquote = True
        if "</blockquote>" in line:
            in_blockquote = False
            # After closing tag, allow a split on next iteration
            current += addition
            continue

        if not in_blockquote and len(current) + len(addition) > limit:
            if current:
                chunks.append(current.strip())
            current = addition
        else:
            current += addition

    if current.strip():
        chunks.append(current.strip())
    return chunks or [""]

# ── Keyboards ─────────────────────────────────────────────────────────────────

def main_menu_kb(adm: bool = False):
    btns = []
    if adm:
        btns.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(btns) if btns else None

def admin_kb(logged_in: bool):
    btns = []
    if logged_in:
        btns.append([InlineKeyboardButton("👤 Session Info", callback_data="admin_session")])
        btns.append([InlineKeyboardButton("🔴 Logout",       callback_data="admin_logout")])
    else:
        btns.append([InlineKeyboardButton("🔑 Login Account", callback_data="admin_login")])
    btns.append([InlineKeyboardButton("◀️ Back", callback_data="back_home")])
    return InlineKeyboardMarkup(btns)

def back_kb(cb: str = "back_home"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data=cb)]])

def result_kb(username: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh",  callback_data=f"refresh_{username}"),
            InlineKeyboardButton("🔗 Fragment", url=f"https://fragment.com/@{username}"),
        ],
        [InlineKeyboardButton("◀️ Back", callback_data="back_home")],
    ])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_login")]])

# ── Data fetching ─────────────────────────────────────────────────────────────

async def fetch_username_price(username: str) -> dict | None:
    try:
        res = await client(GetCollectibleInfoRequest(
            collectible=InputCollectibleUsername(username=username)
        ))
        ton           = res.crypto_amount / 1e9
        purchase_date = res.purchase_date
        return {
            "username":      username,
            "ton":           ton,
            "usd_at_sale":   res.amount / 100,
            "purchase_date": purchase_date,
            "date_str":      purchase_date.strftime("%b %d, %Y") if purchase_date else "Unknown",
        }
    except Exception:
        return None

async def fetch_phone_price(phone: str) -> dict | None:
    try:
        res = await client(GetCollectibleInfoRequest(
            collectible=InputCollectiblePhone(phone=phone)
        ))
        ton           = res.crypto_amount / 1e9
        purchase_date = res.purchase_date
        return {
            "phone":         phone,
            "ton":           ton,
            "usd_at_sale":   res.amount / 100,
            "purchase_date": purchase_date,
            "date_str":      purchase_date.strftime("%b %d, %Y") if purchase_date else "Unknown",
        }
    except Exception:
        return None


    gifts, offset = [], ""
    try:
        while True:
            res = await client(functions.payments.GetSavedStarGiftsRequest(
                peer=peer, offset=offset, limit=100
            ))
            gifts.extend(res.gifts)
            if not res.next_offset:
                break
            offset = res.next_offset
    except Exception as e:
        logger.error(f"fetch_all_gifts: {e}")
    return gifts

async def fetch_all_gifts(peer) -> list:
    gifts, offset = [], ""
    try:
        while True:
            res = await client(functions.payments.GetSavedStarGiftsRequest(
                peer=peer, offset=offset, limit=100
            ))
            gifts.extend(res.gifts)
            if not res.next_offset:
                break
            offset = res.next_offset
    except Exception as e:
        logger.error(f"fetch_all_gifts: {e}")
    return gifts

async def fetch_gift_value(slug: str) -> dict | None:
    try:
        res = await client(functions.payments.GetUniqueStarGiftValueInfoRequest(slug=slug))
        return {
            "currency":        getattr(res, "currency", "USD"),
            "value":           getattr(res, "value", 0) or 0,
            "floor_price":     getattr(res, "floor_price", 0) or 0,
            "last_sale_price": getattr(res, "last_sale_price", 0) or 0,
            "last_sale_date":  getattr(res, "last_sale_date", None),
        }
    except Exception as e:
        logger.debug(f"fetch_gift_value({slug}): {e}")
        return None

# ── Report builder ────────────────────────────────────────────────────────────

async def build_report(username: str):
    username = username.lstrip("@")

    if not await client.is_user_authorized():
        return "❌ Userbot not logged in. Ask admin to login first.", None, None, None, back_kb()

    ton_now = await get_ton_price_now()

    try:
        entity = await client.get_entity(username)
    except Exception:
        return f"❌ @{username} not found or private.", None, None, None, back_kb()

    # ── Usernames ─────────────────────────────────────────────────────────────
    unames = [username]
    if hasattr(entity, "usernames") and entity.usernames:
        for u in entity.usernames:
            if u.username.lower() != username.lower():
                unames.append(u.username)
    if hasattr(entity, "about") and entity.about:
        for bn in extract_usernames(entity.about):
            if bn.lower() not in [u.lower() for u in unames]:
                unames.append(bn)

    u_results = []
    for uname in unames:
        d = await fetch_username_price(uname)
        if d:
            hist = await get_ton_price_on_date(d["purchase_date"]) if d["purchase_date"] else None
            d["usd_hist"] = d["ton"] * hist if hist else d["usd_at_sale"]
            d["usd_now"]  = d["ton"] * ton_now
            u_results.append(d)

    total_u_ton      = sum(r["ton"]      for r in u_results)
    total_u_usd_hist = sum(r["usd_hist"] for r in u_results)
    total_u_usd_now  = sum(r["usd_now"]  for r in u_results)

    # ── Anonymous phone number ────────────────────────────────────────────────
    phone_result = None
    phone_str = getattr(entity, "phone", None)
    if phone_str and phone_str.startswith("888"):
        p = await fetch_phone_price(phone_str)
        if p:
            hist = await get_ton_price_on_date(p["purchase_date"]) if p["purchase_date"] else None
            p["usd_hist"] = p["ton"] * hist if hist else p["usd_at_sale"]
            p["usd_now"]  = p["ton"] * ton_now
            phone_result  = p
            total_u_ton      += p["ton"]
            total_u_usd_hist += p["usd_hist"]
            total_u_usd_now  += p["usd_now"]

    # ── Gifts ─────────────────────────────────────────────────────────────────
    peer  = await client.get_input_entity(username)
    gifts = await fetch_all_gifts(peer)

    collectibles, regulars = [], []
    for g in gifts:
        if hasattr(g, "gift") and hasattr(g.gift, "num") and g.gift.num:
            collectibles.append(g)
        else:
            regulars.append(g)

    slug_cache = {}
    for g in collectibles[:25]:
        slug = getattr(g.gift, "slug", None)
        if slug and slug not in slug_cache:
            slug_cache[slug] = await fetch_gift_value(slug)

    total_g_value_usd = 0.0
    total_g_floor_usd = 0.0
    total_g_floor_ton = 0.0

    coll_data = []
    for g in collectibles[:25]:
        obj    = g.gift
        name   = getattr(obj, "title",  "Unknown")
        num    = getattr(obj, "num",    "?")
        slug   = getattr(obj, "slug",   None)
        vi     = slug_cache.get(slug) if slug else None
        resell = getattr(g, "resell_amount", None)

        val_usd = floor_usd = floor_ton = 0.0
        floor_st = last_st = 0
        last_date = None

        if vi:
            fiat     = float(vi["value"] or 0)
            floor_st = vi["floor_price"] or 0
            last_st  = vi["last_sale_price"] or 0
            last_date = vi["last_sale_date"]

            if fiat:
                val_usd = fiat
                total_g_value_usd += val_usd

            if floor_st:
                floor_ton = floor_st / 227
                floor_usd = floor_ton * ton_now
                total_g_floor_usd += floor_usd
                total_g_floor_ton += floor_ton

        coll_data.append({
            "name": name, "num": num,
            "val_usd": val_usd,
            "floor_st": floor_st, "floor_ton": floor_ton, "floor_usd": floor_usd,
            "last_st": last_st, "last_date": last_date,
            "resell": resell,
        })

    reg_grouped     = {}
    reg_stars_total = 0
    for g in regulars:
        emoji = "🎁"
        stars = 0
        if hasattr(g, "gift"):
            if hasattr(g.gift, "sticker") and hasattr(g.gift.sticker, "alt"):
                emoji = g.gift.sticker.alt
            stars = getattr(g.gift, "stars", 0) or 0
        reg_stars_total += stars
        key = f"{emoji} {stars}⭐"
        reg_grouped[key] = reg_grouped.get(key, 0) + 1

    reg_ton = reg_stars_total / 227
    reg_usd = reg_ton * ton_now
    total_g_floor_usd += reg_usd
    total_g_floor_ton += reg_ton

    # ── Build messages (HTML) ─────────────────────────────────────────────────

    # Message 1 — Usernames + phone
    u_lines = []
    u_lines.append(f"<b>👤 @{he(username)}</b>")
    u_lines.append("")
    u_lines.append("<b>🔤 USERNAMES &amp; NUMBERS</b>")
    if u_results or phone_result:
        bq = []
        for r in u_results:
            bq.append(f"@{he(r['username'])}  ·  {r['ton']:.0f} TON")
            bq.append(f"  Bought for    ${r['usd_hist']:,.0f}  on {he(r['date_str'])}")
            bq.append(f"  Current value ${r['usd_now']:,.0f}")
            bq.append("")
        if phone_result:
            bq.append(f"+{he(phone_result['phone'])}  ·  {phone_result['ton']:.0f} TON")
            bq.append(f"  Bought for    ${phone_result['usd_hist']:,.0f}  on {he(phone_result['date_str'])}")
            bq.append(f"  Current value ${phone_result['usd_now']:,.0f}")
            bq.append("")
        bq.append(f"Total  {total_u_ton:.0f} TON")
        bq.append(f"Bought for    ${total_u_usd_hist:,.0f}")
        bq.append(f"Current value ${total_u_usd_now:,.0f}")
        u_lines.append(f"<blockquote expandable>{chr(10).join(bq)}</blockquote>")
    else:
        u_lines.append("  No collectible usernames or numbers")
    msg_usernames = "\n".join(u_lines)

    # Message 2 — Collectible gifts
    msg_collectibles = None
    if collectibles:
        c_lines = []
        label = f"  —  {len(collectibles)} total" + (", top 25 shown" if len(collectibles) > 25 else "")
        c_lines.append(f"<b>💎 COLLECTIBLE GIFTS{label}</b>")
        bq = []
        for c in coll_data:
            bq.append(f"{he(c['name'])} #{c['num']}")
            if c["floor_st"]:
                bq.append(f"  Floor price  {c['floor_st']:,} ⭐  →  {c['floor_ton']:.2f} TON  ·  ${c['floor_usd']:,.0f}")
            if c["last_st"]:
                last_usd = (c["last_st"] / 227) * ton_now
                ds = f"  ({c['last_date'].strftime('%b %d, %Y')})" if c["last_date"] else ""
                bq.append(f"  Last sale    ${last_usd:,.0f}{ds}")
            if c["resell"]:
                r_usd = (c["resell"] / 227) * ton_now
                bq.append(f"  🟢 Listed    {c['resell']:,} ⭐  ·  ${r_usd:,.0f}")
            bq.append("")
        if len(collectibles) > 25:
            bq.append(f"+ {len(collectibles) - 25} more not shown")
        c_lines.append(f"<blockquote expandable>{chr(10).join(bq)}</blockquote>")
        msg_collectibles = "\n".join(c_lines)

    # Message 3 — Regular gifts
    msg_regulars = None
    if regulars:
        r_lines = []
        r_lines.append(f"<b>⭐ REGULAR GIFTS  —  {len(regulars)} total</b>")
        bq = []
        for name, count in list(reg_grouped.items())[:20]:
            bq.append(f"  {he(name)}  ×{count}")
        if len(reg_grouped) > 20:
            bq.append(f"  + {len(reg_grouped) - 20} more types")
        bq.append("")
        bq.append(f"Total  {reg_ton:.1f} TON  ·  ${reg_usd:,.0f}")
        r_lines.append(f"<blockquote expandable>{chr(10).join(bq)}</blockquote>")
        msg_regulars = "\n".join(r_lines)

    # Message 4 — Summary
    total_by_floor = total_u_usd_now + total_g_floor_usd
    total_ton_all  = total_u_ton     + total_g_floor_ton

    # Separate username totals from phone totals for summary
    u_only_ton      = sum(r["ton"]      for r in u_results)
    u_only_usd_hist = sum(r["usd_hist"] for r in u_results)
    u_only_usd_now  = sum(r["usd_now"]  for r in u_results)

    summary_parts = [f"<b>📊 @{he(username)}  —  Value Summary</b>\n"]

    if u_results:
        summary_parts.append(f"<b>🔤 Usernames</b>")
        summary_parts.append(f"  Bought for    <b>${u_only_usd_hist:,.0f}</b>  ({u_only_ton:.0f} TON)")
        summary_parts.append(f"  Current value <b>${u_only_usd_now:,.0f}</b>\n")

    if phone_result:
        summary_parts.append(f"<b>📱 Anonymous Number</b>")
        summary_parts.append(f"  +{he(phone_result['phone'])}")
        summary_parts.append(f"  Bought for    <b>${phone_result['usd_hist']:,.0f}</b>  ({phone_result['ton']:.0f} TON)")
        summary_parts.append(f"  Current value <b>${phone_result['usd_now']:,.0f}</b>\n")

    if not u_results and not phone_result:
        summary_parts.append(f"<b>🔤 Usernames &amp; Numbers</b>")
        summary_parts.append(f"  None\n")

    summary_parts.append(f"<b>🎁 Gifts  (floor price)</b>")
    summary_parts.append(f"  <b>{total_g_floor_ton:.1f} TON  ·  ${total_g_floor_usd:,.0f}</b>\n")
    summary_parts.append(f"━━━━━━━━━━━━━━━━")
    summary_parts.append(f"💰 <b>Total  {total_ton_all:.1f} TON  ·  ${total_by_floor:,.0f}</b>\n")
    summary_parts.append(f"<i>1 TON = ${ton_now:.2f}</i>")

    summary = "\n".join(summary_parts)

    return msg_usernames, msg_collectibles, msg_regulars, summary, result_kb(username)

# ── Bot handlers ──────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Telegram Account Valuator</b>\n\n"
        "Send any @username to check:\n"
        "• Collectible username prices\n"
        "• All gifts + floor prices\n"
        "• Total value in TON / USD",
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin(update.effective_user.id)),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    data = query.data

    if data == "back_home":
        await query.edit_message_text(
            "👋 <b>Telegram Account Valuator</b>\n\nSend any @username to check its value.",
            parse_mode="HTML", reply_markup=main_menu_kb(is_admin(uid)),
        )

    elif data == "admin_panel":
        if not is_admin(uid):
            await query.answer("⛔ Not authorized.", show_alert=True); return
        logged_in = await client.is_user_authorized()
        status    = "🟢 Logged in" if logged_in else "🔴 Not logged in"
        if logged_in:
            me = await client.get_me()
            status += f" as @{me.username or me.first_name}"
        await query.edit_message_text(
            f"⚙️ <b>Admin Panel</b>\n\nUserbot: {status}",
            parse_mode="HTML", reply_markup=admin_kb(logged_in),
        )

    elif data == "admin_session":
        if not is_admin(uid):
            await query.answer("⛔ Not authorized.", show_alert=True); return
        me = await client.get_me()
        await query.edit_message_text(
            f"👤 <b>Session</b>\n\nName: {me.first_name} {me.last_name or ''}\n"
            f"Username: @{me.username or 'none'}\nID: <code>{me.id}</code>",
            parse_mode="HTML", reply_markup=admin_kb(True),
        )

    elif data == "admin_logout":
        if not is_admin(uid):
            await query.answer("⛔ Not authorized.", show_alert=True); return
        await client.log_out()
        await query.edit_message_text("✅ Logged out.", reply_markup=admin_kb(False))

    elif data == "admin_login":
        if not is_admin(uid):
            await query.answer("⛔ Not authorized.", show_alert=True); return
        await query.edit_message_text(
            "📱 <b>Login  —  Step 1 / 3</b>\n\nSend your phone number:\n<code>+919876543210</code>",
            parse_mode="HTML", reply_markup=cancel_kb(),
        )
        context.user_data["login_state"] = PHONE

    elif data == "cancel_login":
        context.user_data.pop("login_state", None)
        logged_in = await client.is_user_authorized()
        await query.edit_message_text("❌ Cancelled.", reply_markup=admin_kb(logged_in))

    elif data.startswith("refresh_"):
        uname = data.replace("refresh_", "")
        await query.edit_message_text("⏳ Refreshing...")
        msg_u, msg_c, msg_r, summary, kb = await build_report(uname)
        await query.edit_message_text(msg_u, parse_mode="HTML")
        if msg_c:
            await query.message.reply_text(msg_c, parse_mode="HTML")
        if msg_r:
            await query.message.reply_text(msg_r, parse_mode="HTML")
        if summary:
            await query.message.reply_text(summary, parse_mode="HTML", reply_markup=kb)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()

    # Admin login flow
    if is_admin(uid) and "login_state" in context.user_data:
        state = context.user_data["login_state"]

        if state == PHONE:
            context.user_data["phone"] = text
            try:
                await client.connect()
                res = await client.send_code_request(text)
                context.user_data["phone_code_hash"] = res.phone_code_hash
                context.user_data["login_state"]     = OTP
                await update.message.reply_text(
                    "✉️ <b>Login  —  Step 2 / 3</b>\n\nEnter the OTP sent to your phone:",
                    parse_mode="HTML", reply_markup=cancel_kb(),
                )
            except Exception as e:
                context.user_data.pop("login_state", None)
                await update.message.reply_text(f"❌ {e}")
            return

        elif state == OTP:
            otp   = text.replace(" ", "")
            phone = context.user_data["phone"]
            pch   = context.user_data["phone_code_hash"]
            try:
                await client.sign_in(phone, otp, phone_code_hash=pch)
                me = await client.get_me()
                context.user_data.pop("login_state", None)
                await update.message.reply_text(
                    f"✅ <b>Logged in as @{me.username or me.first_name}</b>\n\nBot is ready.",
                    parse_mode="HTML", reply_markup=admin_kb(True),
                )
            except SessionPasswordNeededError:
                context.user_data["login_state"] = PASSWORD
                await update.message.reply_text(
                    "🔐 <b>Login  —  Step 3 / 3</b>\n\nEnter your 2FA password:",
                    parse_mode="HTML", reply_markup=cancel_kb(),
                )
            except PhoneCodeInvalidError:
                await update.message.reply_text("❌ Wrong OTP. Try again:")
            except Exception as e:
                context.user_data.pop("login_state", None)
                await update.message.reply_text(f"❌ {e}")
            return

        elif state == PASSWORD:
            await update.message.delete()
            try:
                await client.sign_in(password=text)
                me = await client.get_me()
                context.user_data.pop("login_state", None)
                await update.message.reply_text(
                    f"✅ <b>Logged in as @{me.username or me.first_name}</b>",
                    parse_mode="HTML", reply_markup=admin_kb(True),
                )
            except Exception as e:
                await update.message.reply_text(f"❌ Wrong password: {e}")
            return

    # Username check
    if text.startswith("@") or re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,}$', text):
        uname = text.lstrip("@")
        msg   = await update.message.reply_text(f"⏳ Checking @{uname}...")
        try:
            msg_u, msg_c, msg_r, summary, kb = await build_report(uname)
            await msg.edit_text(msg_u, parse_mode="HTML")
            if msg_c:
                await update.message.reply_text(msg_c, parse_mode="HTML")
            if msg_r:
                await update.message.reply_text(msg_r, parse_mode="HTML")
            if summary:
                await update.message.reply_text(summary, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}", reply_markup=back_kb())
        return

    await update.message.reply_text(
        "Send a @username to check its value.",
        reply_markup=main_menu_kb(is_admin(uid)),
    )

# ── Main ──────────────────────────────────────────────────────────────────────

async def post_init(app):
    await client.connect()
    print("✅ Telethon connected")

async def post_shutdown(app):
    await client.disconnect()

if __name__ == "__main__":
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 Bot running...")
    app.run_polling()
