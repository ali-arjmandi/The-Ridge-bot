"""New Reservation conversation flow."""
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from .constants import (
    LOCATIONS, STATE_LOCATION, STATE_DATE, STATE_START, STATE_END, STATE_CONFIRM,
    next_14_days, fmt_date, fmt_hour, available_start_hours, available_end_hours,
    main_menu_button,
)
from .db import get_booked_hours, create_reservation


def _cancel_button() -> InlineKeyboardButton:
    return InlineKeyboardButton("❌ Cancel", callback_data="reserve:cancel")


# ── entry ─────────────────────────────────────────────────────────────────────

async def new_reservation_start(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(loc, callback_data=f"loc:{loc}")] for loc in LOCATIONS]
    keyboard.append([_cancel_button()])
    await query.edit_message_text("Select a location:", reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_LOCATION


# ── step 1: location ──────────────────────────────────────────────────────────

async def select_location(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    loc = query.data.split(":", 1)[1]
    ctx.user_data["location"] = loc

    days = next_14_days()
    keyboard = []
    row = []
    for d in days:
        row.append(InlineKeyboardButton(fmt_date(d), callback_data=f"date:{d.isoformat()}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([_cancel_button()])

    await query.edit_message_text(
        f"Location: *{loc}*\nSelect a date:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return STATE_DATE


# ── step 2: date ──────────────────────────────────────────────────────────────

async def select_date(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    chosen_date = query.data.split(":", 1)[1]
    ctx.user_data["date"] = chosen_date

    loc = ctx.user_data["location"]
    booked = get_booked_hours(loc, chosen_date)
    hours = available_start_hours(booked)
    ctx.user_data["booked"] = booked

    if not hours:
        await query.edit_message_text(
            f"No available start times for *{loc}* on {chosen_date}. Please choose another date.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
        )
        return ConversationHandler.END

    keyboard = _hour_keyboard(hours, prefix="start")
    keyboard.append([_cancel_button()])
    d = date.fromisoformat(chosen_date)
    await query.edit_message_text(
        f"Location: *{loc}*\nDate: *{fmt_date(d)}*\nSelect start time:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return STATE_START


# ── step 3: start time ────────────────────────────────────────────────────────

async def select_start(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    start_h = int(query.data.split(":", 1)[1])
    ctx.user_data["start_h"] = start_h

    booked = ctx.user_data["booked"]
    ends = available_end_hours(start_h, booked)

    keyboard = _hour_keyboard(ends, prefix="end")
    keyboard.append([_cancel_button()])
    loc = ctx.user_data["location"]
    d = date.fromisoformat(ctx.user_data["date"])
    await query.edit_message_text(
        f"Location: *{loc}*\nDate: *{fmt_date(d)}*\nStart: *{fmt_hour(start_h)}*\nSelect end time:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return STATE_END


# ── step 4: end time → confirm ────────────────────────────────────────────────

async def select_end(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()
    end_h = int(query.data.split(":", 1)[1])
    ctx.user_data["end_h"] = end_h

    loc = ctx.user_data["location"]
    chosen_date = ctx.user_data["date"]
    start_h = ctx.user_data["start_h"]
    d = date.fromisoformat(chosen_date)

    text = (
        f"Please confirm your reservation:\n\n"
        f"📍 *{loc}*\n"
        f"🗓 {fmt_date(d)}\n"
        f"⏰ {fmt_hour(start_h)} – {fmt_hour(end_h)}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_CONFIRM


# ── step 5: confirm ───────────────────────────────────────────────────────────

async def confirm_reservation(update: Update, ctx: ContextTypes):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text(
            "Reservation cancelled.",
            reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
        )
        ctx.user_data.clear()
        return ConversationHandler.END

    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    loc = ctx.user_data["location"]
    chosen_date = ctx.user_data["date"]
    start_h = ctx.user_data["start_h"]
    end_h = ctx.user_data["end_h"]

    try:
        res_id = create_reservation(user.id, username, loc, chosen_date, start_h, end_h)
    except ValueError:
        await query.edit_message_text(
            "Sorry, that slot was just taken. Please try again.",
            reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
        )
        ctx.user_data.clear()
        return ConversationHandler.END

    d = date.fromisoformat(chosen_date)
    await query.edit_message_text(
        f"✅ *Reservation confirmed!*\n\n"
        f"📍 {loc}\n"
        f"🗓 {fmt_date(d)}\n"
        f"⏰ {fmt_hour(start_h)} – {fmt_hour(end_h)}\n\n"
        f"Booking ID: `{res_id}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
    )

    await _announce_new(ctx, username, loc, d, start_h, end_h)

    ctx.user_data.clear()
    return ConversationHandler.END


async def _announce_new(ctx: ContextTypes, username, loc, d, start_h, end_h):
    group_id = ctx.bot_data.get("allowed_group_id")
    if not group_id:
        return
    text = (
        f"📅 <b>New Reservation</b>\n"
        f"👤 {username}\n"
        f"📍 {loc}\n"
        f"🗓 {fmt_date(d)}\n"
        f"⏰ {fmt_hour(start_h)} – {fmt_hour(end_h)}"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📅 View Calendar", callback_data="group:calendar")]])
    try:
        await ctx.bot.send_message(group_id, text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass


# ── cancel mid-flow ───────────────────────────────────────────────────────────

async def cancel_flow(update: Update, ctx: ContextTypes):
    """Cancel button pressed at any step during the reservation flow."""
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    await query.edit_message_text(
        "Reservation cancelled.",
        reply_markup=InlineKeyboardMarkup([[main_menu_button()]]),
    )
    return ConversationHandler.END


async def cancel_conv(update: Update, ctx: ContextTypes):
    """/start typed mid-flow."""
    ctx.user_data.clear()
    if update.message:
        await update.message.reply_text(
            "Cancelled.", reply_markup=InlineKeyboardMarkup([[main_menu_button()]])
        )
    return ConversationHandler.END


# ── helpers ───────────────────────────────────────────────────────────────────

def _hour_keyboard(hours: list[int], prefix: str) -> list[list[InlineKeyboardButton]]:
    buttons = [InlineKeyboardButton(fmt_hour(h), callback_data=f"{prefix}:{h}") for h in hours]
    rows = []
    for i in range(0, len(buttons), 4):
        rows.append(buttons[i:i+4])
    return rows


# ── handler assembly ──────────────────────────────────────────────────────────

def build_reservation_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(new_reservation_start, pattern="^menu:new$")],
        states={
            STATE_LOCATION: [CallbackQueryHandler(select_location, pattern="^loc:")],
            STATE_DATE:     [CallbackQueryHandler(select_date,     pattern="^date:")],
            STATE_START:    [CallbackQueryHandler(select_start,    pattern="^start:")],
            STATE_END:      [CallbackQueryHandler(select_end,      pattern="^end:")],
            STATE_CONFIRM:  [CallbackQueryHandler(confirm_reservation, pattern="^confirm_")],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_flow, pattern="^reserve:cancel$"),
            CommandHandler("start", cancel_conv),
        ],
        per_message=False,
    )
