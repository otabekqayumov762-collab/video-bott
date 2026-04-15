from aiogram import Router
from . import start, download, help


def setup_user_routers() -> Router:
    router = Router()
    router.include_routers(
        start.router,
        help.router,
        download.router,
    )
    return router
