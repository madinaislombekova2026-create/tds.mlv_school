from bot.handlers.registration import router as registration_router
from bot.handlers.profile import router as profile_router
from bot.handlers.menu import router as menu_router
from bot.handlers.broadcast import router as broadcast_router

__all__ = [
    "registration_router",
    "profile_router",
    "menu_router",
    "broadcast_router"
]
