"""AI 채팅 서비스: 컨텍스트 주입 + Function Calling.

흐름
1. 데이터 요약 조회 (GET /api/data/summary 와 같은 build_summary 함수)
2. 요약을 시스템 프롬프트에 삽입 (컨텍스트 주입)
3. GPT 호출 — 요약만으로 부족하면 GPT가 도구(get_records 등)를 호출해 세부 데이터를 가져옴
4. 질문/답변을 conversations 컬렉션에 자동 저장
"""

import json
import logging
from datetime import date
from typing import Any, Optional

from openai import OpenAI, OpenAIError

from ..config import settings
from ..repositories.base import Repository
from . import conversation_service, data_service

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT_TEMPLATE = """당신은 사용자의 '{data_name}' 기록을 분석해 주는 친절한 데이터 분석 비서입니다.
오늘 날짜: {today}

[사용자 데이터 요약]
{summary_block}

지침
- 위 데이터 요약을 근거로 구체적인 숫자(단위 포함)를 들어 맞춤형으로 답하세요.
- 특정 날짜/기간의 세부 기록, 요일별 패턴, 연속 기록 등 요약에 없는 정보가 필요하면 제공된 도구를 호출하세요.
- 데이터에 없는 내용은 추측하지 말고 모른다고 말하세요.
- 답변은 한국어로, 3~6문장 정도로 간결하게. 필요하면 짧은 조언을 덧붙이세요."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_data_summary",
            "description": "전체 데이터의 최신 요약(기간, 개수, 합계/평균/최대/최소, 추세, 월별 요약)을 조회한다. "
                           "대화 중 데이터가 바뀌었을 수 있을 때 최신 값을 확인하는 용도.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_records",
            "description": "특정 기간의 일별 원본 기록(date, value, memo)을 조회한다. "
                           "'지난주', '10월 첫째 주', '어제 뭐 공부했지?' 같이 구체적 날짜가 필요한 질문에 사용.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "시작일 YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "종료일 YYYY-MM-DD"},
                    "limit": {"type": "integer", "description": "최대 개수 (기본 31, 최대 60)"},
                },
                "required": ["start_date", "end_date"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "추가 통계(요일별 평균, 현재/최장 연속 기록일, 쉬는 날 수, 최고 주간, 최근 14일 7일 이동평균)를 조회한다. "
                           "패턴·습관·꾸준함에 대한 질문에 사용.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_conversations",
            "description": "이전에 저장된 대화 목록(제목, 메시지 수, 마지막 메시지 미리보기)을 조회한다. "
                           "'예전에 뭐 물어봤지?' 같은 질문에 사용.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "최대 개수 (기본 10)"}},
                "additionalProperties": False,
            },
        },
    },
]


class ChatServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def build_system_prompt(summary: dict) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        data_name=settings.DATA_NAME,
        today=date.today().isoformat(),
        summary_block=data_service.summary_to_prompt_block(summary),
    )


def run_tool(name: str, args: dict, data_repo: Repository, conv_repo: Repository) -> Any:
    if name == "get_data_summary":
        return data_service.build_summary(data_repo)
    if name == "get_records":
        try:
            start = date.fromisoformat(args["start_date"])
            end = date.fromisoformat(args["end_date"])
        except (KeyError, ValueError):
            return {"error": "start_date, end_date 는 YYYY-MM-DD 형식이어야 합니다."}
        limit = max(1, min(int(args.get("limit") or 31), 60))
        rows = data_service.list_data(data_repo, start=start, end=end, order="asc", limit=limit)
        return [{"date": r["date"], "value": r["value"], "memo": r.get("memo", "")} for r in rows]
    if name == "get_statistics":
        stats = data_service.build_statistics(data_repo)
        stats["moving_average_7d"] = stats["moving_average_7d"][-14:]
        return stats
    if name == "list_conversations":
        limit = max(1, min(int(args.get("limit") or 10), 30))
        return conversation_service.list_conversations(conv_repo, limit=limit)
    return {"error": f"알 수 없는 도구: {name}"}


def _client() -> OpenAI:
    if not settings.OPENAI_API_KEY:
        raise ChatServiceError("OPENAI_API_KEY 가 설정되지 않았습니다. 서버 환경 변수를 확인하세요.", 503)
    return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=40)


def chat(message: str, conversation_id: Optional[str],
         data_repo: Repository, conv_repo: Repository) -> dict:
    # 1) 데이터 요약 → 2) 시스템 프롬프트 주입
    summary = data_service.build_summary(data_repo)
    messages: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt(summary)}]

    # 이전 대화 맥락 (비용 보호를 위해 최근 N개만)
    if conversation_id:
        prev = conv_repo.get(conversation_id)
        if prev:
            for m in prev.get("messages", [])[-settings.CHAT_HISTORY_LIMIT:]:
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    # 3) GPT 호출 (+ 도구 호출 루프)
    client = _client()
    tool_log: list[dict] = []
    reply = ""
    try:
        for round_no in range(MAX_TOOL_ROUNDS + 1):
            allow_tools = round_no < MAX_TOOL_ROUNDS
            resp = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                tools=TOOLS if allow_tools else None,
                max_completion_tokens=settings.OPENAI_MAX_TOKENS,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                reply = (msg.content or "").strip()
                break

            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = run_tool(tc.function.name, args, data_repo, conv_repo)
                tool_log.append({"name": tc.function.name, "arguments": args})
                logger.info("tool call: %s %s", tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
    except OpenAIError as e:
        logger.exception("OpenAI 호출 실패")
        raise ChatServiceError(f"AI 응답 생성에 실패했습니다: {e.__class__.__name__}", 502) from e

    if not reply:
        reply = "죄송해요, 답변을 생성하지 못했어요. 질문을 조금 바꿔서 다시 시도해 주세요."

    # 4) 대화 자동 저장
    conv = conversation_service.append_messages(
        conv_repo, conversation_id,
        [{"role": "user", "content": message}, {"role": "assistant", "content": reply}],
    )
    return {"reply": reply, "conversation_id": conv["id"], "summary": summary, "tool_calls": tool_log}
