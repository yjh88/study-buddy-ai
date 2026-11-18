"""대화 기록 API.

- GET /api/conversations       : 목록 (messages 미포함, message_count/preview 만)
- GET /api/conversations/{id}  : 특정 대화의 전체 messages (대화 불러오기)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..repositories import get_conversation_repo
from ..repositories.base import Repository
from ..schemas import Conversation, ConversationCreate, ConversationSummaryItem
from ..services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=Conversation, status_code=status.HTTP_201_CREATED, summary="대화 저장")
def create_conversation(body: ConversationCreate, repo: Repository = Depends(get_conversation_repo)):
    return conversation_service.create_conversation(repo, body)


@router.get("", response_model=list[ConversationSummaryItem], summary="대화 목록 조회 (messages 미포함)")
def list_conversations(limit: Optional[int] = Query(50, ge=1, le=200),
                       repo: Repository = Depends(get_conversation_repo)):
    return conversation_service.list_conversations(repo, limit=limit)


@router.get("/{conv_id}", response_model=Conversation, summary="특정 대화 불러오기 (전체 messages)")
def get_conversation(conv_id: str, repo: Repository = Depends(get_conversation_repo)):
    conv = conversation_service.get_conversation(repo, conv_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"대화를 찾을 수 없습니다: {conv_id}")
    return conv


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT, summary="대화 삭제")
def delete_conversation(conv_id: str, repo: Repository = Depends(get_conversation_repo)):
    if not conversation_service.delete_conversation(repo, conv_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"대화를 찾을 수 없습니다: {conv_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
