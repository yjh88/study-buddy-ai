"""데이터 CRUD + 시계열 분석(요약/통계) 서비스.

요약(summary)은 AI 시스템 프롬프트에 주입되는 '컨텍스트'의 원본이다.
"""

import statistics as st
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from ..config import settings
from ..repositories.base import Repository
from ..schemas import DataCreate, DataUpdate

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
TREND_WINDOW = 30      # 최근 30일 vs 직전 30일 비교
TREND_THRESHOLD = 5.0  # ±5% 이내면 '유지'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------- CRUD ----------------
def list_data(repo: Repository, start: Optional[date] = None, end: Optional[date] = None,
              order: str = "desc", limit: Optional[int] = None) -> list[dict]:
    items = repo.list(order_by="date", descending=(order == "desc"))
    if start:
        items = [i for i in items if i["date"] >= start.isoformat()]
    if end:
        items = [i for i in items if i["date"] <= end.isoformat()]
    return items[:limit] if limit else items


def create_data(repo: Repository, body: DataCreate) -> dict:
    now = _now()
    return repo.create({
        "date": body.date.isoformat(), "value": float(body.value), "memo": body.memo,
        "created_at": now, "updated_at": now,
    })


def update_data(repo: Repository, doc_id: str, body: DataUpdate) -> Optional[dict]:
    patch = body.model_dump(exclude_none=True)
    if "date" in patch:
        patch["date"] = patch["date"].isoformat()
    if "value" in patch:
        patch["value"] = float(patch["value"])
    patch["updated_at"] = _now()
    return repo.update(doc_id, patch)


def delete_data(repo: Repository, doc_id: str) -> bool:
    return repo.delete(doc_id)


# ---------------- 분석 ----------------
def _daily_series(items: list[dict]) -> "OrderedDict[str, float]":
    """같은 날짜의 기록은 합산하여 날짜 오름차순 일별 시계열로 만든다."""
    daily: dict[str, float] = defaultdict(float)
    for i in items:
        daily[i["date"]] += float(i.get("value", 0))
    return OrderedDict(sorted(daily.items()))


def _pct(new: float, old: float) -> Optional[float]:
    return None if old == 0 else (new - old) / old * 100


def _trend(series: "OrderedDict[str, float]") -> str:
    values = list(series.values())
    unit = settings.DATA_UNIT
    if len(values) < 14:
        return "데이터가 적어 추세 판단 불가"
    window = min(TREND_WINDOW, len(values) // 2)
    recent = st.mean(values[-window:])
    prev = st.mean(values[-2 * window:-window])
    change = _pct(recent, prev)
    if change is None:
        return f"상승 (최근 {window}일 평균 {recent:.1f}{unit})"
    label = "상승" if change > TREND_THRESHOLD else "하락" if change < -TREND_THRESHOLD else "유지"
    return f"{label} (최근 {window}일 평균 {recent:.1f}{unit}, 직전 {window}일 대비 {change:+.1f}%)"


def build_summary(repo: Repository) -> dict:
    items = repo.list(order_by="date")
    unit = settings.DATA_UNIT
    if not items:
        return {
            "period": "데이터 없음", "count": 0, "unit": unit,
            "metrics": {"total": 0, "average": 0, "max": 0, "min": 0, "std": 0},
            "trend": "데이터 없음", "recent_7d_average": None, "monthly": [], "latest": None,
        }

    series = _daily_series(items)
    dates, values = list(series.keys()), list(series.values())
    max_i, min_i = values.index(max(values)), values.index(min(values))

    monthly: dict[str, list[float]] = defaultdict(list)
    for d, v in series.items():
        monthly[d[:7]].append(v)

    latest = max(items, key=lambda i: (i["date"], i.get("updated_at") or ""))
    return {
        "period": f"{dates[0]} ~ {dates[-1]}",
        "count": len(items),
        "unit": unit,
        "metrics": {
            "total": round(sum(values), 1),
            "average": round(st.mean(values), 1),
            "max": values[max_i], "max_date": dates[max_i],
            "min": values[min_i], "min_date": dates[min_i],
            "std": round(st.pstdev(values), 1),
        },
        "trend": _trend(series),
        "recent_7d_average": round(st.mean(values[-7:]), 1),
        "monthly": [
            {"month": m, "days": len(v), "total": round(sum(v), 1), "average": round(st.mean(v), 1)}
            for m, v in sorted(monthly.items())
        ],
        "latest": latest,
    }


def build_statistics(repo: Repository) -> dict:
    series = _daily_series(repo.list(order_by="date"))
    dates, values = list(series.keys()), list(series.values())

    # 7일 이동평균
    ma = []
    for i, d in enumerate(dates):
        window = values[max(0, i - 6): i + 1]
        ma.append({"date": d, "value": values[i], "ma7": round(st.mean(window), 1)})

    # 요일별 평균
    by_wd: dict[int, list[float]] = defaultdict(list)
    for d, v in series.items():
        by_wd[date.fromisoformat(d).weekday()].append(v)
    weekday_avg = {WEEKDAYS_KO[k]: round(st.mean(by_wd[k]), 1) for k in range(7) if by_wd[k]}

    # 연속 학습일 (값 > 0 이고 날짜가 하루씩 이어질 때)
    longest = current = 0
    prev: Optional[date] = None
    for d, v in series.items():
        day = date.fromisoformat(d)
        if v > 0 and prev is not None and day - prev == timedelta(days=1) and current > 0:
            current += 1
        elif v > 0:
            current = 1
        else:
            current = 0
        longest = max(longest, current)
        prev = day

    # 주간 합계 최고 주
    weekly: dict[str, float] = defaultdict(float)
    for d, v in series.items():
        y, w, _ = date.fromisoformat(d).isocalendar()
        weekly[f"{y}-W{w:02d}"] += v
    best_week = None
    if weekly:
        wk = max(weekly, key=weekly.get)
        best_week = {"week": wk, "total": round(weekly[wk], 1)}

    return {
        "moving_average_7d": ma,
        "weekday_average": weekday_avg,
        "current_streak": current,
        "longest_streak": longest,
        "rest_days": sum(1 for v in values if v == 0),
        "best_week": best_week,
    }


def summary_to_prompt_block(summary: dict) -> str:
    """요약 dict → 시스템 프롬프트에 넣을 텍스트."""
    m, unit = summary["metrics"], summary["unit"]
    monthly = "\n".join(
        f"  - {x['month']}: {x['days']}일 기록, 합계 {x['total']:.0f}{unit}, 일평균 {x['average']:.1f}{unit}"
        for x in summary["monthly"]
    ) or "  - 없음"
    latest = summary.get("latest")
    latest_line = (
        f"{latest['date']} {latest['value']:.0f}{unit} ({latest.get('memo') or '메모 없음'})" if latest else "없음"
    )
    return (
        f"- 데이터 종류: {settings.DATA_NAME} (단위: {unit})\n"
        f"- 데이터 기간: {summary['period']}\n"
        f"- 총 레코드: {summary['count']}개\n"
        f"- 주요 지표: 합계 {m['total']:.0f}{unit}, 일평균 {m['average']:.1f}{unit}, "
        f"최대 {m['max']:.0f}{unit}({m.get('max_date')}), 최소 {m['min']:.0f}{unit}({m.get('min_date')}), "
        f"표준편차 {m['std']:.1f}\n"
        f"- 최근 7일 평균: {summary.get('recent_7d_average')}{unit}\n"
        f"- 최근 트렌드: {summary['trend']}\n"
        f"- 가장 최근 기록: {latest_line}\n"
        f"- 월별 요약:\n{monthly}"
    )
