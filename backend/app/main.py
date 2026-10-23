from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.actions import router as actions_router
from app.api.routes.agendas import router as agendas_router
from app.api.routes.auth import router as auth_router
from app.api.routes.meetings import router as meetings_router
from app.api.routes.memory import router as memory_router
from app.api.routes.minutes import router as minutes_router
from app.api.routes.rooms import router as rooms_router
from app.api.routes.schedule import router as schedule_router
from app.api.routes.traces import router as traces_router
from app.api.routes.users import router as users_router
from app.config import settings
from app.core.errors import AppError, app_exception_handler
from app.core.logging import setup_logging

logger = setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS middleware for frontend UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
app.add_exception_handler(AppError, app_exception_handler)

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(meetings_router, prefix=settings.API_V1_STR)
app.include_router(rooms_router, prefix=settings.API_V1_STR)
app.include_router(agendas_router, prefix=settings.API_V1_STR)
app.include_router(minutes_router, prefix=settings.API_V1_STR)
app.include_router(actions_router, prefix=settings.API_V1_STR)
app.include_router(memory_router, prefix=settings.API_V1_STR)
app.include_router(schedule_router, prefix=settings.API_V1_STR)
app.include_router(traces_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Meeting Organizer Agent API is running."}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": settings.VERSION}
