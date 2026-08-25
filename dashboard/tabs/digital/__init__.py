"""디지털 채널 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.

**맨 위 드롭다운 하나가 이 탭의 카드 전체를 움직인다.** '전체'와 지점
27곳 중 하나를 고르면 표와 그림이 함께 그 대상을 가리킨다. 카드마다
컨트롤을 또 두면 두 값이 어긋나 한 화면에서 서로 다른 지점을 보여준다
(→ registry.Chart.follows_tab).

쓰는 원본 셋 —
- 디지털채널1(`digital_channel`·월별 프레임) — 채널별 이용 고객 수·비중과
  거래활성화율. 열세 달을 담는다.
- 디지털채널2(`digital_profile`) — 채널별 고객 특성. 가장 최근 달만 쓴다.
- 디지털채널3(`digital_usage_days`) — 이용일수 구간별 채널 이용 비중.
  원본이 가장 최근 달만 담고 있다.

카드 자리는 `order`로 적는다(→ registry.grid_order). 표와 차트를 번갈아
놓는 기본 규칙으로는 표가 맨 앞으로 가서 스케치와 자리가 달라진다.
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard import grid
from dashboard import figures as shared_figures
from dashboard.data import (
    DIGITAL_CHANNELS,
    DIGITAL_USAGE_DAY_GROUPS,
    TOTAL_LABEL,
    DashboardData,
)
from dashboard.tabs.digital import figures, metrics
from dashboard.tabs.registry import (
    KIND_RADIO,
    TABLE_PLACE_GRID,
    Chart,
    Select,
    Tab,
    Table,
)

ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"

# 원본이 아직 없을 때 그래프·표 자리에 적는 문구. 아무것도 없이 두면
# 고장인지 데이터가 없는 것인지 구분할 수 없다(→ AGENTS.md §11).
CHANNEL_EMPTY_NOTE = "디지털 채널 이용 원본이 아직 없습니다"
PROFILE_EMPTY_NOTE = "디지털 채널 고객 특성 원본이 아직 없습니다"
DAYS_EMPTY_NOTE = "디지털 채널 이용일수 원본이 아직 없습니다"

# --- 선택 컨트롤 -------------------------------------------------------------
SELECT_SCOPE = "scope"
SELECT_CHANNEL = "channel"


def _scope_names(data: DashboardData) -> list[str]:
    return metrics.scope_names(data)


def _default_scope(_data: DashboardData) -> str:
    return TOTAL_LABEL


# 맨 위 줄에 놓이는 탭 전체 선택. 이 탭의 표와 차트가 모두 이 값을 받는다.
#
# 이름을 '지점'이 아니라 '구분'으로 둔다. 고를 수 있는 값에 '전체'가
# 들어 있어 지점만 고르는 칸이 아니다(→ metrics.scope_names).
SCOPE_SELECT = Select(
    key=SELECT_SCOPE,
    label="구분",
    options=_scope_names,
    default=_default_scope,
)


def _channel_names(_data: DashboardData) -> list[str]:
    """고를 수 있는 채널. 이름은 데이터 계층이 정한다.

    여기 다시 적으면 한 화면 안에서 같은 채널이 다른 이름으로 나타난다
    (→ data.DIGITAL_CHANNELS).
    """
    return list(DIGITAL_CHANNELS)


def _first_channel(_data: DashboardData) -> str:
    return DIGITAL_CHANNELS[0]


def _channel_select() -> Select:
    """카드에 붙는 채널 선택. 값이 셋뿐이라 펼치지 않고 나란히 그린다.

    카드마다 따로 만든다. 한 Select를 두 카드가 나눠 쓰면 컴포넌트 ID는
    카드마다 달라도 선언이 같아 헷갈리므로, 자리마다 하나씩 둔다.
    """
    return Select(
        key=SELECT_CHANNEL,
        label="",
        options=_channel_names,
        default=_first_channel,
        kind=KIND_RADIO,
    )


def _chosen(selection: dict, key: str, fallback: str) -> str:
    """고른 값. 없거나 빈 값이면 기본값을 쓴다."""
    return selection.get(key) or fallback


# --- Figure 만들기 -----------------------------------------------------------
def _trend(data: DashboardData, selection: dict):
    scope = _chosen(selection, SELECT_SCOPE, TOTAL_LABEL)
    channel = _chosen(selection, SELECT_CHANNEL, DIGITAL_CHANNELS[0])
    trend = metrics.channel_trend(data, scope, channel)
    if trend.empty:
        return shared_figures.empty_figure(CHANNEL_EMPTY_NOTE)
    return figures.create_channel_trend_figure(trend, channel, scope)


def _activation(data: DashboardData, selection: dict):
    scope = _chosen(selection, SELECT_SCOPE, TOTAL_LABEL)
    channel = _chosen(selection, SELECT_CHANNEL, DIGITAL_CHANNELS[0])
    scatter = metrics.activation_scatter(data, channel)
    if scatter.empty:
        return shared_figures.empty_figure(CHANNEL_EMPTY_NOTE)
    return figures.create_activation_figure(scatter, channel, scope)


def _usage_days(data: DashboardData, selection: dict):
    scope = _chosen(selection, SELECT_SCOPE, TOTAL_LABEL)
    days = metrics.usage_days(data, scope, DIGITAL_CHANNELS)
    if days.empty:
        return shared_figures.empty_figure(DAYS_EMPTY_NOTE)
    return figures.create_usage_days_figure(
        days, DIGITAL_USAGE_DAY_GROUPS, scope
    )


# --- 이용고객 프로필 표 ------------------------------------------------------
# 행에 놓을 항목. (표준 컬럼, 화면 이름, 표기 함수) 순이며 여기 적은 차례가
# 화면 차례다. **항목마다 단위가 다르다** — 세·원·%. 컬럼 하나의 표기
# 함수로는 적을 수 없어 행이 자기 문구를 들고 간다(→ metrics.channel_profile,
# grid.MONEY_FORMAT).
def _won(value: object) -> str:
    """자산평균. 원본이 원 단위로 담는다(→ data.DIGITAL_PROFILE_*)."""
    return fmt.format_won(value, fmt.WON_PER_WON)


PROFILE_ITEMS: tuple[tuple[str, str, object], ...] = (
    ("average_age", "연령", fmt.format_age),
    ("average_assets_won", "자산평균", _won),
    ("domestic_stock_share", "국내주식비중", fmt.format_percent),
    ("overseas_stock_share", "해외주식비중", fmt.format_percent),
    ("etf_share", "국내ETF비중", fmt.format_percent),
    ("bond_share", "채권비중", fmt.format_percent),
    ("fund_share", "펀드비중", fmt.format_percent),
    ("pension_share", "개인연금비중", fmt.format_percent),
)

# 항목 이름 컬럼의 너비(px). 왼쪽에 고정해 가로로 스크롤해도 어느 항목의
# 값인지 보이게 한다.
ITEM_WIDTH = 150


def _channel_column(channel: str) -> grid.Column:
    """채널 하나의 표 컬럼.

    값은 숫자 그대로 담아 정렬이 정확하고, 보이는 글자는 행이 들고 온
    문구를 쓴다(→ grid.MONEY_FORMAT).
    """
    return grid.Column(
        field=channel.lower(),
        header=channel,
        min_width=110,
        to_text=str,
        js_format=grid.MONEY_FORMAT,
    )


PROFILE_COLUMNS: tuple[grid.Column, ...] = (
    grid.Column(
        field="item",
        header="항목",
        min_width=ITEM_WIDTH,
        to_text=str,
        width=ITEM_WIDTH,
        pinned=True,
        flex=0,
    ),
    *(_channel_column(channel) for channel in DIGITAL_CHANNELS),
)


def _profile_rows(data: DashboardData, selection: dict):
    """표의 '전체' 고정 행과 본문 행.

    이 표에는 위에 고정할 합계 행이 없다. 행이 지점이 아니라 항목이라
    더할 것이 없다.
    """
    scope = _chosen(selection, SELECT_SCOPE, TOTAL_LABEL)
    rows = metrics.channel_profile(
        data, scope, PROFILE_ITEMS, DIGITAL_CHANNELS
    )
    return None, rows


# --- 보조 문구 ---------------------------------------------------------------
def _month_text(data: DashboardData, frame_name: str, empty: str) -> str:
    """그 원본이 담은 가장 최근 달. 원본이 없으면 안내 문구."""
    frame = getattr(data, frame_name)
    if frame is None or frame.empty:
        return empty
    return f"{fmt.format_month(metrics.latest_month(frame))} 기준"


def _trend_text(data: DashboardData) -> str:
    if data.digital_channel.empty:
        return CHANNEL_EMPTY_NOTE
    months = sorted(data.digital_channel["base_month"].unique())
    return (
        f"{fmt.format_month(months[0])} ~ "
        f"{fmt.format_month(months[-1])}"
    )


def _activation_text(data: DashboardData) -> str:
    if data.digital_channel.empty:
        return CHANNEL_EMPTY_NOTE
    month = metrics.latest_month(data.digital_channel)
    return (
        f"{fmt.format_month(month)} 기준 · "
        f"지점 {len(data.branch_names)}곳"
    )


def _profile_text(data: DashboardData) -> str:
    return _month_text(data, "digital_profile", PROFILE_EMPTY_NOTE)


def _days_text(data: DashboardData) -> str:
    return _month_text(data, "digital_usage_days", DAYS_EMPTY_NOTE)


def _context(data: DashboardData) -> dict:
    return {
        "scope_names": metrics.scope_names(data),
        "channels": list(DIGITAL_CHANNELS),
    }


TAB = Tab(
    value="digital",
    label="디지털 채널",
    build_context=_context,
    # 맨 위 줄에 드롭다운 하나. 아래 카드 전체가 이 값을 받는다.
    selects=(SCOPE_SELECT,),
    charts=(
        # 상단 왼쪽 — 채널 하나를 골라 그 이용 고객 수와 비중을 함께 본다.
        Chart(
            key="trend",
            title="이용고객 추이",
            build=_trend,
            selects=(_channel_select(),),
            description=_trend_text,
            follows_tab=True,
            order=1,
        ),
        # 상단 오른쪽 — 이용 비중이 높은 지점이 실제로 더 거래하는지 본다.
        Chart(
            key="activation",
            title="채널 이용과 거래활성화",
            build=_activation,
            selects=(_channel_select(),),
            description=_activation_text,
            note=ZOOM_GUIDE,
            # 점이 몰린 구간을 들여다볼 수 있게 확대·축소를 켠다.
            zoomable=True,
            follows_tab=True,
            order=2,
        ),
        # 중단 오른쪽 — 세 채널을 한 그림에 겹쳐 이용일수 분포를 견준다.
        Chart(
            key="usage-days",
            title="이용일수 구간별 이용비중",
            build=_usage_days,
            description=_days_text,
            follows_tab=True,
            order=4,
        ),
    ),
    tables=(
        # 중단 왼쪽 — 행이 항목, 열이 채널이다. 채널마다 어떤 고객이
        # 쓰는지 한눈에 견준다.
        Table(
            title="이용고객 프로필",
            columns=PROFILE_COLUMNS,
            build=_profile_rows,
            description=_profile_text,
            # 행이 늘 여덟 개뿐이라 높이를 내용에 맞춘다.
            auto_height=True,
            # 행 차례가 항목 차례다. 헤더로 다시 세우면 그 뜻이 사라진다.
            sortable=False,
            place=TABLE_PLACE_GRID,
            order=3,
        ),
    ),
)

__all__ = [
    "CHANNEL_EMPTY_NOTE",
    "DAYS_EMPTY_NOTE",
    "PROFILE_COLUMNS",
    "PROFILE_EMPTY_NOTE",
    "PROFILE_ITEMS",
    "SCOPE_SELECT",
    "SELECT_CHANNEL",
    "SELECT_SCOPE",
    "TAB",
    "figures",
    "metrics",
]
