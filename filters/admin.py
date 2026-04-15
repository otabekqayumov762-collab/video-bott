from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery


class IsBotAdminFilter(BaseFilter):
    def __init__(self, user_ids: list):
        self.user_ids = [int(i) for i in user_ids]

    async def __call__(self, event) -> bool:
        if isinstance(event, (Message, CallbackQuery)):
            return int(event.from_user.id) in self.user_ids
        return False
