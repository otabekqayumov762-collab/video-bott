from aiogram import Router
from aiogram.enums import ChatType
from filters import ChatTypeFilter


def setup_routers() -> Router:
    from handlers.users import setup_user_routers
    from handlers.admin import router as admin_router
    from handlers.errors.error_handler import router as error_router

    router = Router()
    router.message.filter(ChatTypeFilter(chat_types=[ChatType.PRIVATE]))

    router.include_routers(
        admin_router,
        setup_user_routers(),
        error_router,
    )
    return router
