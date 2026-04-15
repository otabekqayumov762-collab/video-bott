from aiogram.fsm.state import StatesGroup, State


class AdminStates(StatesGroup):
    broadcast = State()
    add_channel = State()
    set_card = State()
    set_price = State()
    set_start_text = State()
    set_help_text = State()
    upload_cookies = State()
