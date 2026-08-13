"""자산 탭의 계산.

데이터를 입력받아 그리기 좋은 형태로 정리만 한다. 파일을 직접 읽지 않는다.
어느 탭에서나 쓰는 계산 도구는 `dashboard.metrics`에 있다.

단위는 데이터 계층이 맞춰 둔 것을 그대로 쓴다. 순자산·연금 자산은 억원,
1인 평균 자산은 백만원, 비중과 증감율은 %다(→ dashboard/sources).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import TOTAL_LABEL
from dashboard.metrics import diff_abs, to_float


def _rows_for(frame: pd.DataFrame, branch_name: str) -> pd.DataFrame:
    return frame[frame["branch_name"] == branch_name]


# --- 1. 자산 추이 ------------------------------------------------------------
def asset_trend(
    monthly: pd.DataFrame,
    branch_name: str,
    column: str,
    monthly_total: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """월별 전체 값과 선택 지점 값. base_month 오름차순.

    전체는 원본의 '전체' 행을 그대로 쓴다. 1인 평균 자산은 더할 수 없어
    지점에서 되만들 수 없으므로, '전체' 행이 없으면 비운 채로 둔다.
    """
    if monthly.empty or column not in monthly.columns:
        return pd.DataFrame(
            columns=[
                "base_month",
                "total_value",
                "branch_value",
                "total_delta",
                "branch_delta",
            ]
        )

    months = sorted(monthly["base_month"].unique())
    if monthly_total is not None and not monthly_total.empty:
        totals = monthly_total.set_index("base_month")[column]
    else:
        totals = pd.Series(dtype=float)
    branch = _rows_for(monthly, branch_name).set_index("base_month")[column]

    trend = pd.DataFrame({"base_month": months})
    trend["total_value"] = [
        to_float(totals.get(month)) for month in months
    ]
    trend["branch_value"] = [
        to_float(branch.get(month)) for month in months
    ]
    _fill_deltas(trend)
    return trend


def _fill_deltas(trend: pd.DataFrame) -> None:
    """`<구분>_value`에서 전월 대비 증감을 만들어 `<구분>_delta`에 채운다.

    값을 바꾸면 증감도 다시 만들어야 하므로 한 곳에 둔다.
    """
    for name in ("total", "branch"):
        values = trend[f"{name}_value"]
        trend[f"{name}_delta"] = [
            diff_abs(values.iloc[index], values.iloc[index - 1])
            if index > 0
            else None
            for index in range(len(values))
        ]


# --- 2. 자산 규모와 증가율 ---------------------------------------------------
def asset_growth_scatter(summary: pd.DataFrame) -> pd.DataFrame:
    """지점별 순자산(억원)과 순자산 증가율(%).

    두 값 모두 자산2 원본이 담고 있는 값을 그대로 쓴다. 증가율을 순자산
    시작·종료에서 다시 계산하면 원본과 소수점이 어긋난다.
    """
    columns = ("net_assets_start", "net_assets_end", "net_assets_growth")
    if summary.empty or any(
        column not in summary.columns for column in columns
    ):
        return pd.DataFrame(columns=["branch_name", *columns])
    scatter = summary.loc[:, ["branch_name", *columns]].copy()
    return scatter.dropna(subset=["net_assets_end", "net_assets_growth"])


def median_net_assets(scatter: pd.DataFrame) -> float | None:
    if scatter.empty or "net_assets_end" not in scatter.columns:
        return None
    values = pd.to_numeric(
        scatter["net_assets_end"], errors="coerce"
    ).dropna()
    return float(values.median()) if not values.empty else None


# --- 3. 자산 구성 ------------------------------------------------------------
def asset_mix(
    summary: pd.DataFrame,
    scopes: list[str],
    share_columns: tuple[str, ...],
    summary_total: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """구분마다 자산 구성 비중(%). 한 줄이 막대 하나, 열이 상품이다.

    첫 구분은 항상 전체다. 전체 값은 원본의 '전체' 행을 그대로 쓴다.
    비중은 더할 수 없어 지점에서 되만들면 원본과 달라진다.

    구분 이름을 키로 묶지 않는다. 두 칸에서 같은 지점을 고르면 막대가
    하나로 합쳐져 칸이 조용히 사라진다.
    """
    columns = ["scope", *share_columns]
    if summary.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    for scope in scopes:
        if scope == TOTAL_LABEL:
            source = (
                summary_total
                if summary_total is not None and not summary_total.empty
                else summary.iloc[0:0]
            )
        else:
            source = _rows_for(summary, scope)
        row = {"scope": scope}
        for column in share_columns:
            row[column] = (
                to_float(source.iloc[0][column])
                if not source.empty
                else None
            )
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def asset_mix_columns(
    summary: pd.DataFrame, share_columns: tuple[str, ...]
) -> dict[str, list[float | None]]:
    """지점마다 상품 비중을 한 줄로 담는다.

    정적 HTML이 그래프의 한 자리만 갈아 끼울 때 쓴다. 조합마다 Figure를
    담으면 지점 수의 세제곱이 되므로 숫자만 담는다(→ export_html).
    """
    if summary.empty:
        return {}
    return {
        str(row.branch_name): [
            to_float(getattr(row, column)) for column in share_columns
        ]
        for row in summary.itertuples()
    }


# --- 4. 상품 비중 비교 -------------------------------------------------------
def mix_scatter(
    summary: pd.DataFrame, x_column: str, y_column: str
) -> pd.DataFrame:
    """지점마다 두 상품의 비중(%)을 짝지어 준다."""
    columns = {"branch_name", x_column, y_column}
    if summary.empty or not columns <= set(summary.columns):
        return pd.DataFrame(columns=["branch_name", "x", "y"])
    scatter = pd.DataFrame(
        {
            "branch_name": summary["branch_name"],
            "x": pd.to_numeric(summary[x_column], errors="coerce"),
            "y": pd.to_numeric(summary[y_column], errors="coerce"),
        }
    )
    return scatter.dropna(subset=["x", "y"]).reset_index(drop=True)


# --- 5. 상품 구성별 증감 -----------------------------------------------------
def change_matrix(
    asset_change: pd.DataFrame,
    scope: str,
    asset_types: tuple[str, ...],
    asset_change_total: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """행이 상품, 열이 기준 월인 증감율(%) 표.

    상품 순서는 `data.ALL_ASSET_TYPES`가 정한다. 원본에 없는 분류는 빈 줄로
    남겨 어느 상품이 빠졌는지 화면에서 보이게 한다.
    """
    source = (
        asset_change_total
        if scope == TOTAL_LABEL
        else _rows_for(asset_change, scope)
    )
    if source is None or source.empty:
        return pd.DataFrame()
    matrix = source.pivot_table(
        index="asset_type",
        columns="base_month",
        values="change_rate",
        observed=True,
    )
    return matrix.reindex(list(asset_types))


# --- 6. 연금 추이 ------------------------------------------------------------
# 억원을 백만원으로 바꾸는 배수. 1인 평균은 표의 '1인 평균' 컬럼과 같은
# 백만원 단위로 적는다(→ format.format_million_won).
_100M_TO_1M = 100


def pension_trend(
    monthly: pd.DataFrame,
    branch_name: str,
    assets_column: str,
    count_column: str,
    monthly_total: pd.DataFrame | None = None,
    per_customer: bool = False,
) -> pd.DataFrame:
    """월별 연금 자산과 가입 고객 수. base_month 오름차순.

    자산은 `asset_trend`와 같은 규칙으로 전체·지점을 나란히 담는다. 가입
    고객 수를 함께 붙여, 값이 움직인 것이 가입자가 늘어서인지 1인당
    금액이 커져서인지 hover에서 바로 견줄 수 있게 한다.

    `per_customer`를 켜면 자산 자리에 가입 고객 1인 평균(백만원)을 담는다.
    자산4가 1인 평균을 담고 있지 않아 여기서 나눈다. 자산4의 자산이 정수
    억원이라, 원 단위 값을 그대로 받는 표의 '1인 평균'(자산2)과 만원
    자리가 어긋날 수 있다.
    """
    trend = asset_trend(monthly, branch_name, assets_column, monthly_total)
    if trend.empty:
        return trend
    counts = asset_trend(monthly, branch_name, count_column, monthly_total)
    for scope in ("total", "branch"):
        trend[f"{scope}_count"] = (
            None if counts.empty else counts[f"{scope}_value"]
        )
    if per_customer:
        for scope in ("total", "branch"):
            trend[f"{scope}_value"] = [
                _per_customer(value, count)
                for value, count in zip(
                    trend[f"{scope}_value"], trend[f"{scope}_count"]
                )
            ]
        # 값을 바꿨으므로 증감도 평균 기준으로 다시 만든다.
        _fill_deltas(trend)
    return trend


def _per_customer(
    assets: object, count: object
) -> float | None:
    """자산(억원)을 가입 고객 1인 평균(백만원)으로 바꾼다.

    가입자가 없으면 평균도 없다. 0으로 채우면 '가입자 없음'이 '평균 0원'
    으로 보인다(→ AGENTS.md §9).
    """
    if assets is None or count is None:
        return None
    if pd.isna(assets) or pd.isna(count) or float(count) == 0:
        return None
    return float(assets) * _100M_TO_1M / float(count)


# --- 지점별 표 --------------------------------------------------------------
# 월별 파일에서 가져오는 값. 상단 카드·추이 그래프와 같은 값을 쓴다.
MONTHLY_COLUMNS = ("customer_count", "net_assets", "average_assets")


def branch_table(
    monthly: pd.DataFrame,
    summary: pd.DataFrame,
    table_columns: tuple[str, ...],
    current_month: str | None = None,
    monthly_total: pd.DataFrame | None = None,
    summary_total: pd.DataFrame | None = None,
) -> tuple[dict, pd.DataFrame]:
    """(전체 행, 지점별 행)을 반환한다.

    고객 수·순자산·고객 평균 자산은 월별 파일의 기준 월 값을 쓴다. 상단
    카드와 추이 그래프가 그 값을 쓰므로, 표만 다른 원본을 보면 같은 화면
    안에서 숫자가 어긋난다.

    나머지(증가율·구성 비중·연금)는 지점 한 시점 원본에만 있다.

    전체 행은 원본의 '전체' 행을 그대로 쓴다. 비중과 1인 평균은 더할 수
    없어 지점에서 되만들면 원본과 달라진다. 원본에 '전체' 행이 없으면
    그 값은 비운다.
    """
    empty = pd.DataFrame(columns=list(table_columns))
    if summary.empty or monthly.empty:
        return {}, empty

    if not current_month:
        months = sorted(monthly["base_month"].unique())
        current_month = months[-1] if months else ""
    month_rows = monthly[monthly["base_month"] == current_month]
    if month_rows.empty:
        return {}, empty

    by_branch = {
        column: month_rows.set_index("branch_name")[column].to_dict()
        for column in MONTHLY_COLUMNS
        if column in month_rows.columns
    }

    rows = []
    for row in summary.itertuples():
        name = str(row.branch_name)
        record: dict = {"branch_name": name}
        for column in table_columns:
            if column == "branch_name":
                continue
            if column in by_branch:
                record[column] = to_float(by_branch[column].get(name))
            else:
                record[column] = to_float(getattr(row, column, None))
        rows.append(record)
    branch_rows = pd.DataFrame(rows, columns=list(table_columns)).sort_values(
        "branch_name"
    )

    return (
        _total_row(
            table_columns, current_month, monthly_total, summary_total
        ),
        branch_rows.reset_index(drop=True),
    )


def _total_row(
    table_columns: tuple[str, ...],
    current_month: str,
    monthly_total: pd.DataFrame | None,
    summary_total: pd.DataFrame | None,
) -> dict:
    """원본의 '전체' 행을 표 한 줄로 옮긴다. 값을 다시 계산하지 않는다."""
    month_row = None
    if monthly_total is not None and not monthly_total.empty:
        matched = monthly_total[
            monthly_total["base_month"] == current_month
        ]
        month_row = None if matched.empty else matched.iloc[0]
    profile_row = (
        None
        if summary_total is None or summary_total.empty
        else summary_total.iloc[0]
    )

    total: dict = {"branch_name": TOTAL_LABEL}
    for column in table_columns:
        if column == "branch_name":
            continue
        source = month_row if column in MONTHLY_COLUMNS else profile_row
        total[column] = (
            to_float(source[column])
            if source is not None and column in source.index
            else None
        )
    return total


