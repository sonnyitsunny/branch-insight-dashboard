"""자산 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.

쓰는 원본 — 추이는 자산1(지점×월), 구성·증가율은 자산2(지점 한 시점),
상품별 증감 히트맵은 자산3(지점×월×상품), 연금 자산 추이는 자산4(지점×월)다.
표의 연금 1인 평균만 자산2가 준다.
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard.data import (
    ASSET_SHARE_COLUMNS,
    ASSET_TYPES,
    ASSET_TYPE_TOTAL,
    TOTAL_LABEL,
    DashboardData,
    reference_month,
)
from dashboard.grid import (
    COUNT_FORMAT,
    MONEY_FORMAT,
    PERCENT_FORMAT,
    SIGNED_PERCENT_FORMAT,
    Column,
)
from dashboard.tabs.asset import figures, metrics
from dashboard.tabs.registry import (
    KIND_RADIO,
    PLACE_AXIS_X,
    PLACE_AXIS_Y,
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
# 정한다. 고객 탭과 같은 값을 써서 두 표의 왼쪽 끝이 나란히 놓이게 한다.
BRANCH_COLUMN_WIDTH = 192

# 금액 컬럼의 최소 폭. 조·억·만을 두 자리까지 적으므로
# '3,226억 9,924만원'처럼 길어진다(→ format.format_won).
MONEY_COLUMN_WIDTH = 176

# --- 추이에서 고를 수 있는 값 ------------------------------------------------
# (화면에 보일 이름, 표준 컬럼, 단위, 값 표기, 증감 표기)
TREND_MEASURES = (
    (
        "순자산",
        "net_assets",
        "억원",
        fmt.format_assets,
        fmt.format_assets_delta,
    ),
    (
        "고객 평균 자산",
        "average_assets",
        "백만원",
        fmt.format_million_won,
        fmt.format_million_won_delta,
    ),
)
_TREND_BY_LABEL = {row[0]: row for row in TREND_MEASURES}

# --- 자산 구성 막대에 쌓는 상품 ----------------------------------------------
# 표준 컬럼 순서와 화면 이름을 짝지어 한 곳에서만 관리한다.
MIX_LABELS = (
    "국내주식",
    "해외주식",
    "국내ETF",
    "채권",
    "펀드",
    "기타",
)
_MIX_BY_LABEL = dict(zip(MIX_LABELS, ASSET_SHARE_COLUMNS))

# 비중 비교 산점도에서 고를 수 있는 상품. '기타'는 성격이 달라 뺀다.
COMPARE_LABELS = MIX_LABELS[:-1]

# 자산 구성에서 함께 비교할 지점 칸 수. 첫 칸은 항상 전체다.
MIX_SLOTS = 3

# --- 연금 상품 ---------------------------------------------------------------
# (화면 이름, 표 컬럼 앞머리, 자산 컬럼, 고객 수 컬럼)
# 앞머리 하나로 표의 세 컬럼 이름을 만든다. 상품이 늘면 여기 한 줄만 더한다.
PENSION_PRODUCTS = (
    ("개인연금", "pension", "pension_assets", "pension_customer_count"),
    ("IRP", "irp", "irp_assets", "irp_customer_count"),
    ("DC", "dc", "dc_assets", "dc_customer_count"),
)
_PENSION_BY_LABEL = {row[0]: row for row in PENSION_PRODUCTS}

# --- 연금 추이에서 고를 수 있는 지표 -----------------------------------------
# (화면 이름, 단위, 값 표기, 증감 표기, 1인 평균 여부)
#
# 이름은 아래 표의 연금 컬럼과 같은 말을 쓴다. 같은 값을 그래프와 표에서
# 다르게 부르면 두 곳을 견줄 때 헷갈린다(→ _product_columns).
#
# 1인 평균은 자산4가 담고 있지 않아 데이터 계층이 나눠 만든다. 표의 1인
# 평균은 자산2가 원 단위로 담고 있는 값이라 만원 자리가 어긋날 수 있다
# (→ metrics.pension_trend).
PENSION_MEASURES = (
    ("자산", "억원", fmt.format_assets, fmt.format_assets_delta, False),
    (
        "1인 평균",
        "백만원",
        fmt.format_million_won,
        fmt.format_million_won_delta,
        True,
    ),
)
_PENSION_MEASURE_BY_LABEL = {row[0]: row for row in PENSION_MEASURES}


# --- 표 컬럼 -----------------------------------------------------------------
def _share_column(field: str, header: str) -> Column:
    return Column(
        field=field,
        header=header,
        min_width=130,
        to_text=fmt.format_percent,
        js_format=PERCENT_FORMAT,
    )


def _product_columns(prefix: str, label: str) -> tuple[Column, ...]:
    """연금 상품 하나의 고객 수·자산·1인 평균 세 컬럼.

    상품이 셋이라 같은 모양이 아홉 번 반복된다. 한 곳에서 만들어 표기와
    너비가 상품마다 어긋나지 않게 한다.
    """
    return (
        Column(
            field=f"{prefix}_customer_count",
            header=f"{label} 고객 수",
            min_width=140,
            to_text=fmt.format_count,
            js_format=COUNT_FORMAT,
        ),
        Column(
            field=f"{prefix}_assets",
            header=f"{label} 자산",
            min_width=MONEY_COLUMN_WIDTH,
            to_text=fmt.format_assets,
            js_format=MONEY_FORMAT,
        ),
        Column(
            field=f"{prefix}_assets_average",
            header=f"{label} 1인 평균",
            min_width=MONEY_COLUMN_WIDTH,
            to_text=fmt.format_million_won,
            js_format=MONEY_FORMAT,
        ),
    )


TABLE_COLUMNS = (
    Column(
        field="branch_name",
        header="지점명",
        min_width=120,
        to_text=str,
        width=BRANCH_COLUMN_WIDTH,
        pinned=True,
    ),
    Column(
        field="customer_count",
        header="공통고객 수",
        min_width=130,
        to_text=fmt.format_count,
        js_format=COUNT_FORMAT,
    ),
    Column(
        field="net_assets",
        header="자산 합계",
        min_width=MONEY_COLUMN_WIDTH,
        to_text=fmt.format_assets,
        js_format=MONEY_FORMAT,
    ),
    Column(
        field="average_assets",
        header="자산 평균",
        min_width=MONEY_COLUMN_WIDTH,
        to_text=fmt.format_million_won,
        js_format=MONEY_FORMAT,
    ),
    Column(
        field="net_assets_growth",
        header="자산 증가율(YoY)",
        min_width=160,
        to_text=fmt.format_signed_percent,
        js_format=SIGNED_PERCENT_FORMAT,
        growth=True,
    ),
    *(
        _share_column(column, f"{label} 비중")
        for column, label in zip(ASSET_SHARE_COLUMNS, MIX_LABELS)
    ),
    *(
        column
        for label, prefix, *_ in PENSION_PRODUCTS
        for column in _product_columns(prefix, label)
    ),
)

TABLE_FIELDS = tuple(column.field for column in TABLE_COLUMNS)


# --- 선택 목록 ---------------------------------------------------------------
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


def _scopes(data: DashboardData) -> list[str]:
    return [TOTAL_LABEL, *data.branch_names]


def _total_scope(data: DashboardData) -> str:
    return TOTAL_LABEL


def _measure_labels(_data: DashboardData) -> list[str]:
    return [label for label, *_ in TREND_MEASURES]


def _first_measure(_data: DashboardData) -> str:
    return TREND_MEASURES[0][0]


def _compare_labels(_data: DashboardData) -> list[str]:
    return list(COMPARE_LABELS)


def _pension_labels(_data: DashboardData) -> list[str]:
    return [label for label, *_ in PENSION_PRODUCTS]


def _first_pension(_data: DashboardData) -> str:
    return PENSION_PRODUCTS[0][0]


def _pension_measure_labels(_data: DashboardData) -> list[str]:
    return [label for label, *_ in PENSION_MEASURES]


def _first_pension_measure(_data: DashboardData) -> str:
    return PENSION_MEASURES[0][0]


BRANCH_SELECT = Select(
    key="branch",
    label="지점",
    options=_branch_names,
    default=_nth_branch(0),
)


# --- Figure 만들기 -----------------------------------------------------------
def _trend(data: DashboardData, selection: dict):
    branch_name = selection.get("branch") or ""
    label = selection.get("measure") or TREND_MEASURES[0][0]
    _, column, unit, to_text, to_delta = _TREND_BY_LABEL[label]
    trend = metrics.asset_trend(
        data.monthly, branch_name, column, data.monthly_total
    )
    return figures.create_asset_trend_figure(
        trend, branch_name, label, unit, to_text, to_delta
    )


def _growth(data: DashboardData, _selection: dict | None = None):
    scatter = metrics.asset_growth_scatter(data.summary)
    return figures.create_asset_growth_figure(
        scatter,
        metrics.median_net_assets(scatter),
        start_month=_start_month(data),
        end_month=reference_month(data),
    )


def _mix(data: DashboardData, selection: dict):
    scopes = [TOTAL_LABEL] + [
        selection.get(f"branch{index + 1}") or ""
        for index in range(MIX_SLOTS)
    ]
    mix = metrics.asset_mix(
        data.summary, scopes, ASSET_SHARE_COLUMNS, data.summary_total
    )
    return figures.create_asset_mix_figure(mix, MIX_LABELS)


def _mix_slot_values(data: DashboardData) -> dict:
    """자산 구성에서 지점 칸마다 갈아 끼울 값.

    칸이 셋이라 조합이 지점 수의 세제곱이다. Figure를 다 담을 수 없어
    값만 담는다(→ export_html, registry.VARIANTS_SLOT).

    막대 안에 적을 문구도 함께 담는다. 브라우저가 숫자만 바꾸면 막대 높이는
    새 지점인데 적힌 비중은 이전 지점 값으로 남는다. 문구를 만드는 규칙은
    화면과 같은 함수 한 곳에만 둔다.
    """
    columns = metrics.asset_mix_columns(data.summary, ASSET_SHARE_COLUMNS)
    values = {
        name: {
            "y": numbers,
            "text": [figures.share_label(value) for value in numbers],
        }
        for name, numbers in columns.items()
    }
    return {
        f"branch{index + 1}": values for index in range(MIX_SLOTS)
    }


def _mix_scatter(data: DashboardData, selection: dict):
    x_label = selection.get("x") or COMPARE_LABELS[0]
    y_label = selection.get("y") or COMPARE_LABELS[1]
    scatter = metrics.mix_scatter(
        data.summary, _MIX_BY_LABEL[x_label], _MIX_BY_LABEL[y_label]
    )
    return figures.create_mix_scatter_figure(scatter, x_label, y_label)


def _heatmap(data: DashboardData, selection: dict):
    scope = selection.get("scope") or TOTAL_LABEL
    matrix = metrics.change_matrix(
        data.asset_change,
        scope,
        (*ASSET_TYPES, ASSET_TYPE_TOTAL),
        data.asset_change_total,
    )
    return figures.create_change_heatmap_figure(matrix, scope)


def _pension(data: DashboardData, selection: dict):
    branch_name = selection.get("branch") or ""
    label = selection.get("product") or PENSION_PRODUCTS[0][0]
    measure = selection.get("measure") or PENSION_MEASURES[0][0]
    _, _prefix, assets, count = _PENSION_BY_LABEL[label]
    _, unit, to_text, to_delta, per_customer = _PENSION_MEASURE_BY_LABEL[
        measure
    ]
    trend = metrics.pension_trend(
        data.monthly,
        branch_name,
        assets,
        count,
        data.monthly_total,
        per_customer=per_customer,
    )
    return figures.create_pension_trend_figure(
        trend, branch_name, label, measure, unit, to_text, to_delta
    )


# --- 보조 문구 ---------------------------------------------------------------
def _start_month(data: DashboardData) -> str:
    months = data.months
    return months[0] if months else ""


def _branch_scope_text(data: DashboardData) -> str:
    month = fmt.format_month(reference_month(data))
    return f"{month} 기준 {len(data.branch_names)}개 지점"


def _table_rows(data: DashboardData, _selection: dict | None = None):
    return metrics.branch_table(
        data.monthly,
        data.summary,
        TABLE_FIELDS,
        reference_month(data),
        data.monthly_total,
        data.summary_total,
    )


def _table_text(data: DashboardData) -> str:
    month = fmt.format_month(reference_month(data))
    return f"{month} 기준 · 전체 1행과 지점 {len(data.branch_names)}행"


def _context(data: DashboardData) -> dict:
    return {
        "branch_names": list(data.branch_names),
        "branch_count": len(data.branch_names),
    }


TAB = Tab(
    value="asset",
    label="자산",
    build_context=_context,
    charts=(
        Chart(
            key="trend",
            title="자산 추이",
            build=_trend,
            selects=(
                BRANCH_SELECT,
                Select(
                    key="measure",
                    label="지표",
                    options=_measure_labels,
                    default=_first_measure,
                    kind=KIND_RADIO,
                ),
            ),
        ),
        Chart(
            key="growth",
            title="자산 규모 및 증가율",
            build=_growth,
            description=_branch_scope_text,
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
        Chart(
            key="mix",
            title="자산 구성",
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
            # 칸마다 지점을 고르므로 조합이 지점 수의 세제곱이다. 정적
            # HTML은 Figure 대신 숫자를 담고 그 자리만 갈아 끼운다.
            variants=VARIANTS_SLOT,
            slot_values=_mix_slot_values,
        ),
        Chart(
            key="mixscatter",
            title="자산 구성 비교",
            build=_mix_scatter,
            # 축을 고르는 칸이라 헤더가 아니라 그 축 옆에 둔다. 어느 축을
            # 바꾸는 칸인지 이름을 읽지 않아도 자리로 알 수 있다.
            selects=(
                Select(
                    key="x",
                    label="가로축",
                    options=_compare_labels,
                    default=lambda _data: COMPARE_LABELS[0],
                    place=PLACE_AXIS_X,
                ),
                Select(
                    key="y",
                    label="세로축",
                    options=_compare_labels,
                    default=lambda _data: COMPARE_LABELS[1],
                    place=PLACE_AXIS_Y,
                ),
            ),
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
        Chart(
            key="heatmap",
            title="자산 구성별 증감",
            build=_heatmap,
            selects=(
                Select(
                    key="scope",
                    label="구분",
                    options=_scopes,
                    default=_total_scope,
                ),
            ),
            # 색이 뜻하는 바를 따로 적지 않는다. 칸마다 부호를 붙인 숫자가
            # 있고 오른쪽 색 눈금이 증감율을 그대로 보여 준다. 색만으로
            # 구분하는 것이 아니므로 §5.2에 걸리지 않는다.
        ),
        Chart(
            key="pension",
            title="연금 추이",
            build=_pension,
            # 자산과 1인 평균을 모두 그리므로 제목에 지표를 적지 않는다.
            # 무엇을 그린 것인지는 축 이름이 알린다(→ 자산 추이 패널).
            selects=(
                BRANCH_SELECT,
                Select(
                    key="product",
                    label="상품",
                    options=_pension_labels,
                    default=_first_pension,
                    kind=KIND_RADIO,
                ),
                Select(
                    key="measure",
                    label="지표",
                    options=_pension_measure_labels,
                    default=_first_pension_measure,
                    kind=KIND_RADIO,
                ),
            ),
        ),
    ),
    tables=(
        Table(
            title="지점별 자산 현황",
            columns=TABLE_COLUMNS,
            build=_table_rows,
            description=_table_text,
            guide=TABLE_GUIDE,
        ),
    ),
)

__all__ = ["TAB", "TABLE_COLUMNS", "TABLE_FIELDS", "figures", "metrics"]
