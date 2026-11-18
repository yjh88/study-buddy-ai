"""학습 시간 시계열 데이터 생성 스크립트.

180일치 '일일 학습 시간(분)' 데이터를 만들어 data/study_log.csv 로 저장한다.
- 완만한 상승 추세 (꾸준히 공부 습관이 붙는 상황)
- 요일 패턴 (주말은 길게, 금요일은 짧게)
- 가끔 쉬는 날(0분), 시험 주간 같은 집중 구간
- 시드 고정으로 항상 같은 데이터가 생성됨

실행: python scripts/generate_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
DAYS = 180
END_DATE = date(2026, 11, 17)

TOPICS = [
    "Python 기초 문법", "자료구조 복습", "알고리즘 문제 풀이", "FastAPI 라우터 실습",
    "Pydantic 검증", "Firestore CRUD", "OpenAI API 실습", "프롬프트 엔지니어링",
    "pandas 데이터 분석", "시계열 분석 개념", "HTML/CSS 레이아웃", "JavaScript fetch",
    "Git 브랜치 전략", "SQL 쿼리 연습", "통계 기초", "배포(Render/Vercel)",
    "CORS 개념 정리", "테스트 코드 작성", "선형대수 복습", "논문 읽기",
]
WEEKDAY_FACTOR = {0: 1.0, 1: 1.05, 2: 1.0, 3: 0.95, 4: 0.7, 5: 1.35, 6: 1.2}


def generate() -> list[dict]:
    rng = random.Random(SEED)
    start = END_DATE - timedelta(days=DAYS - 1)
    rows = []
    for i in range(DAYS):
        d = start + timedelta(days=i)
        base = 70 + i * 0.45  # 70분 → 약 150분으로 서서히 증가
        value = base * WEEKDAY_FACTOR[d.weekday()] + rng.gauss(0, 18)

        memo = rng.choice(TOPICS)
        # 시험 대비 집중 구간 (약 120~130일차)
        if 120 <= i <= 130:
            value *= 1.4
            memo = f"집중 주간 - {memo}"
        # 가끔 쉬는 날
        if rng.random() < 0.05:
            value, memo = 0, "휴식"

        rows.append({"date": d.isoformat(), "value": max(0, round(value)), "memo": memo})
    return rows


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "study_log.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = generate()
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value", "memo"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}개 데이터 포인트를 {out} 에 저장했습니다.")


if __name__ == "__main__":
    main()
