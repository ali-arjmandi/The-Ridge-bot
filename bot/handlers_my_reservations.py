"""My Reservations — list and cancel."""
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from .constants import fmt_date, fmt_hour, main_menu_button
from .db import get_user_reservations, get_reservation_by_id, delete_reservation


async def my_reservations(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    rows = get_user_reservations(update.effective_user.id)

    if not rows:
        await query.edit_message_text(
            "You have no upcoming reservations.",
            reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
        )
        return

    keyboard = []
    for r in rows:
        d = date.fromisoformat(r["date"])
        label = f"❌  {r['location']}  |  {d.strftime('%a %b %-d')}  |  {fmt_hour(r['start_h'])}–{fmt_hour(r['end_h'])}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"cancel:{r['id']}")])
    keyboard.append([main_menu_button()])

    await query.edit_message_text(
        "*Your upcoming reservations:*\nTap a booking to cancel it.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cancel_reservation(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    res_id = int(query.data.split(":", 1)[1])

    row = get_reservation_by_id(res_id)
    if row is None:
        await query.edit_message_text("Reservation not found.")
        return

    if row["user_id"] != update.effective_user.id:
        await query.answer("You can only cancel your own reservations.", show_alert=True)
        return

    d = date.fromisoformat(row["date"])
    username = row["username"]
    loc = row["location"]
    start_h = row["start_h"]
    end_h = row["end_h"]

    deleted = delete_reservation(res_id, update.effective_user.id)
    if not deleted:
        await query.edit_message_text(
            "Could not cancel — it may have already been removed.",
            reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
        )
        return

    await query.edit_message_text(
        f"✅ Reservation cancelled:\n\n📍 {loc}\n🗓 {fmt_date(d)}\n⏰ {fmt_hour(start_h)}–{fmt_hour(end_h)}",
        reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
    )

    # announce cancellation to group
    group_id = ctx.bot_data.get("allowed_group_id")
    if group_id:
        text = (
            f"❌ <b>Reservation Cancelled</b>\n"
            f"👤 {username}\n"
            f"📍 {loc}\n"
            f"🗓 {fmt_date(d)}\n"
            f"⏰ {fmt_hour(start_h)} – {fmt_hour(end_h)}"
        )
        url = f"https://t.me/{ctx.bot.username}?start=calendar"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📅 View Calendar", url=url)]])
        try:
            await ctx.bot.send_message(group_id, text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass


def get_my_reservations_handlers():
    return [
        CallbackQueryHandler(my_reservations,   pattern="^menu:my$"),
        CallbackQueryHandler(cancel_reservation, pattern="^cancel:"),
    ]
