"""data/study_log.csv 를 Firestore 'data' 컬렉션에 업로드한다.

실행 (backend 폴더에서):
    python -m scripts.seed_firestore           # 컬렉션이 비어 있을 때만 업로드
    python -m scripts.seed_firestore --force   # 기존 데이터가 있어도 추가 업로드

.env 의 FIREBASE_SERVICE_ACCOUNT_JSON 을 사용한다.
"""

import argparse
import sys

from app.config import settings
from app.repositories import DATA_COLLECTION, load_sample_rows
from app.repositories.firestore_repo import FirestoreRepository, init_firestore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="기존 문서가 있어도 업로드")
    args = parser.parse_args()

    if not settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        sys.exit("FIREBASE_SERVICE_ACCOUNT_JSON 이 설정되지 않았습니다 (.env 확인).")

    repo = FirestoreRepository(init_firestore(settings.FIREBASE_SERVICE_ACCOUNT_JSON), DATA_COLLECTION)
    existing = repo.count()
    if existing and not args.force:
        sys.exit(f"'{DATA_COLLECTION}' 컬렉션에 이미 {existing}건이 있습니다. 덮어쓰려면 --force 를 사용하세요.")

    n = repo.bulk_create(load_sample_rows())
    print(f"Firestore '{DATA_COLLECTION}' 컬렉션에 {n}건 업로드 완료.")


if __name__ == "__main__":
    main()
