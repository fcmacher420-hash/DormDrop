import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.routers.auth import router as auth_router
from app.routers.listings import router as listings_router
from app.routers.marketplace import router as marketplace_router

logger = logging.getLogger("dormdrop")

app = FastAPI(title=settings.app_name, version="0.1.0", description="Campus-only student marketplace prototype")
# Authentication uses a bearer header, not cookies, so credentialed CORS is not needed.
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(listings_router)
app.include_router(marketplace_router)

@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

frontend = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend), name="static")

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(frontend / "index.html")
