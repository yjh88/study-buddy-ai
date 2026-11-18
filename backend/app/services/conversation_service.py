"""대화 기록 서비스."""

from datetime import datetime, timezone
from typing import Optional

from ..repositories.base import Repository
from ..schemas import ConversationCreate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_title(text: str) -> str:
    text = " ".join(text.split())
    return text[:30] + ("…" if len(text) > 30 else "")


def list_conversations(repo: Repository, limit: Optional[int] = None) -> list[dict]:
    """목록에는 messages 를 빼고 메타 정보(개수, 미리보기)만 담는다."""
    result = []
    for c in repo.list(order_by="updated_at", descending=True, limit=limit):
        msgs = c.get("messages", [])
        result.append({
            "id": c["id"],
            "title": c.get("title") or "제목 없음",
            "message_count": len(msgs),
            "preview": (msgs[-1]["content"][:60] if msgs else ""),
            "created_at": c.get("created_at"),
            "updated_at": c.get("updated_at"),
        })
    return result


def get_conversation(repo: Repository, conv_id: str) -> Optional[dict]:
    return repo.get(conv_id)


def create_conversation(repo: Repository, body: ConversationCreate) -> dict:
    now = _now()
    messages = [{**m.model_dump(), "created_at": m.created_at or now} for m in body.messages]
    first_user = next((m["content"] for m in messages if m["role"] == "user"), messages[0]["content"])
    return repo.create({
        "title": body.title or make_title(first_user),
        "messages": messages,
        "created_at": now,
        "updated_at": now,
    })


def append_messages(repo: Repository, conv_id: Optional[str], new_messages: list[dict]) -> dict:
    """채팅 자동 저장: conv_id 가 있으면 이어 붙이고, 없거나 사라졌으면 새 대화를 만든다."""
    now = _now()
    stamped = [{**m, "created_at": now} for m in new_messages]
    existing = repo.get(conv_id) if conv_id else None
    if existing:
        return repo.update(conv_id, {"messages": existing.get("messages", []) + stamped, "updated_at": now})
    first_user = next((m["content"] for m in stamped if m["role"] == "user"), "새 대화")
    return repo.create({"title": make_title(first_user), "messages": stamped,
                        "created_at": now, "updated_at": now})


def delete_conversation(repo: Repository, conv_id: str) -> bool:
    return repo.delete(conv_id)
