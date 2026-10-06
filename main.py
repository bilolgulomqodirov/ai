import os
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from api.routes import router

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ma'lumotlar bazasini initsializatsiya qilish
    init_db()
    yield

app = FastAPI(
    title="Baraka Avto AI — Dealership CRM & ERP",
    description="Avtosalonlar va avtomobil ijarasi (arenda/nasiya) uchun AI Agent boshqaruvidagi CRM va ERP tizimi",
    version="2.0.0",
    lifespan=lifespan
)

# CORS sozlamalari (Ixtiyoriy frontend integratsiyasi uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routerini ulash
app.include_router(router)

# Statik fayllar (Dashboard)
static_dir = BASE_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", summary="ERP Asosiy Dashboard sahifasi")
def serve_dashboard():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Baraka Avto AI CRM & ERP API ishlamoqda. /docs orqali Swagger hujjatlarini ko'rishingiz mumkin."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
