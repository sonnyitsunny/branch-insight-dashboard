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

from dashboard.data import (
    AI_SUMMARY_COLUMN,
    AI_SUMMARY_LINE_BREAK,
    TOTAL_LABEL,
    shift_month,
)


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
    # 고객 1인당 수익(원). 두 값 다 이 프레임에 있으므로 여기서 만든다.
    # 달마다 분모가 달라지므로 전월 값도 그 달의 고객 수로 나눈 값이어야
    # 한다. 한 달의 평균을 다른 달 고객 수로 나누면 뜻이 없다.
    totals["average_revenue"] = [
        safe_ratio(row.common_revenue, row.customer_count)
        for row in totals.itertuples()
    ]
    return totals


# --- AI 요약 -----------------------------------------------------------------
# 원본이 줄머리에 달고 오는 기호. 화면은 CSS로 점을 찍으므로 여기서 뗀다.
# 떼지 않으면 '• - 지점 01은…'처럼 표시가 두 개 붙는다. 원본이 기호 없이
# 오면 아무것도 떼지 않는다.
LINE_MARKERS = ("- ", "· ", "• ", "* ")

# 묶음의 머리줄을 가리는 기호. 원본이 상품 묶음마다 이 기호로 시작하는 줄
# 하나를 넣고 그 아래에 항목을 단다(→ dashboard/sources/product_ai.py).
# 이 기호는 떼지 않는다 — 떼면 어느 줄이 머리인지 화면이 알 수 없다.
# 어느 탭의 글에서나 같은 규칙이라 여기 한 번만 적는다.
SECTION_MARKER = "■"


def ai_summary_lines(
    ai_summary: pd.DataFrame,
    topic: str,
    scope: str = TOTAL_LABEL,
    base_month: str | None = None,
    ai_summary_total: pd.DataFrame | None = None,
) -> list[str]:
    """그 탭·그 이름의 AI 요약을 한 줄씩 나눠 돌려준다.

    프레임 하나에 탭별 글이 모여 있으므로 `topic`으로 먼저 가른다
    (→ data.AI_TOPICS). 원본은 여러 줄을 한 덩이로 담고 있고, 화면과
    정적 HTML이 같은 줄을 보도록 나누는 일을 여기서 한 번만 한다.

    원본이 없거나 그 지점의 값이 비어 있으면 빈 목록을 돌려준다. 그때
    화면에는 왜 비었는지 알리는 문구가 나타난다(→ registry.Insight).
    어느 탭에서나 쓰는 계산이라 탭 모듈이 아니라 여기 둔다.
    """
    if ai_summary.empty or AI_SUMMARY_COLUMN not in ai_summary.columns:
        return []

    base_month = resolve_current_month(ai_summary, base_month)
    if base_month is None:
        return []

    source = ai_summary
    if (
        scope == TOTAL_LABEL
        and ai_summary_total is not None
        and not ai_summary_total.empty
    ):
        source = ai_summary_total
    rows = source[
        (source["base_month"] == base_month) & (source["topic"] == topic)
    ]
    if scope != TOTAL_LABEL:
        rows = rows[rows["branch_name"] == scope]
    if rows.empty:
        return []

    text = rows.iloc[0][AI_SUMMARY_COLUMN]
    if not isinstance(text, str):
        return []
    return [
        stripped
        for line in text.split(AI_SUMMARY_LINE_BREAK)
        if (stripped := _without_marker(line))
    ]


def is_section(line: str) -> bool:
    """묶음의 머리줄인지(→ SECTION_MARKER).

    화면과 정적 HTML이 같은 규칙으로 가리도록 여기 한 번만 적는다
    (→ layout.insight_line_class, export_html).
    """
    return line.startswith(SECTION_MARKER)


def insight_groups(lines: list[str]) -> list[list[str]]:
    """요약 줄을 묶음 단위로 나눈다.

    머리줄(→ SECTION_MARKER)마다 새 묶음이 시작된다. 머리줄이 없는 글은
    통째로 한 묶음이다. 카드 레이아웃이 묶음 하나를 상자 하나로 다루므로
    (→ insight_columns) 나누는 규칙을 여기 한 번만 적는다.
    """
    groups: list[list[str]] = []
    for line in lines:
        if is_section(line) or not groups:
            groups.append([line])
        else:
            groups[-1].append(line)
    return groups


