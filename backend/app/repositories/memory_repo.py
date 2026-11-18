"""메모리 저장소 (Firebase 키 없이 로컬에서 UI/API를 확인할 때만 사용).

서버를 재시작하면 데이터가 사라진다. 배포 환경에서는 Firestore를 사용한다.
"""

from __future__ import annotations

import copy
import threading
import uuid
from typing import Optional

from .base import Repository


class MemoryRepository(Repository):
    def __init__(self):
        self._items: dict[str, dict] = {}
        self._lock = threading.Lock()

    def list(self, order_by=None, descending=False, limit=None):
        with self._lock:
            items = [{"id": k, **copy.deepcopy(v)} for k, v in self._items.items()]
        if order_by:
            items.sort(key=lambda x: x.get(order_by) or "", reverse=descending)
        return items[:limit] if limit else items

    def get(self, doc_id: str) -> Optional[dict]:
        with self._lock:
            item = self._items.get(doc_id)
            return {"id": doc_id, **copy.deepcopy(item)} if item else None

    def create(self, data: dict) -> dict:
        doc_id = uuid.uuid4().hex[:20]
        with self._lock:
            self._items[doc_id] = copy.deepcopy(data)
        return {"id": doc_id, **data}

    def update(self, doc_id: str, data: dict) -> Optional[dict]:
        with self._lock:
            if doc_id not in self._items:
                return None
            self._items[doc_id].update(copy.deepcopy(data))
        return self.get(doc_id)

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            return self._items.pop(doc_id, None) is not None

    def bulk_create(self, items: list[dict]) -> int:
        for item in items:
            self.create(item)
        return len(items)

    def count(self) -> int:
        return len(self._items)
