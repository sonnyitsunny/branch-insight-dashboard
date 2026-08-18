"""공통 집계와 계산.

어느 탭에서나 쓰는 계산 도구와, 탭 위에 있는 KPI 카드 값만 둔다.
탭마다 다른 계산은 그 탭 모듈에 있다(→ dashboard.tabs).

전체 기준 값은 지점 비율의 단순 평균이 아니라 항상 분자·분모를 각각 합산해
계산한다. 같은 계산을 차트나 콜백에서 다시 구현하지 않는다.

분모가 0이거나 기준 월·지점 데이터가 없으면 예외를 던지지 않고 None을
돌려준다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from dashboard.data import shift_month


# --- 기준 월 해석
# -------------------------------------------------------------
def _latest_month(frame: pd.DataFrame) -> str | None:
    """데이터에 들어 있는 가장 최근 월."""
    if frame.empty or "base_month" not in frame.columns:
        return None
    months = frame["base_month"].dropna()
    return None if months.empty else str(months.max())


def resolve_current_month(
    frame: pd.DataFrame, current_month: str | None
) -> str | None:
    """기준 월을 정한다. 지정하지 않으면 데이터의 최신 월을 쓴다.

    상수를 기본 인자로 박아두면 실제 데이터의 기간이 달라졌을 때 조용히
    빈 화면이 된다. 그래서 기본값을 상수가 아니라 데이터에서 끌어온다.
    """
    return current_month if current_month else _latest_month(frame)


def row_for_month(frame: pd.DataFrame, base_month: str) -> pd.Series | None:
    """해당 월의 첫 행. 없으면 None."""
    if frame.empty:
        return None
    matched = frame[frame["base_month"] == base_month]
    if matched.empty:
        return None
    return matched.iloc[0]


# --- 기본 계산 ---------------------------------------------------------------
def to_float(value: object) -> float | None:
    """숫자로 읽는다. 읽을 수 없거나 NaN·inf면 None."""
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def safe_ratio(numerator: object, denominator: object) -> float | None:
    """분모가 0이거나 값이 없으면 None을 반환한다."""
    top = to_float(numerator)
    bottom = to_float(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    return top / bottom


def share_percent(numerator: object, denominator: object) -> float | None:
    """비중(%)을 계산한다."""
    ratio = safe_ratio(numerator, denominator)
    return None if ratio is None else ratio * 100.0


def yoy_rate(current: object, base: object) -> float | None:
    """전년 동월 대비 증가율(%)."""
    return diff_rate(current, base)


def diff_abs(current: object, previous: object) -> float | None:
    """절대 증감."""
    now = to_float(current)
    before = to_float(previous)
    if now is None or before is None:
        return None
    return now - before


def diff_pp(current_percent: object, previous_percent: object) -> float | None:
    """비율의 퍼센트포인트 차이."""
    return diff_abs(current_percent, previous_percent)


def diff_rate(current: object, previous: object) -> float | None:
    """증감률(%). 비교 시점 값이 없거나 0이면 None.

    분모가 0일 때 0%로 돌려주면 "변화 없음"으로 읽힌다. 계산할 수 없다는
    사실을 그대로 넘겨 화면이 `-`로 표시하게 한다.
    """
    ratio = safe_ratio(current, previous)
    return None if ratio is None else (ratio - 1.0) * 100.0


def weighted_mean(values: object, weights: object) -> float | None:
    """고객 수 등을 가중치로 사용한 가중평균."""
    value_array = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(
        dtype=float
    )
    weight_array = pd.to_numeric(pd.Series(weights), errors="coerce").to_numpy(
        dtype=float
    )
    if value_array.size == 0 or value_array.size != weight_array.size:
        return None
    mask = ~(np.isnan(value_array) | np.isnan(weight_array))
    if not mask.any():
        return None
    total_weight = weight_array[mask].sum()
    if total_weight == 0:
        return None
    return float((value_array[mask] * weight_array[mask]).sum() / total_weight)


def fill_deltas(trend: pd.DataFrame) -> None:
    """`<구분>_value`에서 전월 대비 증감을 만들어 `<구분>_delta`에 채운다.

    전체를 막대로, 고른 지점을 선으로 그리는 추이 그림이 모두 이 형태를
    쓴다. 값을 바꾸면 증감도 다시 만들어야 하므로 한 곳에 둔다.
    """
    for name in ("total", "branch"):
        values = trend[f"{name}_value"]
        trend[f"{name}_delta"] = [
            diff_abs(values.iloc[index], values.iloc[index - 1])
            if index > 0
            else None
            for index in range(len(values))
        ]


# --- 분류축이 있는 긴 프레임 -------------------------------------------------
# 거래·수익 원본은 지점 × 월에 분류축이 하나 이상 더 붙는다. "어느 분류를
# 볼지"를 `where`로 받아 걸러 낸 뒤 쓰는 도구를 여기 둔다. 탭마다 다시
# 만들면 같은 계산이 갈라진다(→ AGENTS.md §15).
def matching(frame: pd.DataFrame, where: dict) -> pd.DataFrame:
    """분류값으로 걸러 낸다. 없는 컬럼을 넘기면 빈 프레임이 된다."""
    rows = frame
    for column, value in where.items():
        if column not in rows.columns:
            return rows.iloc[0:0]
        rows = rows[rows[column] == value]
    return rows


def series_by_month(
    frame: pd.DataFrame | None, where: dict, column: str
) -> pd.Series:
    """걸러 낸 행을 기준 월로 찾을 수 있게 만든다."""
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    rows = matching(frame, where)
    if rows.empty:
        return pd.Series(dtype=float)
    return rows.set_index("base_month")[column]


def month_values(
    frame: pd.DataFrame | None, where: dict, month: str, column: str
) -> dict[str, float | None]:
    """그 달의 지점별 값. {지점명: 값}.

    분류축이 있는 프레임에서 한 묶음만 뽑아 지점 이름으로 찾을 수 있게
    만든다. 없는 지점은 아예 담기지 않으므로 표에서 빈 칸이 된다.
    """
    if frame is None or frame.empty or column not in frame.columns:
        return {}
    rows = matching(frame, {**where, "base_month": month})
    if rows.empty:
        return {}
    return {
        str(name): to_float(value)
        for name, value in zip(rows["branch_name"], rows[column])
    }


def growth_scatter(
    frame: pd.DataFrame,
    column: str,
    current_month: str,
    base_month: str,
    where: dict | None = None,
) -> pd.DataFrame:
    """지점마다 기준 월 값과 전년 동월 대비 증가율(%).

    비교할 달이 데이터에 없거나 그때 값이 0이면 증가율을 만들 수 없다.
    그 지점은 0%로 채우지 않고 빼 둔다. 0%는 "변화 없음"으로 읽힌다
    (→ diff_rate).
    """
    columns = ["branch_name", "value", "growth"]
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=columns)

    rows = matching(frame, where or {})
    if rows.empty:
        return pd.DataFrame(columns=columns)

    now = rows[rows["base_month"] == current_month]
    before = rows[rows["base_month"] == base_month]
    if now.empty:
        return pd.DataFrame(columns=columns)
    past = before.set_index("branch_name")[column]

    scatter = pd.DataFrame(
        {
            "branch_name": now["branch_name"].astype(str),
            "value": [to_float(value) for value in now[column]],
            "growth": [
                yoy_rate(value, past.get(str(name)))
                for name, value in zip(now["branch_name"], now[column])
            ],
        }
    )
    return scatter.dropna(subset=["value", "growth"]).reset_index(drop=True)


def median_value(scatter: pd.DataFrame) -> float | None:
    """산점도 세로 기준선 자리. 값이 없으면 None."""
    if scatter.empty or "value" not in scatter.columns:
        return None
    values = pd.to_numeric(scatter["value"], errors="coerce").dropna()
    return float(values.median()) if not values.empty else None


# --- 월별 전체 집계 ----------------------------------------------------------
# 월별 전체로 합산하는 지표. 원본에 없으면 비운 채로 둔다.
TOTAL_MEASURES = (
    "customer_count",
    "total_assets",
    "net_assets",
    "transaction_customer_count",
    "app_user_count",
    # 공통고객 수익(원). 다른 금액 컬럼과 단위가 다르다
    # (→ dashboard/sources/__init__.py 의 merge_revenue).
    "common_revenue",
)


def monthly_totals(
    monthly: pd.DataFrame, monthly_total: pd.DataFrame | None = None
) -> pd.DataFrame:
    """월별 전체 데이터. base_month 오름차순.

    원본에 '전체' 행이 있으면(`monthly_total`) 그 값을 그대로 쓰고,
    없으면 지점을 합산한다.
    """
    if monthly.empty:
        return pd.DataFrame(
            columns=[
                "base_month",
                *TOTAL_MEASURES,
                "transaction_share",
                "app_share",
            ]
        )
    # 프레임에 있는 지표만 더한다. 없는 지표는 아래에서 비운 채로 둔다.
    columns = [
        column for column in TOTAL_MEASURES if column in monthly.columns
    ]

    if monthly_total is not None and not monthly_total.empty:
        # 원본이 '전체' 행을 담고 있으면 그 값을 그대로 쓴다.
        # 지점에서 다시 더하면 원본과 미세하게 달라질 수 있다.
        # 둘이 맞는지는 데이터 계층이 확인한다.
        given = [
            column for column in columns if column in monthly_total.columns
        ]
        totals = (
            monthly_total.loc[:, ["base_month", *given]]
            .sort_values("base_month")
            .reset_index(drop=True)
        )
    else:
        # min_count=1 — 원본에 없는 컬럼은 합계도 없는 값으로 둔다.
        # 기본값 0을 쓰면 데이터가 없다는 사실이 "0원"이라는 숫자로
        # 화면에 나타난다.
        totals = (
            monthly.groupby("base_month", observed=True)[columns]
            .sum(min_count=1)
            .sort_index()
            .reset_index()
        )
    # 프레임에 아예 없던 지표는 비운 채로 둔다. 0으로 채우면 "없음"이
    # "0으로 측정됨"으로 바뀐다.
    for column in TOTAL_MEASURES:
        if column not in totals.columns:
            totals[column] = np.nan

    totals["transaction_share"] = [
        share_percent(row.transaction_customer_count, row.customer_count)
        for row in totals.itertuples()
    ]
    totals["app_share"] = [
        share_percent(row.app_user_count, row.customer_count)
        for row in totals.itertuples()
    ]
    return totals


def kpi_metrics(
    monthly: pd.DataFrame,
    current_month: str | None = None,
    previous_month: str | None = None,
    monthly_total: pd.DataFrame | None = None,
) -> dict[str, dict[str, float | None]]:
    """상단 KPI 카드 값. 항상 전체 기준이다.

    KPI 행은 탭 위에 있으므로 어느 탭을 골라도 같은 값을 보여준다.
    월을 지정하지 않으면 데이터의 최신 월과 그 전월을 쓴다.
    """
    totals = monthly_totals(monthly, monthly_total)
    current_month = resolve_current_month(monthly, current_month)
    if current_month is None:
        current_month = ""
    if previous_month is None:
        previous_month = (
            shift_month(current_month, -1) if current_month else ""
        )
    current = row_for_month(totals, current_month)
    previous = row_for_month(totals, previous_month)

    def _value(row: pd.Series | None, column: str) -> float | None:
        if row is None:
            return None
        return to_float(row[column])

    def _card(column: str, delta_fn) -> dict[str, float | None]:
        """카드 하나의 값·증감·증감률.

        `delta`의 단위는 지표마다 다르다(인원·금액은 절대 증감, 비율은
        퍼센트포인트). `rate`는 어느 지표든 전월 값 대비 몇 % 움직였는지로
        같은 뜻을 갖는다.
        """
        now = _value(current, column)
        before = _value(previous, column)
        return {
            "value": now,
            "delta": delta_fn(now, before),
            "rate": diff_rate(now, before),
        }

    return {
        "customer_count": _card("customer_count", diff_abs),
        "net_assets": _card("net_assets", diff_abs),
        "transaction_share": _card("transaction_share", diff_pp),
        "app_share": _card("app_share", diff_pp),
        "common_revenue": _card("common_revenue", diff_abs),
    }
