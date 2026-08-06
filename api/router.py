"""Top-level API router composition."""

from fastapi import APIRouter

from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.conversations import router as conversations_router
from api.routes.database_connections import router as database_connections_router
from api.routes.files import router as files_router
from api.routes.health import router as health_router
from api.routes.knowledge_bases import router as knowledge_bases_router
from api.routes.permissions import router as permissions_router
from api.routes.roles import router as roles_router
from api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(database_connections_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(conversations_router)
api_router.include_router(chat_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(files_router)
