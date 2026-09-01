"""거래 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.

쓰는 원본 — 거래 추이·상품별 거래·증가율은 거래1(지점×월×상품), 연금
거래 현황은 거래2(지점×월×연금 구분×상품), 입출금은 거래3(지점×월×채널)이다.

증가율은 전년 동월 대비(YoY)다. 기준 월과 12개월 전을 견주므로, 데이터가
13개월보다 짧으면 견줄 달이 없어 산점도가 빈다(→ data.YOY_MONTHS).
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard.data import (
    ALL_CASH_FLOW_CHANNELS,
    CASH_FLOW_CHANNEL_TOTAL,
    CASH_FLOW_CHANNELS,
    PENSION_TRADE_PRODUCT_TYPES,
    PENSION_TYPES,
    TOTAL_LABEL,
    TRADE_PRODUCT_TOTAL,
    TRADE_PRODUCT_TYPES,
    YOY_MONTHS,
    DashboardData,
    reference_month,
    shift_month,
)
from dashboard.grid import (
    COUNT_FORMAT,
    MONEY_FORMAT,
    SIGNED_PERCENT_FORMAT,
    Column,
)
from dashboard.tabs.registry import (
    KIND_RADIO,
    Chart,
    Select,
    Tab,
    Table,
)
from dashboard.tabs.transaction import figures, metrics

ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"
# 표의 조작 안내. 켜 둔 기능만 적는다(→ grid.DEFAULT_COL_DEF).
TABLE_GUIDE = (
    "헤더 클릭 정렬 · 경계 드래그로 너비 조절 · 좌우 스크롤"
    " · 행 클릭 강조"
)

# 지점명 고정 컬럼의 폭. 고정 컬럼은 남는 폭을 나눠 갖지 않으므로 직접
# 정한다. 고객·자산 탭과 같은 값을 써서 세 표의 왼쪽 끝이 나란히 놓이게
# 한다.
BRANCH_COLUMN_WIDTH = 192

# 금액 컬럼의 최소 폭. 조·억·만을 두 자리까지 적으므로
# '3,226억 9,924만원'처럼 길어진다(→ format.format_won).
MONEY_COLUMN_WIDTH = 176

# --- 고를 수 있는 지표 -------------------------------------------------------
# (화면에 보일 이름, 표준 컬럼, 단위, 값 표기, 증감 표기)
#
# 거래금액은 억원, 거래고객수는 명이다. 두 지표가 단위도 자릿수도 달라
# 표기 함수를 지표마다 짝지어 둔다. 그래프·산점도·hover가 모두 이 표를
# 읽으므로 표기가 한 화면 안에서 어긋나지 않는다.
TRADE_MEASURES = (
    (
        "거래고객수",
        "trade_customer_count",
        "명",
        fmt.format_count,
        fmt.format_count_delta,
    ),
    (
        "거래금액",
        "trade_amount",
        "억원",
        fmt.format_assets,
        fmt.format_assets_delta,
    ),
)
_MEASURE_BY_LABEL = {row[0]: row for row in TRADE_MEASURES}

# 연금 거래 현황 막대에 쌓는 상품. '전체'는 세 상품의 합이 아니라 따로
# 계산된 값이라 쌓지 않는다(→ data.PENSION_TRADE_PRODUCT_TYPES).
PENSION_MIX_PRODUCTS = PENSION_TRADE_PRODUCT_TYPES

# 연금 거래 현황이 쓰는 지표. 거래금액 하나로 고정하고 고르게 하지 않는다.
# 거래고객수로는 구성을 읽을 수 없다. '기타'에 원본 값이 없어 한 칸이
# 통째로 빠지고, 남은 두 칸을 더해도 그 연금의 전체 거래고객수가 되지
# 않는다 — 한 고객이 두 상품을 거래하면 양쪽에 들어가 합이 전체보다 커진다.
# 쌓아 놓은 높이가 아무 뜻도 갖지 않는 셈이다.
PENSION_MIX_MEASURE = "거래금액"


# --- 표 컬럼 -----------------------------------------------------------------
# 분류 이름 → 필드 앞머리에 쓸 영문 이름.
#
# 필드 이름은 ASCII여야 한다. AgGrid의 valueFormatter 표현식이 필드
# 이름을 JavaScript 식에 그대로 넣기 때문이다(→ grid._text_expression).
# 화면에 보이는 이름은 왼쪽 한글 그대로다.
PRODUCT_FIELDS: dict[str, str] = {
    TRADE_PRODUCT_TOTAL: "total",
    "국내주식": "domestic_stock",
    "해외주식": "foreign_stock",
    "국내ETF": "domestic_etf",
    "채권": "bond",
    "펀드": "fund",
}
PENSION_FIELDS: dict[str, str] = {
    "개인연금": "personal",
    "IRP": "irp",
    "DC": "dc",
}
CHANNEL_FIELDS: dict[str, str] = {
    "은행": "bank",
    "증권": "securities",
    CASH_FLOW_CHANNEL_TOTAL: "total",
}

# 표에 넣는 순서. 상품은 '전체'를 앞에 두고, 순입금은 은행·증권·전체
# 순으로 적는다(그래프 카드는 증권을 먼저 그린다 — 그쪽은 두 채널을
# 더하면 전체가 되는 것을 보이려는 순서다).
TABLE_PRODUCTS = (TRADE_PRODUCT_TOTAL, *TRADE_PRODUCT_TYPES)
TABLE_CHANNELS = ("은행", "증권", CASH_FLOW_CHANNEL_TOTAL)


def _trade_columns(prefix: str, label: str) -> tuple[Column, ...]:
    """묶음 하나의 거래고객수·거래금액과 각각의 전년 대비 증가율.

    같은 모양이 상품 6개와 연금 3개에 아홉 번 반복된다. 한 곳에서 만들어
    표기와 너비가 묶음마다 어긋나지 않게 한다.
    """
    return (
        Column(
            field=f"{prefix}_customer_count",
            header=f"{label} 거래고객수",
            min_width=150,
            to_text=fmt.format_count,
            js_format=COUNT_FORMAT,
        ),
        Column(
            field=f"{prefix}_amount",
            header=f"{label} 거래금액",
            min_width=MONEY_COLUMN_WIDTH,
            to_text=fmt.format_assets,
            js_format=MONEY_FORMAT,
        ),
        Column(
            field=f"{prefix}_customer_count_growth",
            header=f"{label} 거래고객수 증가율(YoY)",
            min_width=210,
            to_text=fmt.format_signed_percent,
            js_format=SIGNED_PERCENT_FORMAT,
            growth=True,
        ),
        Column(
            field=f"{prefix}_amount_growth",
            header=f"{label} 거래금액 증가율(YoY)",
            min_width=210,
            to_text=fmt.format_signed_percent,
            js_format=SIGNED_PERCENT_FORMAT,
            growth=True,
        ),
    )


def _flow_column(channel: str) -> Column:
    """순입금 컬럼 하나.

    부호가 뜻을 가지므로 `+`/`-`를 붙여 적고 증감 색을 입힌다. 들어온
    달과 빠져나간 달을 훑으면서 바로 가릴 수 있어야 한다.
    """
    return Column(
        field=f"net_inflow_{CHANNEL_FIELDS[channel]}",
        header=f"순입금 {channel}",
        min_width=MONEY_COLUMN_WIDTH,
        to_text=fmt.format_assets_delta,
        js_format=MONEY_FORMAT,
        growth=True,
    )


TABLE_COLUMNS: tuple[Column, ...] = (
    Column(
        field="branch_name",
        header="영업점명",
        min_width=120,
        to_text=str,
        width=BRANCH_COLUMN_WIDTH,
        pinned=True,
    ),
    *(
        column
        for product in TABLE_PRODUCTS
        for column in _trade_columns(
            f"trade_{PRODUCT_FIELDS[product]}", product
        )
    ),
    *(_flow_column(channel) for channel in TABLE_CHANNELS),
    *(
        column
        for pension in PENSION_TYPES
        for column in _trade_columns(
            f"pension_{PENSION_FIELDS[pension]}", pension
        )
    ),
)

TABLE_FIELDS = tuple(column.field for column in TABLE_COLUMNS)


# --- 선택 목록 ---------------------------------------------------------------
def _branch_names(data: DashboardData) -> list[str]:
    return list(data.branch_names)


def _first_branch(data: DashboardData) -> str:
    names = data.branch_names
    return names[0] if names else ""


def _scopes(data: DashboardData) -> list[str]:
    """전체를 포함한 구분 목록. 입출금·연금 거래가 쓴다."""
    return [TOTAL_LABEL, *data.branch_names]


def _total_scope(_data: DashboardData) -> str:
    return TOTAL_LABEL


def _measure_labels(_data: DashboardData) -> list[str]:
    return [label for label, *_ in TRADE_MEASURES]


def _first_measure(_data: DashboardData) -> str:
    return TRADE_MEASURES[0][0]


def _product_labels(_data: DashboardData) -> list[str]:
    """상품별 카드에서 고를 상품. 종합 카드가 '전체'를 맡으므로 뺀다."""
    return list(TRADE_PRODUCT_TYPES)


def _first_product(_data: DashboardData) -> str:
    return TRADE_PRODUCT_TYPES[0]


def _pension_labels(_data: DashboardData) -> list[str]:
    return list(PENSION_TYPES)


def _first_pension(_data: DashboardData) -> str:
    return PENSION_TYPES[0]


BRANCH_SELECT = Select(
    key="branch",
    label="영업점",
    options=_branch_names,
    default=_first_branch,
)

SCOPE_SELECT = Select(
    key="scope",
    label="구분",
    options=_scopes,
    default=_total_scope,
)

MEASURE_SELECT = Select(
    key="measure",
    label="지표",
    options=_measure_labels,
    default=_first_measure,
    kind=KIND_RADIO,
)

PRODUCT_SELECT = Select(
    key="product",
    label="상품",
    options=_product_labels,
    default=_first_product,
)


# --- 기준 월 -----------------------------------------------------------------
def _yoy_base_month(data: DashboardData) -> str:
    """전년 동월. 기준 월에서 `YOY_MONTHS`만큼 거슬러 올라간다."""
    return shift_month(reference_month(data), -YOY_MONTHS)


# --- Figure 만들기 -----------------------------------------------------------
def _measure_of(selection: dict):
    label = selection.get("measure") or TRADE_MEASURES[0][0]
    return _MEASURE_BY_LABEL[label]


def _trend_of(data: DashboardData, selection: dict, product: str):
    """상품 하나의 추이 카드. 종합 카드와 상품별 카드가 함께 쓴다."""
    branch_name = selection.get("branch") or ""
    label, column, unit, to_text, to_delta = _measure_of(selection)
    trend = metrics.measure_trend(
        data.transaction,
        data.transaction_total,
        branch_name,
        column,
        {"product_type": product},
    )
    title = label if product == TRADE_PRODUCT_TOTAL else f"{product} {label}"
    return figures.create_trade_trend_figure(
        trend, branch_name, title, unit, to_text, to_delta
    )


def _total_trend(data: DashboardData, selection: dict):
    return _trend_of(data, selection, TRADE_PRODUCT_TOTAL)


def _product_trend(data: DashboardData, selection: dict):
    product = selection.get("product") or TRADE_PRODUCT_TYPES[0]
    return _trend_of(data, selection, product)


def _growth_of(data: DashboardData, selection: dict, product: str):
    """상품 하나의 증가율 산점도. 종합 카드와 상품별 카드가 함께 쓴다."""
    label, column, unit, to_text, _delta = _measure_of(selection)
    current = reference_month(data)
    base = _yoy_base_month(data)
    scatter = metrics.growth_scatter(
        data.transaction,
        column,
        current,
        base,
        {"product_type": product},
    )
    title = label if product == TRADE_PRODUCT_TOTAL else f"{product} {label}"
    return figures.create_growth_scatter_figure(
        scatter,
        title,
        unit,
        to_text,
        metrics.median_value(scatter),
        base_month=base,
        current_month=current,
    )


def _total_growth(data: DashboardData, selection: dict):
    return _growth_of(data, selection, TRADE_PRODUCT_TOTAL)


def _product_growth(data: DashboardData, selection: dict):
    product = selection.get("product") or TRADE_PRODUCT_TYPES[0]
    return _growth_of(data, selection, product)


def _cash_flow(data: DashboardData, selection: dict):
    scope = selection.get("scope") or TOTAL_LABEL
    trend = metrics.cash_flow_trend(
        data.cash_flow,
        data.cash_flow_total,
        scope,
        TOTAL_LABEL,
        CASH_FLOW_CHANNELS,
        CASH_FLOW_CHANNEL_TOTAL,
    )
    return figures.create_cash_flow_figure(
        trend, scope, CASH_FLOW_CHANNELS
    )


def _pension_mix(data: DashboardData, selection: dict):
    scope = selection.get("scope") or TOTAL_LABEL
    pension_type = selection.get("pension") or PENSION_TYPES[0]
    label, column, unit, to_text, _delta = _MEASURE_BY_LABEL[
        PENSION_MIX_MEASURE
    ]
    mix = metrics.pension_mix_trend(
        data.pension_transaction,
        data.pension_transaction_total,
        scope,
        TOTAL_LABEL,
        pension_type,
        PENSION_MIX_PRODUCTS,
        column,
    )
    return figures.create_pension_mix_figure(
        mix, PENSION_MIX_PRODUCTS, scope, pension_type, label, unit, to_text
    )


# --- 보조 문구 ---------------------------------------------------------------
def _yoy_text(data: DashboardData) -> str:
    base = fmt.format_month(_yoy_base_month(data))
    current = fmt.format_month(reference_month(data))
    return f"{base} → {current} · {len(data.branch_names)}개 영업점"


def _cash_flow_text(_data: DashboardData) -> str:
    securities, bank = CASH_FLOW_CHANNELS
    return f"막대는 순입금 전체 · 선을 더하면 막대({securities}+{bank})"


def _pension_text(_data: DashboardData) -> str:
    products = " · ".join(PENSION_MIX_PRODUCTS)
    return f"{PENSION_MIX_MEASURE} 기준 · 쌓는 상품 {products}"


def _table_rows(data: DashboardData, _selection: dict | None = None):
    """지점별 공통고객 거래 현황 표의 (전체 행, 지점 행들).

    상품·연금은 거래고객수와 거래금액을 함께 담고, 순입금은 값 하나만
    담는다. 어느 프레임의 어느 분류를 볼지 여기서 한 번 정해 넘긴다.
    연금은 그 구분의 '전체' 상품 값을 쓴다 — 표에 상품별로 또 나누면
    컬럼이 세 배가 된다.
    """
    current = reference_month(data)
    base = _yoy_base_month(data)
    groups = (
        *(
            (
                f"trade_{PRODUCT_FIELDS[product]}",
                data.transaction,
                data.transaction_total,
                {"product_type": product},
            )
            for product in TABLE_PRODUCTS
        ),
        *(
            (
                f"pension_{PENSION_FIELDS[pension]}",
                data.pension_transaction,
                data.pension_transaction_total,
                {
                    "pension_type": pension,
                    "product_type": TRADE_PRODUCT_TOTAL,
                },
            )
            for pension in PENSION_TYPES
        ),
    )
    flows = tuple(
        (
            f"net_inflow_{CHANNEL_FIELDS[channel]}",
            data.cash_flow,
            data.cash_flow_total,
            {"channel": channel},
        )
        for channel in TABLE_CHANNELS
    )
    return metrics.branch_table(
        groups, flows, TABLE_FIELDS, current, base, TOTAL_LABEL
    )


def _table_text(data: DashboardData) -> str:
    month = fmt.format_month(reference_month(data))
    return f"{month} 기준"


def _context(data: DashboardData) -> dict:
    return {
        "branch_names": list(data.branch_names),
        "branch_count": len(data.branch_names),
    }


TAB = Tab(
    value="transaction",
    label="거래",
    build_context=_context,
    charts=(
        Chart(
            key="total",
            title="거래 추이",
            build=_total_trend,
            selects=(BRANCH_SELECT, MEASURE_SELECT),
        ),
        Chart(
            key="growth",
            title="영업점별 거래 규모 비교분석",
            build=_total_growth,
            selects=(MEASURE_SELECT,),
            description=_yoy_text,
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
        Chart(
            key="product",
            title="상품별 거래",
            build=_product_trend,
            selects=(BRANCH_SELECT, PRODUCT_SELECT, MEASURE_SELECT),
        ),
        Chart(
            key="productgrowth",
            title="영업점X상품별 거래 규모 비교분석",
            build=_product_growth,
            selects=(PRODUCT_SELECT, MEASURE_SELECT),
            description=_yoy_text,
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
        Chart(
            key="cashflow",
            title="입출금 분석",
            build=_cash_flow,
            selects=(SCOPE_SELECT,),
            description=_cash_flow_text,
        ),
        Chart(
            key="pension",
            title="연금 거래 현황 분석",
            build=_pension_mix,
            # 지표를 고르게 하지 않는다. 거래금액 하나뿐이라 라디오가
            # 있어도 누를 곳이 없다(→ PENSION_MIX_MEASURE).
            selects=(
                SCOPE_SELECT,
                Select(
                    key="pension",
                    label="연금",
                    options=_pension_labels,
                    default=_first_pension,
                    kind=KIND_RADIO,
                ),
            ),
            description=_pension_text,
        ),
    ),
    tables=(
        Table(
            title="영업점별 공통고객 거래 현황",
            columns=TABLE_COLUMNS,
            build=_table_rows,
            description=_table_text,
            guide=TABLE_GUIDE,
        ),
    ),
)

__all__ = [
    "PENSION_MIX_MEASURE",
    "PENSION_MIX_PRODUCTS",
    "TABLE_COLUMNS",
    "TABLE_FIELDS",
    "TAB",
    "TRADE_MEASURES",
    "figures",
    "metrics",
]


# 채널 목록이 늘면 입출금 그림의 선도 늘어야 한다. 지금은 두 채널 + 전체를
# 전제로 그리므로, 늘어난 것을 모르고 지나가지 않게 여기서 확인한다.
if len(ALL_CASH_FLOW_CHANNELS) != 3:  # pragma: no cover - 설정 확인
    raise ValueError(
        "입출금 그림은 채널 두 개와 '전체'를 전제로 합니다. "
        f"현재 채널: {', '.join(ALL_CASH_FLOW_CHANNELS)}. "
        "dashboard/tabs/transaction/figures.py 의 "
        "create_cash_flow_figure 를 함께 고쳐 주세요."
    )
