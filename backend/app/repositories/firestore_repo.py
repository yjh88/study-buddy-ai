"""Firestore 저장소 구현."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from .base import Repository

logger = logging.getLogger(__name__)


def init_firestore(service_account: str):
    """FIREBASE_SERVICE_ACCOUNT_JSON 값으로 Firestore 클라이언트를 만든다.

    - 값이 '{' 로 시작하면 JSON 문자열로 간주 (Render 환경 변수에 키 내용을 통째로 넣는 방식)
    - 아니면 키 파일 경로로 간주 (로컬 개발용)
    """
    raw = service_account.strip()
    if raw.startswith("{"):
        cred = credentials.Certificate(json.loads(raw))
    elif os.path.exists(raw):
        cred = credentials.Certificate(raw)
    else:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON 이 JSON 문자열도, 존재하는 파일 경로도 아닙니다.")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()


class FirestoreRepository(Repository):
    def __init__(self, client, collection: str):
        self.col = client.collection(collection)

    @staticmethod
    def _to_dict(doc) -> dict:
        return {"id": doc.id, **(doc.to_dict() or {})}

    def list(self, order_by=None, descending=False, limit=None):
        query = self.col
        if order_by:
            direction = firestore.Query.DESCENDING if descending else firestore.Query.ASCENDING
            query = query.order_by(order_by, direction=direction)
        if limit:
            query = query.limit(limit)
        return [self._to_dict(d) for d in query.stream()]

    def get(self, doc_id: str) -> Optional[dict]:
        doc = self.col.document(doc_id).get()
        return self._to_dict(doc) if doc.exists else None

    def create(self, data: dict) -> dict:
        ref = self.col.document()
        ref.set(data)
        return {"id": ref.id, **data}

    def update(self, doc_id: str, data: dict) -> Optional[dict]:
        ref = self.col.document(doc_id)
        if not ref.get().exists:
            return None
        ref.update(data)
        return self._to_dict(ref.get())

    def delete(self, doc_id: str) -> bool:
        ref = self.col.document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    def bulk_create(self, items: list[dict]) -> int:
        # Firestore 배치는 최대 500개 쓰기
        written = 0
        for i in range(0, len(items), 400):
            batch = self.col._client.batch()
            for item in items[i:i + 400]:
                batch.set(self.col.document(), item)
            batch.commit()
            written += len(items[i:i + 400])
        return written

    def count(self) -> int:
        result = self.col.count().get()
        return int(result[0][0].value)
