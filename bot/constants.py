from datetime import date, timedelta

LOCATIONS = ["BBQ Plaza", "BBQ Middle", "BBQ Bakema", "Common Room"]

# conversation states
(
    STATE_LOCATION,
    STATE_DATE,
    STATE_START,
    STATE_END,
    STATE_CONFIRM,
) = range(5)


def next_14_days() -> list[date]:
    today = date.today()
    return [today + timedelta(days=i) for i in range(14)]


def fmt_date(d: date) -> str:
    return d.strftime("%A, %B %-d")


def available_start_hours(booked: list[tuple[int, int]]) -> list[int]:
    """Hours 9–23 not fully blocked."""
    result = []
    for h in range(9, 24):
        # a start hour is available if at least one complete booking (h, h+1) fits
        if not any(s <= h < e for s, e in booked):
            result.append(h)
    return result


def available_end_hours(start_h: int, booked: list[tuple[int, int]]) -> list[int]:
    """End hours start_h+1 through 24 that don't overlap existing bookings."""
    result = []
    for end in range(start_h + 1, 25):
        if not any(start_h < e and end > s for s, e in booked):
            result.append(end)
    return result


def fmt_hour(h: int) -> str:
    return "00:00" if h == 24 else f"{h:02d}:00"


def main_menu_button():
    from telegram import InlineKeyboardButton
    return InlineKeyboardButton("🏠 Main Menu", callback_data="menu:back")
