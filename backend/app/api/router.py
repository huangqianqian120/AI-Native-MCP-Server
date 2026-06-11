from fastapi import APIRouter

from app.api.routes import schema, generation, chat, upload

api_router = APIRouter()
api_router.include_router(schema.router, prefix="/schema", tags=["schema"])
api_router.include_router(generation.router, prefix="/generate", tags=["generation"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
