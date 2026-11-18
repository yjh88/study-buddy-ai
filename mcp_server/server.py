"""MCP Server (보너스): 같은 내부 기능을 외부 채널(Claude Desktop 등 MCP 클라이언트)에서 도구로 호출.

배포된 FastAPI(REST)를 그대로 호출하는 얇은 어댑터라서, 웹 채팅과 MCP 클라이언트가
동일한 데이터/로직을 공유한다.

백엔드와 의존성(starlette/pydantic 버전)이 충돌하므로 별도 가상환경을 사용한다.
설치:  cd mcp_server && python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt
실행:  STUDY_API_BASE_URL=https://<render-app>.onrender.com .venv\\Scripts\\python server.py   (stdio 전송)

Claude Desktop 설정 예 (claude_desktop_config.json):
{
  "mcpServers": {
    "study-buddy": {
      "command": "C:/path/to/mcp_server/.venv/Scripts/python.exe",
      "args": ["C:/path/to/mcp_server/server.py"],
      "env": {"STUDY_API_BASE_URL": "https://<render-app>.onrender.com"}
    }
  }
}
"""

import json
import os
import urllib.parse
import urllib.request

from mcp.server.mcpserver import MCPServer

API_BASE = os.getenv("STUDY_API_BASE_URL", "http://localhost:8000").rstrip("/")

mcp = MCPServer("study-buddy")


def _get(path: str, params: dict | None = None):
    query = f"?{urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})}" if params else ""
    with urllib.request.urlopen(f"{API_BASE}{path}{query}", timeout=60) as resp:  # noqa: S310 (고정 API 주소)
        return json.loads(resp.read().decode("utf-8"))


@mcp.tool()
def get_data_summary() -> dict:
    """학습 시간 데이터 전체 요약(기간, 개수, 합계/평균/최대/최소, 추세, 월별 요약)을 조회한다."""
    return _get("/api/data/summary")


@mcp.tool()
def get_records(start_date: str, end_date: str, limit: int = 31) -> list:
    """특정 기간(YYYY-MM-DD ~ YYYY-MM-DD)의 일별 학습 기록(date, value, memo)을 조회한다."""
    rows = _get("/api/data", {"start": start_date, "end": end_date, "order": "asc", "limit": max(1, min(limit, 60))})
    return [{"date": r["date"], "value": r["value"], "memo": r.get("memo", "")} for r in rows]


@mcp.tool()
def get_statistics() -> dict:
    """요일별 평균, 현재/최장 연속 학습일, 쉰 날 수, 최고의 주 등 추가 통계를 조회한다."""
    stats = _get("/api/data/statistics")
    stats["moving_average_7d"] = stats["moving_average_7d"][-14:]
    return stats


@mcp.tool()
def list_conversations(limit: int = 10) -> list:
    """웹에서 저장된 이전 대화 목록(제목, 메시지 수, 미리보기)을 조회한다."""
    return _get("/api/conversations", {"limit": max(1, min(limit, 50))})


if __name__ == "__main__":
    mcp.run()
