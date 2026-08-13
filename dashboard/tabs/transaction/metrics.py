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

from dashboard.metrics import fill_deltas, to_float, yoy_rate

TREND_COLUMNS = (
    "base_month",
    "total_value",
    "branch_value",
    "total_delta",
    "branch_delta",
)


def _matching(frame: pd.DataFrame, where: dict) -> pd.DataFrame:
    """분류값으로 걸러 낸다. 없는 컬럼을 넘기면 빈 프레임이 된다."""
    rows = frame
    for column, value in where.items():
        if column not in rows.columns:
            return rows.iloc[0:0]
        rows = rows[rows[column] == value]
    return rows


def _by_month(
    frame: pd.DataFrame | None, where: dict, column: str
) -> pd.Series:
    """걸러 낸 행을 기준 월로 찾을 수 있게 만든다."""
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    rows = _matching(frame, where)
    if rows.empty:
        return pd.Series(dtype=float)
    return rows.set_index("base_month")[column]


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
    totals = _by_month(total_frame, where, column)
    branch = _by_month(frame, {**where, "branch_name": branch_name}, column)

    trend = pd.DataFrame({"base_month": months})
    trend["total_value"] = [to_float(totals.get(month)) for month in months]
    trend["branch_value"] = [to_float(branch.get(month)) for month in months]
    fill_deltas(trend)
    return trend


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
    (→ metrics.diff_rate).
    """
    columns = ["branch_name", "value", "growth"]
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=columns)

    rows = _matching(frame, where or {})
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
        values = _by_month(source, {"channel": channel}, "net_amount")
        trend[name] = [to_float(values.get(month)) for month in months]
    return trend


# --- 연금 거래 구성 ----------------------------------------------------------
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
        values = _by_month(
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


def _month_values(
    frame: pd.DataFrame | None, where: dict, month: str, column: str
) -> dict[str, float | None]:
    """그 달의 지점별 값. {지점명: 값}.

    분류축이 있는 프레임에서 한 묶음만 뽑아 지점 이름으로 찾을 수 있게
    만든다. 없는 지점은 아예 담기지 않으므로 표에서 빈 칸이 된다.
    """
    if frame is None or frame.empty or column not in frame.columns:
        return {}
    rows = _matching(frame, {**where, "base_month": month})
    if rows.empty:
        return {}
    return {
        str(name): to_float(value)
        for name, value in zip(rows["branch_name"], rows[column])
    }


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
            now = _month_values(frame, where, current_month, column)
            past = _month_values(frame, where, base_month, column)
            for branch, value in now.items():
                record = rows.setdefault(branch, {})
                record[f"{prefix}_{name}"] = value
                record[f"{prefix}_{name}_growth"] = yoy_rate(
                    value, past.get(branch)
                )
            given = _month_values(
                total_frame, where, current_month, column
            )
            given_past = _month_values(
                total_frame, where, base_month, column
            )
            for branch, value in given.items():
                total[f"{prefix}_{name}"] = value
                total[f"{prefix}_{name}_growth"] = yoy_rate(
                    value, given_past.get(branch)
                )

    for field, frame, total_frame, where in flows:
        now = _month_values(frame, where, current_month, "net_amount")
        for branch, value in now.items():
            rows.setdefault(branch, {})[field] = value
        given = _month_values(
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
