"""고객 탭의 집계와 계산.

전체 기준 값은 지점 비율의 단순 평균이 아니라 항상 분자·분모를 각각 합산해
계산한다. 같은 계산을 차트나 콜백에서 다시 구현하지 않는다.

분모가 0이거나 기준 월·지점 데이터가 없으면 예외를 던지지 않고 None을
돌려준다. 공통 계산 도구는 `dashboard.metrics`에 있다.
"""

from __future__ import annotations

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
from dashboard.metrics import (
    diff_abs,
    monthly_totals,
    resolve_current_month,
    row_for_month,
    share_percent,
    to_float,
    weighted_mean,
    yoy_rate,
)

TREND_COLUMNS = (
    "base_month",
    "total_count",
    "total_delta",
    "branch_count",
    "branch_delta",
    "branch_yoy",
)
SCATTER_COLUMNS = (
    "branch_name",
    "base_count",
    "current_count",
    "count_delta",
    "yoy",
)
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


# --- 고객 추이 ---------------------------------------------------------------
def customer_trend(
    monthly: pd.DataFrame,
    branch_name: str,
    monthly_total: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """전체 막대와 선택 지점 선그래프에 쓰는 월별 데이터."""
    if monthly.empty:
        return pd.DataFrame(columns=list(TREND_COLUMNS))

    totals = monthly_totals(monthly, monthly_total)[
        ["base_month", "customer_count"]
    ].rename(columns={"customer_count": "total_count"})
    branch = (
        monthly[monthly["branch_name"] == branch_name][
            ["base_month", "customer_count"]
        ]
        .rename(columns={"customer_count": "branch_count"})
        .sort_values("base_month")
    )
    trend = totals.merge(branch, on="base_month", how="left").sort_values(
        "base_month"
    )
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


# --- 고객 수 및 성장률 산점도
# -------------------------------------------------
def growth_scatter(
    monthly: pd.DataFrame,
    current_month: str | None = None,
    base_month: str | None = None,
    summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """지점별 고객 수와 YoY 증가율.

    증가율은 원본이 담아 둔 값(`summary.customer_growth_yoy`)을 우선 쓰고,
    없을 때만 monthly의 두 시점에서 계산한다. 테이블과 같은 숫자를 보여주기
    위해서다. 월을 지정하지 않으면 데이터의 최신 월과 그 12개월 전을 쓴다.
    """
    if monthly.empty:
        return pd.DataFrame(columns=list(SCATTER_COLUMNS))

    current_month = resolve_current_month(monthly, current_month)
    if current_month is None:
        return pd.DataFrame(columns=list(SCATTER_COLUMNS))
    if base_month is None:
        base_month = shift_month(current_month, -YOY_MONTHS)

    current = monthly[monthly["base_month"] == current_month][
        ["branch_name", "customer_count"]
    ]
    base = monthly[monthly["base_month"] == base_month][
        ["branch_name", "customer_count"]
    ]
    merged = current.merge(
        base, on="branch_name", how="left", suffixes=("_current", "_base")
    ).rename(
        columns={
            "customer_count_current": "current_count",
            "customer_count_base": "base_count",
        }
    )
    merged["count_delta"] = [
        diff_abs(row.current_count, row.base_count)
        for row in merged.itertuples()
    ]
    merged["yoy"] = [
        yoy_rate(row.current_count, row.base_count)
        for row in merged.itertuples()
    ]

    # 원본이 증가율을 담고 있으면 그 값으로 덮는다. 테이블과 같은 숫자를
    # 보여주기
    # 위해서다. 두 곳이 다른 방식으로 계산하면 같은 지점이 다르게 보인다.
    given = _given_growth(summary, current_month)
    if given is not None:
        replaced = merged["branch_name"].map(given)
        merged["yoy"] = replaced.where(replaced.notna(), merged["yoy"])

    return (
        merged.loc[:, list(SCATTER_COLUMNS)]
        .sort_values("branch_name")
        .reset_index(drop=True)
    )


def _given_growth(
    summary: pd.DataFrame | None, base_month: str
) -> pd.Series | None:
    """원본이 담아 둔 지점별 증가율. 없으면 None."""
    if (
        summary is None
        or summary.empty
        or "customer_growth_yoy" not in summary.columns
    ):
        return None
    rows = summary[summary["base_month"] == base_month]
    if rows.empty or rows["customer_growth_yoy"].isna().all():
        return None
    return rows.set_index("branch_name")["customer_growth_yoy"]


def median_customer_count(scatter: pd.DataFrame) -> float | None:
    """산점도 세로 기준선에 쓰는 고객 수 중앙값.

    이 선은 '고객 수 많음/적음'을 가르는 분할선이므로 평균이 아니라
    중앙값을 쓴다. 큰 지점 몇 곳이 평균을 끌어올리면 지점 대부분이
    '적음' 쪽에 몰려 사분면 문구가 사실과 달라진다. 중앙값은 정의상
    항상 절반으로 가른다.
    """
    if scatter.empty:
        return None
    values = pd.to_numeric(scatter["current_count"], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.median())


# --- 연령별 고객 분포
# ---------------------------------------------------------
def age_distribution(
    age: pd.DataFrame,
    branch_name: str,
    base_month: str | None = None,
    age_total: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """전체와 선택 지점의 연령 구간별 고객 수·비중.

    전체는 원본에 '전체' 행이 있으면(`age_total`) 그 값을 그대로 쓰고,
    없으면 구간별 고객 수 합계를 전체 고객 수로 나눈다.
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
    total_rows = (
        None
        if age_total is None
        else age_total[age_total["base_month"] == base_month]
    )
    if total_rows is not None and not total_rows.empty:
        frames.append(_age_frame(total_rows, TOTAL_LABEL))
    else:
        frames.append(_age_frame(month_data, TOTAL_LABEL))

    branch_data = month_data[month_data["branch_name"] == branch_name]
    if not branch_data.empty:
        frames.append(_age_frame(branch_data, branch_name))

    return pd.concat(frames, ignore_index=True)


def _age_frame(rows: pd.DataFrame, scope: str) -> pd.DataFrame:
    """구간별 고객 수와 비중. 원본이 비중을 담고 있으면 그 값을 그대로 쓴다."""
    counts = (
        rows.groupby("age_group", observed=True)["customer_count"]
        .sum()
        .reindex(list(AGE_GROUPS), fill_value=0)
    )
    total = float(counts.sum())
    shares = [share_percent(value, total) for value in counts.to_numpy()]
    # 원본의 비중은 지점 하나를 기준으로 계산된 값이다. 여러 지점을 묶을 때는
    # 쓸 수 없으므로(비중끼리 더하거나 고를 수 없다) 인원수에서 다시 계산한다.
    if "share" in rows.columns and rows["branch_id"].nunique() == 1:
        given = rows.set_index("age_group")["share"].reindex(list(AGE_GROUPS))
        if given.notna().all():
            shares = [float(value) for value in given.to_numpy()]
    return pd.DataFrame(
        {
            "age_group": list(AGE_GROUPS),
            "scope": scope,
            "customer_count": counts.to_numpy(dtype=int),
            "share": shares,
        }
    )


# --- 투자성향 ----------------------------------------------------------------
def investment_breakdown(
    investment: pd.DataFrame,
    scope: str = TOTAL_LABEL,
    base_month: str | None = None,
    investment_total: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """투자성향별 마케팅 동의·불원 구성. 성향 순서는 고정한다.

    전체는 원본에 '전체' 행이 있으면(`investment_total`) 그 값을 그대로 쓰고,
    없으면 지점을 합산한다. 월을 지정하지 않으면 데이터의 최신 월을 쓴다.
    """
    if investment.empty:
        return pd.DataFrame(columns=list(INVESTMENT_COLUMNS))

    base_month = resolve_current_month(investment, base_month)
    if base_month is None:
        return pd.DataFrame(columns=list(INVESTMENT_COLUMNS))

    source = investment
    if (
        scope == TOTAL_LABEL
        and investment_total is not None
        and not investment_total.empty
    ):
        source = investment_total
    month_data = source[source["base_month"] == base_month]
    if scope != TOTAL_LABEL:
        month_data = month_data[month_data["branch_name"] == scope]
    if month_data.empty:
        return pd.DataFrame(columns=list(INVESTMENT_COLUMNS))

    grouped = (
        month_data.groupby(
            ["investment_type", "marketing_consent"], observed=True
        )["customer_count"]
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
        for label, series in (
            (CONSENT_LABEL, consent),
            (NON_CONSENT_LABEL, non_consent),
        ):
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


# --- 지점별 고객 현황 테이블
# --------------------------------------------------
def branch_table(
    monthly: pd.DataFrame,
    summary: pd.DataFrame,
    current_month: str | None = None,
    base_month: str | None = None,
    summary_total: pd.DataFrame | None = None,
) -> tuple[dict[str, float | str | None], pd.DataFrame]:
    """(전체 행, 지점별 행)을 반환한다.

    지점 비율은 데이터 계층이 넘겨준 값을 그대로 쓴다. 원본이 비율로
    주면 그 값이, 인원수로 주면 인원수에서 만든 값이 들어 있다
    (→ dashboard.data).

    전체 행은 원본에 '전체' 행이 있으면(`summary_total`) 그 값을 그대로 쓴다.
    없으면 지점 값에서 계산한다 — 비율은 고객 수로 가중평균하고, 단순 평균은
    쓰지 않는다.

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
        # 증가율은 원본이 주면 그 값을 쓴다. 없으면 monthly의 두 시점에서
        # 계산한다.
        growth = to_float(getattr(row, "customer_growth_yoy", None))
        if growth is None:
            growth = yoy_rate(
                row.customer_count, base_counts.get(row.branch_name)
            )
        rows.append(
            {
                "branch_name": row.branch_name,
                "customer_count": int(row.customer_count),
                "customer_growth_yoy": growth,
                "male_share": to_float(row.male_share),
                "average_age": to_float(row.average_age),
                "recent_signup_share": to_float(row.recent_signup_share),
                "recommendation_share": to_float(row.recommendation_share),
                "grade_s_share": to_float(row.grade_s_share),
            }
        )
    branch_rows = pd.DataFrame(rows, columns=list(TABLE_COLUMNS)).sort_values(
        "branch_name"
    )

    given_total = (
        row_for_month(summary_total, current_month)
        if summary_total is not None
        else None
    )
    if given_total is not None:
        total_row = _total_row_from_source(given_total)
    else:
        total_current = float(current["customer_count"].sum())
        total_base = float(sum(base_counts.values())) if base_counts else None
        weights = current["customer_count"]
        total_row = {
            "branch_name": TOTAL_LABEL,
            "customer_count": int(total_current),
            "customer_growth_yoy": yoy_rate(total_current, total_base),
            "male_share": weighted_mean(current["male_share"], weights),
            "average_age": weighted_mean(current["average_age"], weights),
            "recent_signup_share": weighted_mean(
                current["recent_signup_share"], weights
            ),
            "recommendation_share": weighted_mean(
                current["recommendation_share"], weights
            ),
            "grade_s_share": weighted_mean(current["grade_s_share"], weights),
        }
    return total_row, branch_rows.reset_index(drop=True)


def _total_row_from_source(row: pd.Series) -> dict[str, float | str | None]:
    """원본의 '전체' 행을 화면 표시용 값으로 옮긴다.

    값을 다시 계산하지 않는다.
    """
    count = to_float(row["customer_count"])
    total_row: dict[str, float | str | None] = {
        "branch_name": TOTAL_LABEL,
        "customer_count": None if count is None else int(count),
    }
    for column in TABLE_COLUMNS:
        if column in ("branch_name", "customer_count"):
            continue
        total_row[column] = (
            to_float(row[column]) if column in row.index else None
        )
    return total_row
