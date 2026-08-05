"""집계와 계산.

전체 기준 값은 지점 비율의 단순 평균이 아니라 항상 분자·분모를 각각 합산해
계산한다. 같은 계산을 차트나 콜백에서 다시 구현하지 않는다.

분모가 0이거나 기준 월·지점 데이터가 없으면 예외를 던지지 않고 None을 돌려준다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from dashboard.data import (
    AGE_GROUPS,
    CONSENT_LABEL,
    INVESTMENT_TYPES,
    NON_CONSENT_LABEL,
    TOTAL_LABEL,
    YOY_MONTHS,
    shift_month,
)

TREND_COLUMNS = (
    "base_month",
    "total_count",
    "total_delta",
    "branch_count",
    "branch_delta",
    "branch_yoy",
)
SCATTER_COLUMNS = ("branch_name", "base_count", "current_count", "count_delta", "yoy")
AGE_COLUMNS = ("age_group", "scope", "customer_count", "share")
INVESTMENT_COLUMNS = (
    "investment_type",
    "consent_label",
    "customer_count",
    "share",
    "type_total",
)
TABLE_COLUMNS = (
    "branch_name",
    "customer_count",
    "customer_growth_yoy",
    "male_share",
    "average_age",
    "recent_signup_share",
    "recommendation_share",
    "grade_s_share",
)


# --- 기준 월 해석 -------------------------------------------------------------
def _latest_month(frame: pd.DataFrame) -> str | None:
    """데이터에 들어 있는 가장 최근 월."""
    if frame.empty or "base_month" not in frame.columns:
        return None
    months = frame["base_month"].dropna()
    return None if months.empty else str(months.max())


def resolve_current_month(frame: pd.DataFrame, current_month: str | None) -> str | None:
    """기준 월을 정한다. 지정하지 않으면 데이터의 최신 월을 쓴다.

    상수를 기본 인자로 박아두면 실제 데이터의 기간이 달라졌을 때 조용히
    빈 화면이 된다. 그래서 기본값을 상수가 아니라 데이터에서 끌어온다.
    """
    return current_month if current_month else _latest_month(frame)


# --- 기본 계산 ---------------------------------------------------------------
def _to_float(value: object) -> float | None:
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
    top = _to_float(numerator)
    bottom = _to_float(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    return top / bottom


def share_percent(numerator: object, denominator: object) -> float | None:
    """비중(%)을 계산한다."""
    ratio = safe_ratio(numerator, denominator)
    return None if ratio is None else ratio * 100.0


def yoy_rate(current: object, base: object) -> float | None:
    """전년 동월 대비 증가율(%)."""
    ratio = safe_ratio(current, base)
    return None if ratio is None else (ratio - 1.0) * 100.0


def diff_abs(current: object, previous: object) -> float | None:
    """절대 증감."""
    now = _to_float(current)
    before = _to_float(previous)
    if now is None or before is None:
        return None
    return now - before


def diff_pp(current_percent: object, previous_percent: object) -> float | None:
    """비율의 퍼센트포인트 차이."""
    return diff_abs(current_percent, previous_percent)


def weighted_mean(values: object, weights: object) -> float | None:
    """고객 수 등을 가중치로 사용한 가중평균."""
    value_array = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    weight_array = pd.to_numeric(pd.Series(weights), errors="coerce").to_numpy(dtype=float)
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
def monthly_totals(monthly: pd.DataFrame) -> pd.DataFrame:
    """모든 지점을 합산한 월별 전체 데이터. base_month 오름차순."""
    columns = ["customer_count", "total_assets", "transaction_customer_count", "app_user_count"]
    if monthly.empty:
        return pd.DataFrame(columns=["base_month", *columns, "transaction_share", "app_share"])
    totals = (
        monthly.groupby("base_month", observed=True)[columns].sum().sort_index().reset_index()
    )
    totals["transaction_share"] = [
        share_percent(row.transaction_customer_count, row.customer_count)
        for row in totals.itertuples()
    ]
    totals["app_share"] = [
        share_percent(row.app_user_count, row.customer_count) for row in totals.itertuples()
    ]
    return totals


def _row_for_month(frame: pd.DataFrame, base_month: str) -> pd.Series | None:
    if frame.empty:
        return None
    matched = frame[frame["base_month"] == base_month]
    if matched.empty:
        return None
    return matched.iloc[0]


def kpi_metrics(
    monthly: pd.DataFrame,
    current_month: str | None = None,
    previous_month: str | None = None,
) -> dict[str, dict[str, float | None]]:
    """상단 KPI 카드 값. 항상 전체 지점 합산 기준이다.

    월을 지정하지 않으면 데이터의 최신 월과 그 전월을 쓴다.
    """
    totals = monthly_totals(monthly)
    current_month = resolve_current_month(monthly, current_month)
    if current_month is None:
        current_month = ""
    if previous_month is None:
        previous_month = shift_month(current_month, -1) if current_month else ""
    current = _row_for_month(totals, current_month)
    previous = _row_for_month(totals, previous_month)

    def _value(row: pd.Series | None, column: str) -> float | None:
        if row is None:
            return None
        return _to_float(row[column])

    return {
        "customer_count": {
            "value": _value(current, "customer_count"),
            "delta": diff_abs(_value(current, "customer_count"), _value(previous, "customer_count")),
        },
        "total_assets": {
            "value": _value(current, "total_assets"),
            "delta": diff_abs(_value(current, "total_assets"), _value(previous, "total_assets")),
        },
        "transaction_share": {
            "value": _value(current, "transaction_share"),
            "delta": diff_pp(
                _value(current, "transaction_share"), _value(previous, "transaction_share")
            ),
        },
        "app_share": {
            "value": _value(current, "app_share"),
            "delta": diff_pp(_value(current, "app_share"), _value(previous, "app_share")),
        },
    }


# --- 고객 추이 ---------------------------------------------------------------
def customer_trend(monthly: pd.DataFrame, branch_name: str) -> pd.DataFrame:
    """전체 막대와 선택 지점 선그래프에 쓰는 월별 데이터."""
    if monthly.empty:
        return pd.DataFrame(columns=list(TREND_COLUMNS))

    totals = monthly_totals(monthly)[["base_month", "customer_count"]].rename(
        columns={"customer_count": "total_count"}
    )
    branch = (
        monthly[monthly["branch_name"] == branch_name][["base_month", "customer_count"]]
        .rename(columns={"customer_count": "branch_count"})
        .sort_values("base_month")
    )
    trend = totals.merge(branch, on="base_month", how="left").sort_values("base_month")
    trend["total_delta"] = trend["total_count"].diff()
    trend["branch_delta"] = trend["branch_count"].diff()

    # YoY는 행 번호가 아니라 월 라벨로 12개월 전을 찾는다.
    # 행 번호로 세면 중간에 빠진 월이 있을 때 엉뚱한 달과 비교하면서도
    # 오류 없이 그럴듯한 숫자를 내놓는다.
    base_counts = dict(zip(trend["base_month"], trend["branch_count"]))
    trend["branch_yoy"] = [
        yoy_rate(count, base_counts.get(shift_month(month, -YOY_MONTHS)))
        for month, count in zip(trend["base_month"], trend["branch_count"])
    ]
    return trend.loc[:, list(TREND_COLUMNS)].reset_index(drop=True)


# --- 고객 수 및 성장률 산점도 -------------------------------------------------
def growth_scatter(
    monthly: pd.DataFrame,
    current_month: str | None = None,
    base_month: str | None = None,
) -> pd.DataFrame:
    """지점별 고객 수와 YoY 증가율.

    월을 지정하지 않으면 데이터의 최신 월과 그 12개월 전을 쓴다.
    """
    if monthly.empty:
        return pd.DataFrame(columns=list(SCATTER_COLUMNS))

    current_month = resolve_current_month(monthly, current_month)
    if current_month is None:
        return pd.DataFrame(columns=list(SCATTER_COLUMNS))
    if base_month is None:
        base_month = shift_month(current_month, -YOY_MONTHS)

    current = monthly[monthly["base_month"] == current_month][["branch_name", "customer_count"]]
    base = monthly[monthly["base_month"] == base_month][["branch_name", "customer_count"]]
    merged = current.merge(
        base, on="branch_name", how="left", suffixes=("_current", "_base")
    ).rename(
        columns={"customer_count_current": "current_count", "customer_count_base": "base_count"}
    )
    merged["count_delta"] = [
        diff_abs(row.current_count, row.base_count) for row in merged.itertuples()
    ]
    merged["yoy"] = [yoy_rate(row.current_count, row.base_count) for row in merged.itertuples()]
    return merged.loc[:, list(SCATTER_COLUMNS)].sort_values("branch_name").reset_index(drop=True)


def median_customer_count(scatter: pd.DataFrame) -> float | None:
    """산점도 세로 기준선에 쓰는 고객 수 중앙값."""
    if scatter.empty:
        return None
    values = pd.to_numeric(scatter["current_count"], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.median())


# --- 연령별 고객 분포 ---------------------------------------------------------
def age_distribution(
    age: pd.DataFrame, branch_name: str, base_month: str | None = None
) -> pd.DataFrame:
    """전체와 선택 지점의 연령 구간별 고객 수·비중.

    전체 비중은 지점 비율의 평균이 아니라 구간별 고객 수 합계를 전체 고객 수로 나눈다.
    월을 지정하지 않으면 데이터의 최신 월을 쓴다.
    """
    if age.empty:
        return pd.DataFrame(columns=list(AGE_COLUMNS))

    base_month = resolve_current_month(age, base_month)
    if base_month is None:
        return pd.DataFrame(columns=list(AGE_COLUMNS))

    month_data = age[age["base_month"] == base_month]
    if month_data.empty:
        return pd.DataFrame(columns=list(AGE_COLUMNS))

    frames = []
    total_counts = month_data.groupby("age_group", observed=True)["customer_count"].sum()
    frames.append(_age_frame(total_counts, TOTAL_LABEL))

    branch_data = month_data[month_data["branch_name"] == branch_name]
    if not branch_data.empty:
        branch_counts = branch_data.groupby("age_group", observed=True)["customer_count"].sum()
        frames.append(_age_frame(branch_counts, branch_name))

    return pd.concat(frames, ignore_index=True)


def _age_frame(counts: pd.Series, scope: str) -> pd.DataFrame:
    counts = counts.reindex(list(AGE_GROUPS), fill_value=0)
    total = float(counts.sum())
    return pd.DataFrame(
        {
            "age_group": list(AGE_GROUPS),
            "scope": scope,
            "customer_count": counts.to_numpy(dtype=int),
            "share": [share_percent(value, total) for value in counts.to_numpy()],
        }
    )


# --- 투자성향 ----------------------------------------------------------------
def investment_breakdown(
    investment: pd.DataFrame, scope: str = TOTAL_LABEL, base_month: str | None = None
) -> pd.DataFrame:
    """투자성향별 마케팅 동의·불원 구성. 성향 순서는 고정한다.

    월을 지정하지 않으면 데이터의 최신 월을 쓴다.
    """
    if investment.empty:
        return pd.DataFrame(columns=list(INVESTMENT_COLUMNS))

    base_month = resolve_current_month(investment, base_month)
    if base_month is None:
        return pd.DataFrame(columns=list(INVESTMENT_COLUMNS))

    month_data = investment[investment["base_month"] == base_month]
    if scope != TOTAL_LABEL:
        month_data = month_data[month_data["branch_name"] == scope]
    if month_data.empty:
        return pd.DataFrame(columns=list(INVESTMENT_COLUMNS))

    grouped = (
        month_data.groupby(["investment_type", "marketing_consent"], observed=True)["customer_count"]
        .sum()
        .unstack(fill_value=0)
        .reindex(list(INVESTMENT_TYPES), fill_value=0)
    )
    consent = grouped.get(True, pd.Series(0, index=grouped.index))
    non_consent = grouped.get(False, pd.Series(0, index=grouped.index))
    type_total = consent.add(non_consent, fill_value=0)

    rows = []
    for investment_type in INVESTMENT_TYPES:
        total = float(type_total.get(investment_type, 0))
        for label, series in ((CONSENT_LABEL, consent), (NON_CONSENT_LABEL, non_consent)):
            count = int(series.get(investment_type, 0))
            rows.append(
                {
                    "investment_type": investment_type,
                    "consent_label": label,
                    "customer_count": count,
                    "share": share_percent(count, total),
                    "type_total": int(total),
                }
            )
    return pd.DataFrame(rows, columns=list(INVESTMENT_COLUMNS))


# --- 지점별 고객 현황 테이블 --------------------------------------------------
def branch_table(
    monthly: pd.DataFrame,
    summary: pd.DataFrame,
    current_month: str | None = None,
    base_month: str | None = None,
) -> tuple[dict[str, float | str | None], pd.DataFrame]:
    """(전체 행, 지점별 행)을 반환한다. 비율은 모두 분자·분모 합산으로 계산한다.

    월을 지정하지 않으면 데이터의 최신 월과 그 12개월 전을 쓴다.
    """
    empty_rows = pd.DataFrame(columns=list(TABLE_COLUMNS))
    if summary.empty or monthly.empty:
        return {}, empty_rows

    current_month = resolve_current_month(summary, current_month)
    if current_month is None:
        return {}, empty_rows
    if base_month is None:
        base_month = shift_month(current_month, -YOY_MONTHS)

    current = summary[summary["base_month"] == current_month]
    if current.empty:
        return {}, empty_rows

    base_counts = (
        monthly[monthly["base_month"] == base_month]
        .set_index("branch_name")["customer_count"]
        .to_dict()
    )

    rows = []
    for row in current.itertuples():
        rows.append(
            {
                "branch_name": row.branch_name,
                "customer_count": int(row.customer_count),
                "customer_growth_yoy": yoy_rate(
                    row.customer_count, base_counts.get(row.branch_name)
                ),
                "male_share": share_percent(row.male_customer_count, row.customer_count),
                "average_age": _to_float(row.average_age),
                "recent_signup_share": share_percent(
                    row.recent_signup_customer_count, row.customer_count
                ),
                "recommendation_share": share_percent(
                    row.recommendation_consent_customer_count, row.customer_count
                ),
                "grade_s_share": share_percent(
                    row.grade_s_or_higher_customer_count, row.customer_count
                ),
            }
        )
    branch_rows = pd.DataFrame(rows, columns=list(TABLE_COLUMNS)).sort_values("branch_name")

    total_current = float(current["customer_count"].sum())
    total_base = float(sum(base_counts.values())) if base_counts else None
    total_row: dict[str, float | str | None] = {
        "branch_name": TOTAL_LABEL,
        "customer_count": int(total_current),
        "customer_growth_yoy": yoy_rate(total_current, total_base),
        "male_share": share_percent(current["male_customer_count"].sum(), total_current),
        "average_age": weighted_mean(current["average_age"], current["customer_count"]),
        "recent_signup_share": share_percent(
            current["recent_signup_customer_count"].sum(), total_current
        ),
        "recommendation_share": share_percent(
            current["recommendation_consent_customer_count"].sum(), total_current
        ),
        "grade_s_share": share_percent(
            current["grade_s_or_higher_customer_count"].sum(), total_current
        ),
    }
    return total_row, branch_rows.reset_index(drop=True)
