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


# --- 월별 전체 집계 ----------------------------------------------------------
def monthly_totals(
    monthly: pd.DataFrame, monthly_total: pd.DataFrame | None = None
) -> pd.DataFrame:
    """월별 전체 데이터. base_month 오름차순.

    원본에 '전체' 행이 있으면(`monthly_total`) 그 값을 그대로 쓰고,
    없으면 지점을 합산한다.
    """
    columns = [
        "customer_count",
        "total_assets",
        "transaction_customer_count",
        "app_user_count",
    ]
    if monthly.empty:
        return pd.DataFrame(
            columns=["base_month", *columns, "transaction_share", "app_share"]
        )

    if monthly_total is not None and not monthly_total.empty:
        # 원본이 '전체' 행을 담고 있으면 그 값을 그대로 쓴다.
        # 지점에서 다시 더하면 원본과 미세하게 달라질 수 있다.
        # 둘이 맞는지는 데이터 계층이 확인한다.
        totals = (
            monthly_total.loc[:, ["base_month", *columns]]
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
        "total_assets": _card("total_assets", diff_abs),
        "transaction_share": _card("transaction_share", diff_pp),
        "app_share": _card("app_share", diff_pp),
    }
