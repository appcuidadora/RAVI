from dotenv import load_dotenv
load_dotenv()

import os
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from database import client
from auth_routes import router as auth_router
from core_routes import router as core_router
from whatsapp_routes import router as whatsapp_router
from seed import create_indexes, seed_demo

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RAVI API")

app.include_router(auth_router)
app.include_router(core_router)
app.include_router(whatsapp_router)

frontend_url = os.environ.get("FRONTEND_URL", "")
origins = [frontend_url] if frontend_url else os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await create_indexes()
    await seed_demo()
    logger.info("RAVI API pronta")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
