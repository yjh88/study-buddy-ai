"""저장소 인터페이스.

서비스 계층은 이 인터페이스만 알고, 실제 저장소가 Firestore인지
로컬 테스트용 메모리인지는 몰라도 되도록 분리했다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Repository(ABC):
    @abstractmethod
    def list(self, order_by: Optional[str] = None, descending: bool = False,
             limit: Optional[int] = None) -> list[dict]: ...

    @abstractmethod
    def get(self, doc_id: str) -> Optional[dict]: ...

    @abstractmethod
    def create(self, data: dict) -> dict: ...

    @abstractmethod
    def update(self, doc_id: str, data: dict) -> Optional[dict]: ...

    @abstractmethod
    def delete(self, doc_id: str) -> bool: ...

    @abstractmethod
    def bulk_create(self, items: list[dict]) -> int: ...

    @abstractmethod
    def count(self) -> int: ...
