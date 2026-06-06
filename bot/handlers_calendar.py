"""View Calendar — private chat button + /calendar group command."""
from datetime import date
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

from .constants import fmt_date, fmt_hour, main_menu_button
from .db import get_all_upcoming


def _build_calendar_text() -> str:
    rows = get_all_upcoming()
    if not rows:
        return "No upcoming reservations."

    lines = ["<b>Upcoming Reservations</b>\n"]
    current_date = None
    for r in rows:
        d = date.fromisoformat(r["date"])
        if d != current_date:
            current_date = d
            lines.append(f"\n📅 <b>{fmt_date(d)}</b>")
        lines.append(
            f"  📍 {r['location']}  {fmt_hour(r['start_h'])}–{fmt_hour(r['end_h'])}  👤 {r['username']}"
        )
    return "\n".join(lines)


async def view_calendar_private(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        _build_calendar_text(),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
    )


async def calendar_command_group(update: Update, ctx: ContextTypes):
    await update.message.reply_text(_build_calendar_text(), parse_mode="HTML")


async def group_calendar_button(update: Update, ctx: ContextTypes):
    """Inline button pressed on a group announcement — reply with the calendar."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(_build_calendar_text(), parse_mode="HTML")


def get_calendar_handlers():
    return [
        CallbackQueryHandler(view_calendar_private, pattern="^menu:calendar$"),
        CallbackQueryHandler(group_calendar_button, pattern="^group:calendar$"),
        CommandHandler("calendar", calendar_command_group),
    ]
