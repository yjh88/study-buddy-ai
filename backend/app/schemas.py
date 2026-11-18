"""Pydantic 요청/응답 스키마.

요청 본문은 라우터에 도달하기 전에 여기서 검증된다.
잘못된 값(빈 문자열, 음수 시간, 미래 날짜 등)은 FastAPI가 자동으로 422 응답을 돌려준다.
"""

from datetime import date as Date
from datetime import timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_MINUTES_PER_DAY = 24 * 60


def _validate_date(v: Optional[Date]) -> Optional[Date]:
    if v is None:
        return v
    if v > Date.today() + timedelta(days=1):
        raise ValueError("미래 날짜는 기록할 수 없습니다.")
    if v.year < 2000:
        raise ValueError("2000년 이후 날짜만 허용됩니다.")
    return v


# ---------- 데이터 (data 컬렉션) ----------
class DataBase(BaseModel):
    date: Date = Field(..., description="기록 날짜 (YYYY-MM-DD)", examples=["2026-11-18"])
    value: float = Field(
        ..., ge=0, le=MAX_MINUTES_PER_DAY, description="학습 시간(분), 0~1440", examples=[120]
    )
    memo: str = Field("", max_length=200, description="메모 (최대 200자)", examples=["FastAPI 실습"])

    @field_validator("date")
    @classmethod
    def date_in_range(cls, v: Date) -> Date:
        return _validate_date(v)

    @field_validator("memo")
    @classmethod
    def strip_memo(cls, v: str) -> str:
        return v.strip()


class DataCreate(DataBase):
    pass


class DataUpdate(BaseModel):
    """부분 수정 허용. 최소 한 개 필드는 있어야 한다."""

    date: Optional[Date] = None
    value: Optional[float] = Field(None, ge=0, le=MAX_MINUTES_PER_DAY)
    memo: Optional[str] = Field(None, max_length=200)

    @field_validator("date")
    @classmethod
    def date_in_range(cls, v: Optional[Date]) -> Optional[Date]:
        return _validate_date(v)

    @field_validator("memo")
    @classmethod
    def strip_memo(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v is not None else v

    @model_validator(mode="after")
    def at_least_one(self):
        if self.date is None and self.value is None and self.memo is None:
            raise ValueError("수정할 필드(date, value, memo)를 하나 이상 보내야 합니다.")
        return self


class DataItem(BaseModel):
    id: str
    date: str
    value: float
    memo: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Metrics(BaseModel):
    total: float
    average: float
    max: float
    max_date: Optional[str] = None
    min: float
    min_date: Optional[str] = None
    std: float


class MonthlyStat(BaseModel):
    month: str
    days: int
    total: float
    average: float


class DataSummary(BaseModel):
    period: str
    count: int
    unit: str
    metrics: Metrics
    trend: str
    recent_7d_average: Optional[float] = None
    monthly: list[MonthlyStat] = []
    latest: Optional[DataItem] = None


class DataStatistics(BaseModel):
    moving_average_7d: list[dict]
    weekday_average: dict[str, float]
    current_streak: int
    longest_streak: int
    rest_days: int
    best_week: Optional[dict] = None


# ---------- 대화 (conversations 컬렉션) ----------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)
    created_at: Optional[str] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    messages: list[Message] = Field(..., min_length=1, max_length=200)


class ConversationSummaryItem(BaseModel):
    """목록 조회용: messages 는 포함하지 않는다 (불러오기는 GET /api/conversations/{id})."""

    id: str
    title: str
    message_count: int
    preview: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Conversation(BaseModel):
    id: str
    title: str
    messages: list[Message]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------- 채팅 ----------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="사용자 질문")
    conversation_id: Optional[str] = Field(None, description="이어서 대화할 대화 ID (없으면 새 대화)")

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("메시지가 비어 있습니다.")
        return v


class ToolCallLog(BaseModel):
    name: str
    arguments: dict


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    summary: DataSummary | None = None
    tool_calls: list[ToolCallLog] = []
