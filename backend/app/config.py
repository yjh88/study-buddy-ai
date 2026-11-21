"""환경 변수 기반 설정.

키/비밀값은 절대 코드에 넣지 않고 .env(로컬) 또는 Render 환경 변수(배포)에서 읽는다.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [v.strip().rstrip("/") for v in value.split(",") if v.strip()]


class Settings:
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "600"))

    # Firebase: JSON 문자열 또는 키 파일 경로 둘 다 허용
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    # firestore | memory | auto(기본: 키가 있으면 firestore, 없으면 memory)
    DB_BACKEND: str = os.getenv("DB_BACKEND", "auto").lower()
    # Firestore 'data' 컬렉션이 비어 있으면 시작 시 샘플 CSV를 업로드 (true/false)
    SEED_SAMPLE_IF_EMPTY: bool = os.getenv("SEED_SAMPLE_IF_EMPTY", "true").lower() == "true"

    # CORS 허용 도메인 (쉼표 구분). 예: https://my-app.vercel.app,http://localhost:5500
    ALLOWED_ORIGINS: list[str] = _split_csv(
        os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,http://127.0.0.1:3000",
        )
    )

    # 비용 보호: IP당 분당 채팅 요청 수, 프롬프트에 넣을 과거 메시지 수
    CHAT_RATE_LIMIT_PER_MIN: int = int(os.getenv("CHAT_RATE_LIMIT_PER_MIN", "10"))
    CHAT_HISTORY_LIMIT: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))

    # 데이터 단위/이름 (요약·프롬프트 문구에 사용)
    DATA_NAME: str = os.getenv("DATA_NAME", "일일 학습 시간")
    DATA_UNIT: str = os.getenv("DATA_UNIT", "분")


settings = Settings()
