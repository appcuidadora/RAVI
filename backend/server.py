from dotenv import load_dotenv
load_dotenv()

import os
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from database import client, db
from auth_routes import router as auth_router
from core_routes import router as core_router
from whatsapp_routes import router as whatsapp_router
from usage_routes import router as usage_router
from seed import create_indexes, seed_demo, seed_platform
from admin_routes import router as admin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RAVI API")

app.include_router(auth_router)
app.include_router(core_router)
app.include_router(whatsapp_router)
app.include_router(usage_router)
app.include_router(admin_router)

frontend_url = os.environ.get("FRONTEND_URL", "")
origins = [frontend_url] if frontend_url else os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    try:
        await db.command("ping")
        return {"status": "ok", "mongo": "ok"}
    except Exception:
        return {"status": "degraded", "mongo": "error"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Erro não tratado em %s %s: %s", request.method, request.url.path, exc)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Erro interno do servidor"}, status_code=500)


@app.on_event("startup")
async def startup():
    doc = await db.platform_settings.find_one({"id": "global"})
    for k, v in (((doc or {}).get("secrets")) or {}).items():
        if isinstance(v, str) and v and not os.environ.get(k):
            os.environ[k] = v
    await create_indexes()
    await seed_platform()
    await seed_demo()
    logger.info("RAVI API pronta")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
