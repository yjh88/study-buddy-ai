"""FastAPI 앱 진입점.

로컬 실행: uvicorn main:app --reload
Swagger UI: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.repositories import init_store, store
from app.routers import chat, conversations, data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_store()
    logger.info("CORS 허용 도메인: %s", settings.ALLOWED_ORIGINS)
    yield


app = FastAPI(
    title="My Study AI Assistant API",
    description="내 학습 시간 데이터를 이해하고 답해 주는 AI 비서 API. "
                "데이터 요약을 시스템 프롬프트에 주입(컨텍스트 주입)하고, 필요 시 Function Calling으로 세부 데이터를 조회합니다.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled_exception(_: Request, exc: Exception):
    # 내부 오류 상세(스택, 키 등)는 응답에 노출하지 않고 로그로만 남긴다.
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "서버 내부 오류가 발생했습니다."})


@app.get("/", tags=["health"], summary="서비스 안내")
def root():
    return {"service": "My Study AI Assistant API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["health"], summary="헬스 체크 (콜드스타트 깨우기 용도)")
def health():
    return {"status": "ok", "db": store.backend, "ai_ready": bool(settings.OPENAI_API_KEY)}
