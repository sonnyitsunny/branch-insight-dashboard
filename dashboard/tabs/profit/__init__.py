"""수익 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.

쓰는 원본 — 네 카드 모두 수익1(지점 × 월 × 수익 분류)이다.

**'전체'와 '공통'** — 원본의 '전체'는 전체고객, '공통'은 공통고객이다.
지점 축의 '전체'(합계 행)와 이름이 같지만 다른 축이다
(→ dashboard/sources/revenue1.py).

증가율은 전년 동월 대비(YoY)다. 기준 월과 12개월 전을 견주므로, 데이터가
13개월보다 짧으면 견줄 달이 없어 산점도가 빈다(→ data.YOY_MONTHS).
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard import metrics as shared
from dashboard.data import (
    REVENUE_FINAL,
    REVENUE_PENSION,
    REVENUE_PRODUCT_TYPES,
    REVENUE_RETAIL,
    TOTAL_LABEL,
    YOY_MONTHS,
    DashboardData,
    reference_month,
    shift_month,
)
from dashboard.grid import (
    MONEY_FORMAT,
    PERCENT_FORMAT,
    SIGNED_PERCENT_FORMAT,
    Column,
)
from dashboard.tabs.profit import figures, metrics
from dashboard.tabs.registry import (
    VARIANTS_SLOT,
    Chart,
    Select,
    Tab,
    Table,
)

ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"
# 표의 조작 안내. 켜 둔 기능만 적는다(→ grid.DEFAULT_COL_DEF).
TABLE_GUIDE = (
    "헤더 클릭 정렬 · 경계 드래그로 너비 조절 · 좌우 스크롤"
    " · 행 클릭 강조"
)

# 지점명 고정 컬럼의 폭. 고정 컬럼은 남는 폭을 나눠 갖지 않으므로 직접
# 정한다. 고객·자산·거래 탭과 같은 값을 써서 표들의 왼쪽 끝이 나란히
# 놓이게 한다.
BRANCH_COLUMN_WIDTH = 192

# 표 컬럼의 최소 폭. 이 표는 값보다 헤더가 길다. 헤더에 원본 컬럼 이름을
# 그대로 적기 때문이다(→ TABLE_HEADER_PREFIX). 가장 긴 이름이
# '수익_공통_CMA발행어음RP 증가율(YoY)'이라 그 폭에 맞춘다.
MONEY_COLUMN_WIDTH = 190
GROWTH_COLUMN_WIDTH = 260
SHARE_COLUMN_WIDTH = 215

# --- 표준 컬럼 ---------------------------------------------------------------
# 데이터 계층이 맞춰 둔 이름을 여기 한 번만 적는다
# (→ dashboard/data.py 의 REVENUE_COLUMNS).
AMOUNT_COLUMN = "revenue_amount"  # 공통고객 수익(원)
ALL_AMOUNT_COLUMN = "all_revenue_amount"  # 전체고객 수익(원)
SHARE_COLUMN = "revenue_share"  # 분류별 비중(%)
COMMON_SHARE_COLUMN = "common_revenue_share"  # 공통고객 수익 비중(%)

# --- 화면에 쓰는 이름 --------------------------------------------------------
# 원본 컬럼 이름은 길어서 화면에는 짧게 적는다. 뜻이 헷갈리지 않도록
# '전체고객'·'공통고객'을 앞에 붙인다.
ALL_AMOUNT_LABEL = "전체고객 수익"
COMMON_AMOUNT_LABEL = "공통고객 수익"
COMMON_SHARE_LABEL = "공통고객 수익 비중"

# --- 수익 비중 막대에 쌓는 분류 ----------------------------------------------
# 리테일 상품 아홉 개에 '퇴직'을 더한 열 칸이다. 원본이 이 열 개의 비중을
# 담고 있으며 분모는 공통고객 '최종' 수익이다. 소계인 '리테일'과 합계인
# '최종'은 쌓지 않는다 — 함께 쌓으면 같은 금액을 두 번 세게 된다.
MIX_TYPES: tuple[str, ...] = (*REVENUE_PRODUCT_TYPES, REVENUE_PENSION)

# 수익 비중에서 함께 비교할 지점 칸 수. 첫 칸은 항상 전체다.
MIX_SLOTS = 3


# --- 표 컬럼 -----------------------------------------------------------------
# 수익 분류 → 필드 앞머리에 쓸 영문 이름.
#
# 필드 이름은 ASCII여야 한다. AgGrid의 valueFormatter 표현식이 필드
# 이름을 JavaScript 식에 그대로 넣기 때문이다(→ grid._text_expression).
# 화면에 보이는 이름은 왼쪽 한글 그대로다.
REVENUE_FIELDS: dict[str, str] = {
    REVENUE_FINAL: "final",
    REVENUE_RETAIL: "retail",
    REVENUE_PENSION: "pension",
    "국내주식": "domestic_stock",
    "국내ETF": "domestic_etf",
    "해외주식": "foreign_stock",
    "예수금": "deposit",
    "신용": "credit",
    "펀드": "fund",
    "채권": "bond",
    "CMA발행어음RP": "cma_rp",
    "기타": "other",
}

# 표 헤더에 붙이는 앞머리. 원본 컬럼 이름을 그대로 적어, 표에서 본 값이
# 원본의 어느 컬럼인지 바로 찾을 수 있게 한다.
TABLE_HEADER_PREFIX = "수익_공통_"

# 표에 금액과 증가율을 넣는 분류. 묶음 셋을 앞에 두고 상품을 잇는다.
# '기타'는 일부러 뺀다. 그래서 비중 컬럼을 모두 더해도 100%가 되지 않는다.
# 우상단 비중 그래프는 '기타'를 포함해 쌓으므로 표와 구성이 다르다.
TABLE_TYPES: tuple[str, ...] = (
    REVENUE_FINAL,
    REVENUE_RETAIL,
    REVENUE_PENSION,
    "국내주식",
    "국내ETF",
    "해외주식",
    "예수금",
    "신용",
    "펀드",
    "채권",
    "CMA발행어음RP",
)
# 비중을 넣는 분류. '최종'과 '리테일'은 원본에 비중 컬럼이 없다.
# '최종' 자리에는 뜻이 다른 공통고객 수익 비중을 따로 넣는다.
TABLE_SHARE_TYPES: tuple[str, ...] = tuple(
    revenue_type
    for revenue_type in TABLE_TYPES
    if revenue_type not in (REVENUE_FINAL, REVENUE_RETAIL)
)


def _amount_columns(revenue_type: str) -> tuple[Column, ...]:
    """분류 하나의 수익과 전년 대비 증가율.

    같은 모양이 분류마다 반복된다. 한 곳에서 만들어 표기와 너비가
    분류마다 어긋나지 않게 한다.
    """
    field = f"revenue_{REVENUE_FIELDS[revenue_type]}"
    header = f"{TABLE_HEADER_PREFIX}{revenue_type}"
    return (
        Column(
            field=field,
            header=header,
            min_width=MONEY_COLUMN_WIDTH,
            to_text=fmt.format_revenue,
            js_format=MONEY_FORMAT,
        ),
        Column(
            field=f"{field}_growth",
            # 'YoY'는 다른 탭의 표와 같은 표기다. 한 화면 안에서 같은 뜻이
            # 다르게 적히지 않게 맞춘다.
            header=f"{header} 증가율(YoY)",
            min_width=GROWTH_COLUMN_WIDTH,
            to_text=fmt.format_signed_percent,
            js_format=SIGNED_PERCENT_FORMAT,
            growth=True,
        ),
    )


def _share_column(field: str, header: str) -> Column:
    return Column(
        field=field,
        header=header,
        min_width=SHARE_COLUMN_WIDTH,
        to_text=fmt.format_percent,
        js_format=PERCENT_FORMAT,
    )


TABLE_COLUMNS: tuple[Column, ...] = (
    Column(
        field="branch_name",
        header="지점명",
        min_width=120,
        to_text=str,
        width=BRANCH_COLUMN_WIDTH,
        pinned=True,
    ),
    *(
        column
        for revenue_type in TABLE_TYPES
        for column in _amount_columns(revenue_type)
    ),
    # 전체고객 수익 대비 공통고객 수익 비중. 아래 분류별 비중과 분모가
    # 다르며, 원본에서도 분류 이름 없이 담겨 있다
    # (→ dashboard/sources/revenue1.py).
    _share_column("share_common", f"{TABLE_HEADER_PREFIX}비중"),
    *(
        _share_column(
            f"share_{REVENUE_FIELDS[revenue_type]}",
            f"{TABLE_HEADER_PREFIX}{revenue_type}_비중",
        )
        for revenue_type in TABLE_SHARE_TYPES
    ),
)

TABLE_FIELDS = tuple(column.field for column in TABLE_COLUMNS)


# --- 선택 목록 ---------------------------------------------------------------
def _scopes(data: DashboardData) -> list[str]:
    """전체를 포함한 구분 목록. 수익 추이가 쓴다."""
    return [TOTAL_LABEL, *data.branch_names]


def _total_scope(_data: DashboardData) -> str:
    return TOTAL_LABEL


def _branch_names(data: DashboardData) -> list[str]:
    return list(data.branch_names)


def _nth_branch(index: int):
    """지점 목록의 n번째. 지점이 적으면 마지막 지점을 쓴다."""

    def pick(data: DashboardData) -> str:
        names = data.branch_names
        if not names:
            return ""
        return names[min(index, len(names) - 1)]

    return pick


SCOPE_SELECT = Select(
    key="scope",
    label="구분",
    options=_scopes,
    default=_total_scope,
)


# --- 기준 월 -----------------------------------------------------------------
def _yoy_base_month(data: DashboardData) -> str:
    """전년 동월. 기준 월에서 `YOY_MONTHS`만큼 거슬러 올라간다."""
    return shift_month(reference_month(data), -YOY_MONTHS)


# --- Figure 만들기 -----------------------------------------------------------
def _trend(data: DashboardData, selection: dict):
    """수익 추이 — 막대는 전체고객 수익, 선은 공통고객 수익 비중."""
    scope = selection.get("scope") or TOTAL_LABEL
    trend = metrics.revenue_trend(
        data.revenue,
        data.revenue_total,
        scope,
        TOTAL_LABEL,
        REVENUE_FINAL,
        ALL_AMOUNT_COLUMN,
        COMMON_SHARE_COLUMN,
    )
    return figures.create_revenue_trend_figure(
        trend, scope, f"{ALL_AMOUNT_LABEL}(원)", COMMON_SHARE_LABEL
    )


def _mix(data: DashboardData, selection: dict):
    scopes = [TOTAL_LABEL] + [
        selection.get(f"branch{index + 1}") or ""
        for index in range(MIX_SLOTS)
    ]
    mix = metrics.revenue_mix(
        data.revenue,
        data.revenue_total,
        scopes,
        TOTAL_LABEL,
        MIX_TYPES,
        reference_month(data),
        SHARE_COLUMN,
    )
    return figures.create_revenue_mix_figure(mix, MIX_TYPES)


def _mix_slot_values(data: DashboardData) -> dict:
    """수익 비중에서 지점 칸마다 갈아 끼울 값.

    칸이 셋이라 조합이 지점 수의 세제곱이다. Figure를 다 담을 수 없어
    값만 담는다(→ export_html, registry.VARIANTS_SLOT).

    막대 안에 적을 문구도 함께 담는다. 브라우저가 숫자만 바꾸면 막대 높이는
    새 지점인데 적힌 비중은 이전 지점 값으로 남는다. 문구를 만드는 규칙은
    화면과 같은 함수 한 곳에만 둔다(→ dashboard.figures.share_label).
    """
    from dashboard.figures import share_label

    columns = metrics.revenue_mix_columns(
        data.revenue, MIX_TYPES, reference_month(data), SHARE_COLUMN
    )
    values = {
        name: {
            "y": numbers,
            "text": [share_label(value) for value in numbers],
        }
        for name, numbers in columns.items()
    }
    return {f"branch{index + 1}": values for index in range(MIX_SLOTS)}


def _scatter_of(
    data: DashboardData,
    column: str,
    measure_label: str,
    unit_label: str,
    to_text,
    value_suffix: str = "",
):
    """산점도 하나. 금액 비교와 점유율 비교가 함께 쓴다."""
    current = reference_month(data)
    base = _yoy_base_month(data)
    scatter = shared.growth_scatter(
        data.revenue,
        column,
        current,
        base,
        {"revenue_type": REVENUE_FINAL},
    )
    return figures.create_revenue_scatter_figure(
        scatter,
        measure_label,
        unit_label,
        to_text,
        shared.median_value(scatter),
        base_month=base,
        current_month=current,
        value_suffix=value_suffix,
    )


def _amount_scatter(data: DashboardData, _selection: dict):
    return _scatter_of(
        data,
        AMOUNT_COLUMN,
        f"{COMMON_AMOUNT_LABEL}금액",
        "원",
        fmt.format_revenue,
    )


def _share_scatter(data: DashboardData, _selection: dict):
    return _scatter_of(
        data,
        COMMON_SHARE_COLUMN,
        f"{COMMON_AMOUNT_LABEL} 점유율",
        "%",
        fmt.format_percent,
        value_suffix="%",
    )


# --- 보조 문구 ---------------------------------------------------------------
def _trend_text(_data: DashboardData) -> str:
    return (
        f"막대는 {ALL_AMOUNT_LABEL}(원) · "
        f"선은 {COMMON_SHARE_LABEL}(%, 공통 최종 ÷ 전체 최종)"
    )


def _mix_text(data: DashboardData) -> str:
    month = fmt.format_month(reference_month(data))
    return f"{month} 기준 · 첫 칸은 {TOTAL_LABEL} · 쌓는 칸 {len(MIX_TYPES)}개"


def _yoy_text(data: DashboardData) -> str:
    base = fmt.format_month(_yoy_base_month(data))
    current = fmt.format_month(reference_month(data))
    return f"{base} → {current} · {len(data.branch_names)}개 지점"


def _table_rows(data: DashboardData, _selection: dict | None = None):
    """지점별 공통고객 수익 현황 표의 (전체 행, 지점 행들).

    어느 분류의 어느 컬럼을 볼지 여기서 한 번 정해 넘긴다. 금액은 모두
    공통고객 기준이며 원 단위다(→ AMOUNT_COLUMN).
    """
    current = reference_month(data)
    base = _yoy_base_month(data)
    amounts = tuple(
        (
            f"revenue_{REVENUE_FIELDS[revenue_type]}",
            revenue_type,
            AMOUNT_COLUMN,
        )
        for revenue_type in TABLE_TYPES
    )
    shares = (
        ("share_common", REVENUE_FINAL, COMMON_SHARE_COLUMN),
        *(
            (
                f"share_{REVENUE_FIELDS[revenue_type]}",
                revenue_type,
                SHARE_COLUMN,
            )
            for revenue_type in TABLE_SHARE_TYPES
        ),
    )
    return metrics.branch_table(
        data.revenue,
        data.revenue_total,
        amounts,
        shares,
        TABLE_FIELDS,
        current,
        base,
        TOTAL_LABEL,
    )


def _table_text(data: DashboardData) -> str:
    month = fmt.format_month(reference_month(data))
    base = fmt.format_month(_yoy_base_month(data))
    return (
        f"{month} 기준 · 증가율은 {base} 대비 · "
        f"전체 1행과 지점 {len(data.branch_names)}행"
    )


def _context(data: DashboardData) -> dict:
    return {
        "branch_names": list(data.branch_names),
        "branch_count": len(data.branch_names),
    }


TAB = Tab(
    value="profit",
    label="수익",
    build_context=_context,
    charts=(
        Chart(
            key="trend",
            title="공통고객 수익 추이",
            build=_trend,
            selects=(SCOPE_SELECT,),
            description=_trend_text,
        ),
        Chart(
            key="mix",
            title="공통고객 수익 비중",
            build=_mix,
            selects=tuple(
                Select(
                    key=f"branch{index + 1}",
                    label=f"비교 {index + 1}",
                    options=_branch_names,
                    default=_nth_branch(index),
                )
                for index in range(MIX_SLOTS)
            ),
            description=_mix_text,
            # 칸마다 지점을 고르므로 조합이 지점 수의 세제곱이다. 정적
            # HTML은 Figure 대신 숫자를 담고 그 자리만 갈아 끼운다.
            variants=VARIANTS_SLOT,
            slot_values=_mix_slot_values,
        ),
        Chart(
            key="amount",
            title="공통고객 수익금액 비교",
            build=_amount_scatter,
            description=_yoy_text,
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
        Chart(
            key="share",
            title="공통고객 수익 점유율 비교",
            build=_share_scatter,
            description=_yoy_text,
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
    ),
    tables=(
        Table(
            title="지점별 공통고객 수익 현황",
            columns=TABLE_COLUMNS,
            build=_table_rows,
            description=_table_text,
            guide=TABLE_GUIDE,
        ),
    ),
)

__all__ = [
    "MIX_SLOTS",
    "MIX_TYPES",
    "TABLE_COLUMNS",
    "TABLE_FIELDS",
    "TABLE_TYPES",
    "TAB",
    "figures",
    "metrics",
]


# 쌓는 칸이 색보다 많아지면 서로 다른 분류가 같은 색으로 그려진다. 원본에
# 상품이 늘었을 때 모르고 지나가지 않게 여기서 확인한다.
if len(MIX_TYPES) > len(figures.MIX_COLORS):  # pragma: no cover - 설정 확인
    raise ValueError(
        f"수익 비중 막대에 쌓는 칸이 {len(MIX_TYPES)}개인데 색은 "
        f"{len(figures.MIX_COLORS)}개뿐입니다. "
        "dashboard/tabs/profit/figures.py 의 MIX_COLORS 를 늘려 주세요."
    )
