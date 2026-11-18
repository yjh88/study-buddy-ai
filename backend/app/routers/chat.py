"""AI 채팅 API."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import settings
from ..repositories import get_conversation_repo, get_data_repo
from ..repositories.base import Repository
from ..schemas import ChatRequest, ChatResponse
from ..services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])

# 간단한 IP별 요청 제한 (OpenAI 과금 보호용, 단일 인스턴스 기준)
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    limit = settings.CHAT_RATE_LIMIT_PER_MIN
    if limit <= 0:
        return
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "요청이 너무 많습니다. 1분 후 다시 시도해 주세요.")
    q.append(now)


@router.post("/chat", response_model=ChatResponse, summary="AI 대화 (데이터 요약 컨텍스트 주입 + 자동 저장)",
             dependencies=[Depends(rate_limit)])
def chat(body: ChatRequest,
         data_repo: Repository = Depends(get_data_repo),
         conv_repo: Repository = Depends(get_conversation_repo)):
    try:
        return chat_service.chat(body.message, body.conversation_id, data_repo, conv_repo)
    except chat_service.ChatServiceError as e:
        raise HTTPException(e.status_code, str(e)) from e
