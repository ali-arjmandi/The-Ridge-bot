import os
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)

from .db import init_db, get_config
from .handlers_reserve import build_reservation_conv
from .handlers_my_reservations import get_my_reservations_handlers
from .handlers_calendar import get_calendar_handlers
from .handlers_admin import admin_menu, build_admin_conv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ── main menu ─────────────────────────────────────────────────────────────────

def _main_menu_markup(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📅 New Reservation", callback_data="menu:new")],
        [InlineKeyboardButton("📋 My Reservations", callback_data="menu:my")],
        [InlineKeyboardButton("🗓 View Calendar",    callback_data="menu:calendar")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⚙️ Admin Settings", callback_data="menu:admin")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, ctx: ContextTypes):
    if update.effective_chat.type != "private":
        return
    admin_id = ctx.bot_data.get("admin_id")
    is_admin = update.effective_user.id == admin_id
    markup = _main_menu_markup(is_admin)
    text = "Welcome to *The Ridge* Amenity Reservation Bot!\nWhat would you like to do?"
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


# ── bootstrap ─────────────────────────────────────────────────────────────────

def main():
    token = os.environ["BOT_TOKEN"]
    raw_admin_id = os.environ.get("ADMIN_ID", "")
    if not raw_admin_id:
        raise RuntimeError("ADMIN_ID must be set in .env")
    admin_id = int(raw_admin_id)

    init_db()

    # Load persisted group ID (set by admin via bot, stored in DB)
    raw_group_id = get_config("allowed_group_id")
    allowed_group_id = int(raw_group_id) if raw_group_id else None

    app = Application.builder().token(token).build()
    app.bot_data["admin_id"] = admin_id
    app.bot_data["allowed_group_id"] = allowed_group_id

    if allowed_group_id:
        log.info("Bot starting. Allowed group: %s", allowed_group_id)
    else:
        log.info("Bot starting. No group configured yet — admin must set it via the bot.")

    # Guard: drop updates from any group that isn't the configured building group.
    # Reads bot_data dynamically so it takes effect immediately after admin saves a new ID.
    async def _guard(update: Update, ctx: ContextTypes):
        chat = update.effective_chat
        if chat is None:
            raise ApplicationHandlerStop
        if chat.type == "private":
            return
        if chat.type in ("group", "supergroup"):
            allowed = ctx.bot_data.get("allowed_group_id")
            if allowed and chat.id == allowed:
                return
        raise ApplicationHandlerStop

    app.add_handler(TypeHandler(Update, _guard), group=-999)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^menu:back$"))

    # Admin
    app.add_handler(CallbackQueryHandler(admin_menu, pattern="^menu:admin$"))
    app.add_handler(build_admin_conv(admin_id))

    # Regular flows
    app.add_handler(build_reservation_conv())
    for h in get_my_reservations_handlers():
        app.add_handler(h)
    for h in get_calendar_handlers():
        app.add_handler(h)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
