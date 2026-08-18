"""수익 탭의 계산.

데이터를 입력받아 그리기 좋은 형태로 정리만 한다. 파일을 직접 읽지 않는다.
어느 탭에서나 쓰는 계산 도구는 `dashboard.metrics`에 있다 — 산점도
(`growth_scatter`·`median_value`)는 거래 탭과 같은 것을 쓴다.

단위는 데이터 계층이 맞춰 둔 것을 그대로 쓴다. 수익은 **원**이고 비중은
이미 %다(→ dashboard/sources/revenue1.py).

수익 원본은 지점 × 월 × 수익 분류인 긴 형태다. 그래서 아래 함수들은
"어느 분류를 볼지"를 정해 걸러 낸 뒤 월별·지점별로 줄 세운다.

비중은 원본 값을 그대로 쓴다. 금액에서 되계산하지 않는다. 반올림 때문에
화면 숫자가 원본과 달라진다(→ AGENTS.md §9).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dashboard.metrics import (
    month_values,
    series_by_month,
    to_float,
    yoy_rate,
)

TREND_COLUMNS = ("base_month", "amount", "share")


def _source_for(
    frame: pd.DataFrame,
    total_frame: pd.DataFrame | None,
    scope: str,
    total_label: str,
) -> pd.DataFrame | None:
    """고른 구분의 행. 전체면 원본의 '전체' 행을 그대로 쓴다.

    비중은 더할 수 없어 지점에서 되만들면 원본과 달라진다. '전체' 행이
    없으면 None을 돌려주고 화면은 안내 상태가 된다(→ AGENTS.md §9).
    """
    if scope == total_label:
        return total_frame
    return frame[frame["branch_name"] == scope]


def revenue_trend(
    revenue: pd.DataFrame,
    revenue_total: pd.DataFrame | None,
    scope: str,
    total_label: str,
    revenue_type: str,
    amount_column: str,
    share_column: str,
) -> pd.DataFrame:
    """고른 구분의 월별 수익 금액과 공통고객 비중. base_month 오름차순.

    막대로 그릴 금액과 선으로 그릴 비중이 원본의 같은 행에 있다. 한 줄에
    함께 담아 그림이 두 번 걸러 내지 않게 한다.

    없는 달은 비운 채로 둔다. 0으로 채우면 '자료 없음'이 '0원으로
    측정됨'으로 바뀐다.
    """
    if revenue.empty:
        return pd.DataFrame(columns=list(TREND_COLUMNS))

    source = _source_for(revenue, revenue_total, scope, total_label)
    if source is None or source.empty:
        return pd.DataFrame(columns=list(TREND_COLUMNS))

    months = sorted(revenue["base_month"].unique())
    where = {"revenue_type": revenue_type}
    trend = pd.DataFrame({"base_month": months})
    for name, column in (
        ("amount", amount_column),
        ("share", share_column),
    ):
        values = series_by_month(source, where, column)
        trend[name] = [to_float(values.get(month)) for month in months]
    return trend


def revenue_mix(
    revenue: pd.DataFrame,
    revenue_total: pd.DataFrame | None,
    scopes: list[str],
    total_label: str,
    revenue_types: tuple[str, ...],
    base_month: str,
    share_column: str,
) -> pd.DataFrame:
    """구분마다 수익 구성 비중(%). 한 줄이 막대 하나, 열이 분류다.

    첫 구분은 항상 전체다. 전체 값은 원본의 '전체' 행을 그대로 쓴다.

    구분 이름을 키로 묶지 않는다. 두 칸에서 같은 지점을 고르면 막대가
    하나로 합쳐져 칸이 조용히 사라진다(→ figures.mix_figure).
    """
    columns = ["scope", *revenue_types]
    if revenue.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    for scope in scopes:
        source = _source_for(revenue, revenue_total, scope, total_label)
        row: dict = {"scope": scope}
        for revenue_type in revenue_types:
            row[revenue_type] = _share_of(
                source, revenue_type, base_month, share_column
            )
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def _share_of(
    source: pd.DataFrame | None,
    revenue_type: str,
    base_month: str,
    share_column: str,
) -> float | None:
    """한 구분·한 분류의 비중. 없으면 None."""
    if source is None or source.empty:
        return None
    values = series_by_month(
        source, {"revenue_type": revenue_type}, share_column
    )
    return to_float(values.get(base_month))


def revenue_mix_columns(
    revenue: pd.DataFrame,
    revenue_types: tuple[str, ...],
    base_month: str,
    share_column: str,
) -> dict[str, list[float | None]]:
    """지점마다 분류별 비중을 한 줄로 담는다.

    정적 HTML이 그래프의 한 자리만 갈아 끼울 때 쓴다. 조합마다 Figure를
    담으면 지점 수의 세제곱이 되므로 숫자만 담는다(→ export_html).
    """
    if revenue.empty:
        return {}
    rows = revenue[revenue["base_month"] == base_month]
    if rows.empty:
        return {}
    wide = rows.pivot_table(
        index="branch_name",
        columns="revenue_type",
        values=share_column,
        observed=True,
    )
    return {
        str(name): [
            to_float(wide.at[name, revenue_type])
            if revenue_type in wide.columns
            else None
            for revenue_type in revenue_types
        ]
        for name in wide.index
    }


# --- 지점별 표 --------------------------------------------------------------
def branch_table(
    revenue: pd.DataFrame,
    revenue_total: pd.DataFrame | None,
    amounts: tuple[tuple[str, str, str], ...],
    shares: tuple[tuple[str, str, str], ...],
    fields: tuple[str, ...],
    current_month: str,
    base_month: str,
    total_label: str,
) -> tuple[dict, pd.DataFrame]:
    """(전체 행, 지점별 행)을 반환한다.

    `amounts`는 금액과 전년 대비 증가율을 함께 만드는 묶음이고, `shares`는
    값 하나만 있는 비중이다. 각각 (필드 이름, 수익 분류, 표준 컬럼) 순이며
    어느 분류를 볼지는 탭이 정해서 넘긴다. 여기서는 그대로 돌면서 채우기만
    하므로 분류가 늘어도 이 함수는 그대로다.

    전체 행은 원본의 '전체' 지점 행을 그대로 쓴다. 비중은 더할 수 없고,
    금액도 지점에서 되만들면 원본과 달라질 수 있다(→ AGENTS.md §9).

    비교할 달의 값이 없으면 증가율을 0%로 채우지 않고 비운다. 0%는
    "변화 없음"으로 읽힌다(→ metrics.diff_rate).
    """
    rows: dict[str, dict] = {}
    total: dict = {field: None for field in fields}
    total["branch_name"] = total_label

    for field, revenue_type, column in amounts:
        where = {"revenue_type": revenue_type}
        now = month_values(revenue, where, current_month, column)
        past = month_values(revenue, where, base_month, column)
        for branch, value in now.items():
            record = rows.setdefault(branch, {})
            record[field] = value
            record[f"{field}_growth"] = yoy_rate(value, past.get(branch))
        given = month_values(revenue_total, where, current_month, column)
        given_past = month_values(revenue_total, where, base_month, column)
        for branch, value in given.items():
            total[field] = value
            total[f"{field}_growth"] = yoy_rate(
                value, given_past.get(branch)
            )

    for field, revenue_type, column in shares:
        where = {"revenue_type": revenue_type}
        now = month_values(revenue, where, current_month, column)
        for branch, value in now.items():
            rows.setdefault(branch, {})[field] = value
        given = month_values(revenue_total, where, current_month, column)
        for value in given.values():
            total[field] = value

    if not rows:
        return {}, pd.DataFrame(columns=list(fields))

    table = pd.DataFrame(
        [{"branch_name": name, **values} for name, values in rows.items()]
    )
    for field in fields:
        if field not in table.columns:
            table[field] = np.nan
    return (
        total,
        table.loc[:, list(fields)]
        .sort_values("branch_name")
        .reset_index(drop=True),
    )
