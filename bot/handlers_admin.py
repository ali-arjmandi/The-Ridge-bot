"""Admin-only settings — visible only to the configured ADMIN_ID."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .db import get_config, set_config
from .constants import main_menu_button

STATE_WAITING_GROUP_ID = 10


async def admin_menu(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    current = get_config("allowed_group_id") or "Not set"
    keyboard = [
        [InlineKeyboardButton("✏️ Set Group ID", callback_data="admin:set_group")],
        [main_menu_button()],
    ]
    await query.edit_message_text(
        f"⚙️ *Admin Settings*\n\nGroup ID: `{current}`\n\n"
        "To find your group ID, forward any message from the group to @userinfobot.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ask_group_id(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Send me the group ID (a negative number, e.g. `-1001234567890`).\n\n"
        "You can get it from @userinfobot or by forwarding a group message to it.\n\n"
        "Send /start to cancel.",
    )
    return STATE_WAITING_GROUP_ID


async def receive_group_id(update: Update, ctx: ContextTypes):
    text = update.message.text.strip()
    try:
        group_id = int(text)
        if group_id >= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "That doesn't look right. Group IDs are negative numbers like `-1001234567890`. Try again or send /start to cancel."
        )
        return STATE_WAITING_GROUP_ID

    set_config("allowed_group_id", str(group_id))
    ctx.bot_data["allowed_group_id"] = group_id

    await update.message.reply_text(
        f"✅ Group ID saved: `{group_id}`\n\nThe bot now restricts group access to this chat.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
    )
    return ConversationHandler.END


async def cancel_admin(update: Update, ctx: ContextTypes):
    if update.message:
        await update.message.reply_text(
            "Cancelled.",
            reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
        )
    return ConversationHandler.END


def build_admin_conv(admin_id: int) -> ConversationHandler:
    admin_filter = filters.User(admin_id)
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_group_id, pattern="^admin:set_group$")],
        states={
            STATE_WAITING_GROUP_ID: [
                MessageHandler(filters.TEXT & admin_filter & ~filters.COMMAND, receive_group_id)
            ],
        },
        fallbacks=[CommandHandler("start", cancel_admin)],
        per_message=False,
    )
