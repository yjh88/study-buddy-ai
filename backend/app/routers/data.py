"""데이터 API: CRUD 4개 + summary + statistics."""

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..repositories import get_data_repo
from ..repositories.base import Repository
from ..schemas import DataCreate, DataItem, DataStatistics, DataSummary, DataUpdate
from ..services import data_service

router = APIRouter(prefix="/api/data", tags=["data"])


# 고정 경로(/summary, /statistics)는 경로 변수(/{id}) 라우트보다 먼저 선언한다.
@router.get("/summary", response_model=DataSummary, summary="데이터 요약 (프롬프트 주입용)")
def get_summary(repo: Repository = Depends(get_data_repo)):
    return data_service.build_summary(repo)


@router.get("/statistics", response_model=DataStatistics, summary="추가 통계 (이동평균, 요일별 평균, 연속 기록)")
def get_statistics(repo: Repository = Depends(get_data_repo)):
    return data_service.build_statistics(repo)


@router.get("", response_model=list[DataItem], summary="데이터 목록 조회")
def list_data(
    start: Optional[date] = Query(None, description="시작일 (포함)"),
    end: Optional[date] = Query(None, description="종료일 (포함)"),
    order: Literal["asc", "desc"] = Query("desc", description="날짜 정렬 방향"),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    repo: Repository = Depends(get_data_repo),
):
    if start and end and start > end:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "start 는 end 보다 이후일 수 없습니다.")
    return data_service.list_data(repo, start=start, end=end, order=order, limit=limit)


@router.post("", response_model=DataItem, status_code=status.HTTP_201_CREATED, summary="새 데이터 추가")
def create_data(body: DataCreate, repo: Repository = Depends(get_data_repo)):
    return data_service.create_data(repo, body)


@router.put("/{doc_id}", response_model=DataItem, summary="데이터 수정")
def update_data(doc_id: str, body: DataUpdate, repo: Repository = Depends(get_data_repo)):
    updated = data_service.update_data(repo, doc_id, body)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"데이터를 찾을 수 없습니다: {doc_id}")
    return updated


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, summary="데이터 삭제")
def delete_data(doc_id: str, repo: Repository = Depends(get_data_repo)):
    if not data_service.delete_data(repo, doc_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"데이터를 찾을 수 없습니다: {doc_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