def insight_columns(lines: list[str]) -> list[list[list[str]]]:
    """요약 줄을 카드 안에서 나눠 놓을 칸으로 접는다.

    묶음이 둘 이상이면 한 칸에 세로로 길게 늘어놓는 대신 좌우 두 칸으로
    나눈다. 앞쪽 절반이 왼쪽, 나머지가 오른쪽이다 — 묶음 넷이면 왼쪽에
    둘, 오른쪽에 둘이 놓인다. 묶음을 가운데서 자르지 않으므로 머리줄과 그
    아래 항목이 갈라지지 않는다.

    **칸은 줄을 평평하게 이어 붙이지 않는다.** 칸은 묶음의 목록이고 묶음은
    줄의 목록이다 — 묶음마다 화면이 독립된 상자를 그리게 한다. 앞 묶음의
    길이가 칸마다 다르면(예: 국내주식이 해외주식보다 줄이 많으면), 옆
    칸의 같은 순번 묶음(해외주식과 국내ETF·펀드)이 서로 다른 높이에서
    시작해 제목이 어긋난다. 상자로 나누고 CSS 그리드에 맡기면 같은 순번의
    상자끼리 자동으로 키를 맞춰 그 어긋남이 생기지 않는다
    (→ layout.insight_lines, export_html._insight_lines,
    assets/style.css의 .insight-columns).

    묶음이 없거나 하나뿐인 탭은 한 칸 그대로다. 그런 글은 줄이 몇 개뿐이라
    나누면 오히려 읽는 자리가 흩어진다.

    화면과 정적 HTML이 같은 자리에서 나누도록 규칙을 여기 한 번만 적는다.
    """
    groups = insight_groups(lines)
    if len(groups) < 2:
        return [groups]
    half = (len(groups) + 1) // 2
    return [groups[:half], groups[half:]]


def insight_column_rows(columns: list[list[list[str]]]) -> int:
    """좌우로 나뉜 칸 가운데 더 긴 칸의 묶음 수.

    칸마다 묶음을 세로로 쌓다가 이 수에서 다음 칸으로 넘어간다
    (→ insight_columns). 묶음 수가 데이터마다 달라 CSS에 고정 값을 적어
    둘 수 없고, 화면과 정적 HTML이 그릴 때마다 이 값으로 그리드 행 수를
    정한다(→ layout.insight_columns_style,
    export_html._insight_columns_style).
    """
    return max(len(column) for column in columns)


def _without_marker(line: str) -> str:
    """줄머리 기호를 뗀 글. 기호가 없으면 앞뒤 공백만 덜어 낸다."""
    text = line.strip()
    for marker in LINE_MARKERS:
        if text.startswith(marker):
            return text[len(marker):].strip()
    return text


# 투자수익률 카드가 쓰는 기간과 그 표준 컬럼. 원본이 기간마다 컬럼을 따로
# 담고 있어 하나를 고른다(→ dashboard/sources/branch_return.py). 카드 이름에
# 기간을 적으므로 이름과 컬럼을 여기 함께 두어 둘이 어긋나지 않게 한다
# (→ layout.KPI_CARDS).
KPI_RETURN_PERIOD = "1년"
KPI_RETURN_COLUMN = "return_1y"


def _return_card(
    branch_return_total: pd.DataFrame | None,
    current_month: str,
    previous_month: str,
) -> dict[str, float | None]:
    """투자수익률 카드. 지점별 수익률 원본의 '전체' 행을 그대로 쓴다.

    수익률은 더할 수도 평균 낼 수도 없으므로 지점에서 다시 만들지 않는다.
    원본에 '전체' 행이 없으면 비운 채로 둔다(→ AGENTS.md §9).

    증감은 두 달 값의 뺄셈, 곧 퍼센트포인트 차이다. 증감률은 내지 않는다 —
    비율의 비율은 화면에서 두 숫자가 같은 뜻으로 읽힌다
    (→ layout.KpiCard.show_rate).
    """
    empty: dict[str, float | None] = {
        "value": None,
        "delta": None,
        "rate": None,
    }
    if branch_return_total is None or branch_return_total.empty:
        return empty
    if KPI_RETURN_COLUMN not in branch_return_total.columns:
        return empty

    def _at(month: str) -> float | None:
        row = row_for_month(branch_return_total, month)
        return None if row is None else to_float(row[KPI_RETURN_COLUMN])

    value = _at(current_month)
    return {
        "value": value,
        "delta": diff_pp(value, _at(previous_month)),
        "rate": None,
    }


def kpi_metrics(
    monthly: pd.DataFrame,
    current_month: str | None = None,
    previous_month: str | None = None,
    monthly_total: pd.DataFrame | None = None,
    branch_return_total: pd.DataFrame | None = None,
) -> dict[str, dict[str, float | None]]:
    """상단 KPI 카드 값. 항상 전체 기준이다.

    KPI 행은 탭 위에 있으므로 어느 탭을 골라도 같은 값을 보여준다.
    월을 지정하지 않으면 데이터의 최신 월과 그 전월을 쓴다.

    투자수익률만 월별 프레임이 아니라 지점별 수익률 원본의 '전체' 행에서
    온다. 그 원본이 없으면 그 카드만 비고 나머지는 그대로 나온다.
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
        # 거래고객 비중 카드가 인원수와 그 증감을 함께 적는다
        # (→ layout.KPI_CARDS).
        "transaction_customer_count": _card(
            "transaction_customer_count", diff_abs
        ),
        "app_share": _card("app_share", diff_pp),
        "common_revenue": _card("common_revenue", diff_abs),
        # 고객 1인당 수익(원). 달마다 그 달의 고객 수로 나눈 값이라
        # 증감도 두 달의 평균끼리 견준 것이다(→ monthly_totals).
        "average_revenue": _card("average_revenue", diff_abs),
        KPI_RETURN_COLUMN: _return_card(
            branch_return_total, current_month, previous_month
        ),
    }
