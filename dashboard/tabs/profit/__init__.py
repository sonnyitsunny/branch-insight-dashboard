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
    TOTAL_LABEL,
    YOY_MONTHS,
    DashboardData,
    reference_month,
    shift_month,
)
from dashboard.tabs.profit import figures, metrics
from dashboard.tabs.registry import (
    VARIANTS_SLOT,
    Chart,
    Select,
    Tab,
)

ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"

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
)

__all__ = [
    "MIX_SLOTS",
    "MIX_TYPES",
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
