"""Group restriction filter.

Blocks any update coming from a group/supergroup that is NOT the allowed building group.
The bot silently ignores such messages — it does not reply, does not leave.
"""
from telegram import Update
from telegram.ext import BaseHandler, ContextTypes


class GroupRestrictionMiddleware:
    """
    Call `filter(update)` before dispatching.
    Returns True  → update is allowed through
    Returns False → update must be dropped
    """

    def __init__(self, allowed_group_id: int):
        self.allowed_group_id = allowed_group_id

    def allows(self, update: Update) -> bool:
        chat = update.effective_chat
        if chat is None:
            return False
        if chat.type == "private":
            return True
        if chat.type in ("group", "supergroup"):
            return chat.id == self.allowed_group_id
        # channels etc. — ignore
        return False
