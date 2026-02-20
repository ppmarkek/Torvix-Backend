from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.auth import router as auth_router
from app.api.routes.food_database import compat_router as food_database_compat_router
from app.api.routes.food_database import router as food_database_router
from app.api.routes.health import router as health_router

app = FastAPI(title="Torvix Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(food_database_router)
app.include_router(food_database_compat_router)
