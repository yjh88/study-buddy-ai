"""저장소 생성 및 의존성 제공.

컬렉션 구조
- data:          {date: "YYYY-MM-DD", value: number, memo: string, created_at, updated_at}
- conversations: {title, messages: [{role, content, created_at}], created_at, updated_at}
"""

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .base import Repository
from .memory_repo import MemoryRepository

logger = logging.getLogger(__name__)

DATA_COLLECTION = "data"
CONVERSATION_COLLECTION = "conversations"
SAMPLE_CSV = Path(__file__).resolve().parents[2] / "data" / "study_log.csv"


class _Store:
    backend: str = "uninitialized"
    data: Repository
    conversations: Repository


store = _Store()


def load_sample_rows() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    with SAMPLE_CSV.open(encoding="utf-8") as f:
        return [
            {"date": r["date"], "value": float(r["value"]), "memo": r["memo"],
             "created_at": now, "updated_at": now}
            for r in csv.DictReader(f)
        ]


def init_store() -> None:
    mode = settings.DB_BACKEND
    use_firestore = mode == "firestore" or (mode == "auto" and settings.FIREBASE_SERVICE_ACCOUNT_JSON)

    if use_firestore:
        from .firestore_repo import FirestoreRepository, init_firestore

        client = init_firestore(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
        store.data = FirestoreRepository(client, DATA_COLLECTION)
        store.conversations = FirestoreRepository(client, CONVERSATION_COLLECTION)
        store.backend = "firestore"
        logger.info("Firestore 저장소를 사용합니다.")
        # 최초 배포 시 data 컬렉션이 비어 있으면 샘플 데이터를 한 번만 업로드
        if settings.SEED_SAMPLE_IF_EMPTY and store.data.count() == 0:
            n = store.data.bulk_create(load_sample_rows())
            logger.info("Firestore 'data' 컬렉션이 비어 있어 샘플 %d건을 업로드했습니다.", n)
    else:
        store.data = MemoryRepository()
        store.conversations = MemoryRepository()
        store.backend = "memory"
        n = store.data.bulk_create(load_sample_rows())
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON 이 없어 메모리 저장소를 사용합니다 (샘플 %d건 로드, 재시작 시 초기화).", n
        )


def get_data_repo() -> Repository:
    return store.data


def get_conversation_repo() -> Repository:
    return store.conversations
