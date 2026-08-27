"""거래 탭의 계산.

데이터를 입력받아 그리기 좋은 형태로 정리만 한다. 파일을 직접 읽지 않는다.
어느 탭에서나 쓰는 계산 도구는 `dashboard.metrics`에 있다.

단위는 데이터 계층이 맞춰 둔 것을 그대로 쓴다. 거래금액·입출금은 억원,
거래고객수는 명이다(→ dashboard/sources/transaction1.py).

세 원본 모두 지점 × 월에 분류축이 하나 이상 더 붙는 긴 형태다. 그래서
아래 함수들은 "어느 분류를 볼지"를 `where`로 받아 걸러 낸 뒤 월별로
줄 세운다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dashboard.metrics import (
    fill_deltas,
    growth_scatter,
    median_value,
    month_values,
    series_by_month,
    to_float,
    yoy_rate,
)

# 분류축이 있는 긴 프레임을 다루는 도구(`series_by_month`·`month_values`·
# `growth_scatter`·`median_value`)는 수익 탭도 쓰므로 `dashboard.metrics`에
# 둔다. 여기서 다시 만들면 같은 계산이 두 곳으로 갈라진다.

TREND_COLUMNS = (
    "base_month",
    "total_value",
    "branch_value",
    "total_delta",
    "branch_delta",
)


def measure_trend(
    frame: pd.DataFrame,
    total_frame: pd.DataFrame | None,
    branch_name: str,
    column: str,
    where: dict | None = None,
) -> pd.DataFrame:
    """월별 전체 값과 선택 지점 값. base_month 오름차순.

    전체는 원본의 '전체' 행을 그대로 쓴다. 거래고객수는 한 고객이 여러
    상품을 거래하면 상품별 합보다 작아, 지점에서 되만들면 원본과 달라진다.
    '전체' 행이 없으면 비운 채로 둔다(→ AGENTS.md §9).
    """
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=list(TREND_COLUMNS))

    where = where or {}
    months = sorted(frame["base_month"].unique())
    totals = series_by_month(total_frame, where, column)
    branch = series_by_month(
        frame, {**where, "branch_name": branch_name}, column
    )

    trend = pd.DataFrame({"base_month": months})
    trend["total_value"] = [to_float(totals.get(month)) for month in months]
    trend["branch_value"] = [to_float(branch.get(month)) for month in months]
    fill_deltas(trend)
    return trend


# --- 입출금 -----------------------------------------------------------------
CASH_FLOW_COLUMNS = ("base_month", "net_total", "net_securities", "net_bank")


def cash_flow_trend(
    cash_flow: pd.DataFrame,
    cash_flow_total: pd.DataFrame | None,
    scope: str,
    total_label: str,
    channels: tuple[str, str],
    channel_total: str,
) -> pd.DataFrame:
    """고른 구분의 월별 순입금. base_month 오름차순.

    막대로 그릴 전체 채널과 선으로 그릴 두 채널을 한 줄에 담는다. 채널
    이름은 데이터 계층의 상수에서 받는다. 여기 적어 두면 원본의 채널이
    늘었을 때 두 곳을 고쳐야 한다(→ data.CASH_FLOW_CHANNELS).
    """
    if cash_flow.empty:
        return pd.DataFrame(columns=list(CASH_FLOW_COLUMNS))

    source = (
        cash_flow_total
        if scope == total_label
        else cash_flow[cash_flow["branch_name"] == scope]
    )
    if source is None or source.empty:
        return pd.DataFrame(columns=list(CASH_FLOW_COLUMNS))

    months = sorted(cash_flow["base_month"].unique())
    securities, bank = channels
    trend = pd.DataFrame({"base_month": months})
    for name, channel in (
        ("net_total", channel_total),
        ("net_securities", securities),
        ("net_bank", bank),
    ):
        values = series_by_month(source, {"channel": channel}, "net_amount")
        trend[name] = [to_float(values.get(month)) for month in months]
    return trend


# --- 연금 거래 현황 분석 -----------------------------------------------------
def pension_mix_trend(
    pension_transaction: pd.DataFrame,
    pension_transaction_total: pd.DataFrame | None,
    scope: str,
    total_label: str,
    pension_type: str,
    products: tuple[str, ...],
    column: str,
) -> pd.DataFrame:
    """고른 구분·연금의 월별 상품 값. 열 하나가 쌓을 상품 하나다.

    원본에 없는 상품은 빈 열로 남긴다. 0으로 채우면 "없음"이 "0으로
    측정됨"으로 바뀐다. 거래고객수는 '기타'에 원본 값이 없어 그 열이
    통째로 빈다(→ dashboard/sources/transaction2.py).
    """
    columns = ["base_month", *products]
    if pension_transaction.empty or column not in pension_transaction.columns:
        return pd.DataFrame(columns=columns)

    source = (
        pension_transaction_total
        if scope == total_label
        else pension_transaction[
            pension_transaction["branch_name"] == scope
        ]
    )
    if source is None or source.empty:
        return pd.DataFrame(columns=columns)

    months = sorted(pension_transaction["base_month"].unique())
    mix = pd.DataFrame({"base_month": months})
    for product in products:
        values = series_by_month(
            source,
            {"pension_type": pension_type, "product_type": product},
            column,
        )
        mix[product] = [to_float(values.get(month)) for month in months]
    return mix


# --- 지점별 표 --------------------------------------------------------------
# 거래 묶음 하나가 만드는 컬럼. (필드 뒷말, 표준 컬럼)
# 증가율은 뒷말에 `_growth`를 더해 만든다.
TRADE_TABLE_FIELDS = (
    ("customer_count", "trade_customer_count"),
    ("amount", "trade_amount"),
)


def branch_table(
    groups: tuple[tuple[str, pd.DataFrame, pd.DataFrame | None, dict], ...],
    flows: tuple[tuple[str, pd.DataFrame, pd.DataFrame | None, dict], ...],
    fields: tuple[str, ...],
    current_month: str,
    base_month: str,
    total_label: str,
) -> tuple[dict, pd.DataFrame]:
    """(전체 행, 지점별 행)을 반환한다.

    `groups`는 거래고객수·거래금액과 각각의 전년 대비 증가율을 만드는
    묶음이고, `flows`는 값 하나만 있는 순입금이다. 어느 프레임의 어느
    분류를 볼지는 탭이 정해서 넘긴다. 여기서는 그대로 돌면서 채우기만
    하므로, 상품이나 연금이 늘어도 이 함수는 그대로다.

    전체 행은 원본의 '전체' 지점 행을 그대로 쓴다. 거래고객수는 지점에서
    더할 수 없다 — 한 고객이 두 지점에서 거래하면 두 번 세어진다.

    비교할 달의 값이 없으면 증가율을 0%로 채우지 않고 비운다. 0%는
    "변화 없음"으로 읽힌다(→ metrics.diff_rate).
    """
    rows: dict[str, dict] = {}
    total: dict = {field: None for field in fields}
    total["branch_name"] = total_label

    for prefix, frame, total_frame, where in groups:
        for name, column in TRADE_TABLE_FIELDS:
            now = month_values(frame, where, current_month, column)
            past = month_values(frame, where, base_month, column)
            for branch, value in now.items():
                record = rows.setdefault(branch, {})
                record[f"{prefix}_{name}"] = value
                record[f"{prefix}_{name}_growth"] = yoy_rate(
                    value, past.get(branch)
                )
            given = month_values(
                total_frame, where, current_month, column
            )
            given_past = month_values(
                total_frame, where, base_month, column
            )
            for branch, value in given.items():
                total[f"{prefix}_{name}"] = value
                total[f"{prefix}_{name}_growth"] = yoy_rate(
                    value, given_past.get(branch)
                )

    for field, frame, total_frame, where in flows:
        now = month_values(frame, where, current_month, "net_amount")
        for branch, value in now.items():
            rows.setdefault(branch, {})[field] = value
        given = month_values(
            total_frame, where, current_month, "net_amount"
        )
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
