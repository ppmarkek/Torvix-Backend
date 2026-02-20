from fastapi import FastAPI
from app.api.routes.auth import router as auth_router
from app.api.routes.food_database import router as food_database_router
from app.api.routes.health import router as health_router

app = FastAPI(title="Torvix Backend")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(food_database_router)
