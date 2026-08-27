"""디지털 채널 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.

**카드마다 구분 드롭다운이 하나씩 있다.** '전체'와 지점 27곳 중 하나를
고르면 그 카드만 그 대상을 가리킨다. 카드끼리 서로 다른 지점을 놓고 견줄
수 있다. 다른 탭도 이렇게 카드 안에서 고른다(→ tabs.customer, tabs.product).

차트는 카드 헤더에 자기 컨트롤을 직접 단다(→ registry.Chart.selects).
표는 컨트롤을 직접 갖지 못해, 표마다 선택 줄을 하나씩 만들고 그 줄의
컨트롤을 표 카드 헤더 안에 넣는다(→ registry.PLACE_TABLE). 줄이 여섯이라도
컨트롤이 모두 카드 안에 있어 한 그리드에 나란히 놓인다
(→ registry.Tab.grid_rows).

쓰는 원본 넷 —
- 디지털채널1(`digital_channel`·월별 프레임) — 채널별 이용 고객 수·비중과
  거래활성화율. 열세 달을 담는다.
- 디지털채널2(`digital_profile`) — 채널별 고객 특성. 가장 최근 달만 쓴다.
- 디지털채널3(`digital_usage_days`) — 이용일수 구간별 채널 이용 비중.
  원본이 가장 최근 달만 담고 있다.
- 디지털채널4(`digital_menu_rank`) — 메뉴 분류별 이용 순위와 거래 전환
  비율. 원본이 가장 최근 달만 담고 있다.

**'공통고객' 분류는 화면에 '전체'로 적는다.** 원본이 담은 이름은 그대로 두고
보이는 글자만 갈아 끼운다(→ MENU_LABELS).

카드 자리는 `order`로 적는다(→ registry.grid_order). 표와 차트를 번갈아
놓는 기본 규칙으로는 표가 맨 앞으로 가서 스케치와 자리가 달라진다. 선택
줄이 여섯이라 줄마다 카드가 한 장씩인데, 그 번호로 그리드 전체를 다시
세운다(→ registry.row_order).
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard import grid
from dashboard import figures as shared_figures
from dashboard.data import (
    DIGITAL_CHANNELS,
    DIGITAL_MENU_CATEGORIES,
    DIGITAL_USAGE_DAY_GROUPS,
    TOTAL_LABEL,
    DashboardData,
)
from dashboard.tabs.digital import figures, metrics
from dashboard.tabs.registry import (
    KIND_RADIO,
    PLACE_TABLE,
    TABLE_PLACE_GRID,
    Chart,
    Select,
    Tab,
    Table,
)

ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"

# 세로축이 무엇을 잰 값인지. 축 이름('거래활성화(%)')만으로는 어느 기간의
# 무엇에 대한 비중인지 알 수 없다(→ registry.Chart.subtitle).
ACTIVATION_SUBTITLE = "거래활성화: 당월 거래고객 비중"

# 메뉴 두 카드의 제목 아래 줄. 분류 이름에 붙은 '선호형'이 어디서 온
# 말인지, 메뉴별 거래활성화가 무엇을 센 값인지 밝힌다.
MENU_SEGMENT_SUBTITLE = "고객세그먼트는 고객별 자산 분석으로 분류"
MENU_ACTIVATION_SUBTITLE = "해당 메뉴 조회고객의 당월 거래여부 분석"

# 메뉴 산점도 제목. 두 드롭다운이 무엇을 고르는 칸인지까지 제목에 잇는다.
MENU_SCATTER_TITLE = "앱 메뉴별 거래활성화 분석: 지점 X 고객 세그먼트별"

# 원본이 아직 없을 때 그래프·표 자리에 적는 문구. 아무것도 없이 두면
# 고장인지 데이터가 없는 것인지 구분할 수 없다(→ AGENTS.md §11).
CHANNEL_EMPTY_NOTE = "디지털 채널 이용 원본이 아직 없습니다"
PROFILE_EMPTY_NOTE = "디지털 채널 고객 특성 원본이 아직 없습니다"
DAYS_EMPTY_NOTE = "디지털 채널 이용일수 원본이 아직 없습니다"
MENU_EMPTY_NOTE = "디지털 채널 메뉴 순위 원본이 아직 없습니다"

# --- 메뉴 분류 이름 ----------------------------------------------------------
# 이 분류는 고객을 자산 구성으로 가른 세그먼트다. '공통고객'은 나머지
# 다섯과 나란한 하나의 분류이고 합계가 아니다(→ data 의 주석). 그래서
# 화면에는 '전체'가 아니라 '공통고객 전체'로 적는다.
#
# **값은 바꾸지 않는다** — 데이터를 고를 때는 원본 이름을 그대로 쓰고,
# 보이는 글자만 여기서 갈아 끼운다. 데이터 계층의 이름을 바꾸면 다른
# 원본과 맞물리는 자리가 함께 흔들린다(→ data.DIGITAL_MENU_CATEGORIES).
#
# 원본이 분류 이름을 바꾸면 이 표가 걸리지 않아 원본 이름이 그대로 나온다.
# 틀린 이름이 나오는 것보다 낫다.
MENU_TOTAL_CATEGORY = "공통고객"
MENU_LABELS: dict[str, str] = {
    MENU_TOTAL_CATEGORY: f"{MENU_TOTAL_CATEGORY} {TOTAL_LABEL}"
}

# 표 컬럼 헤더에만 붙이는 꼬리말. 순위표는 열이 여섯이라 머리글만으로 무엇을
# 가른 열인지 읽혀야 한다 — '국내주식'이라고만 적으면 그 상품의 메뉴 순위로
# 읽힌다. 드롭다운은 카드 제목이 세그먼트라고 말하고 있고 칸도 좁아 붙이지
# 않는다(→ MENU_COLUMNS, MENU_SELECT).
MENU_SEGMENT_SUFFIX = "선호형"


def menu_label(category: str) -> str:
    """화면에 적을 분류 이름. 드롭다운과 hover가 쓴다."""
    return MENU_LABELS.get(category, category)


def menu_column_header(category: str) -> str:
    """순위표 컬럼에 적을 분류 이름. 세그먼트 꼬리말이 붙는다."""
    if category in MENU_LABELS:
        return MENU_LABELS[category]
    return f"{category} {MENU_SEGMENT_SUFFIX}"


def menu_category(label: str) -> str:
    """화면 이름에서 되찾은 원본 분류 이름.

    고를 수 있는 값이 화면 이름이라, 데이터를 고르기 전에 원본 이름으로
    되돌린다.
    """
    for category, shown in MENU_LABELS.items():
        if shown == label:
            return category
    return label


# --- 선택 컨트롤 -------------------------------------------------------------
# 차트가 자기 헤더에 다는 컨트롤의 키. 컴포넌트 ID에 차트 키가 함께 들어가
# 네 차트가 같은 이름을 써도 겹치지 않는다(→ registry.Chart.select_id).
SELECT_SCOPE = "scope"
SELECT_CHANNEL = "channel"
SELECT_MENU = "menu"

# 표가 쓰는 선택 줄의 키. 이쪽은 탭 하나가 다 갖고 있어(→ Tab.selects)
# 표마다 다른 이름이어야 한다. 같은 이름을 두 줄이 쓰면 목록과 기본값이
# 한 칸으로 겹친다(→ Tab.option_map).
SELECT_PROFILE_SCOPE = "profile-scope"
SELECT_MENU_SCOPE = "menu-scope"

# 표 카드마다 선택 줄을 하나씩 만든다. 이름이 그 줄에 속한 표를 가른다
# (→ registry.DEFAULT_GROUP).
PROFILE_GROUP = "profile"
MENU_GROUP = "menu-rank"

# 컨트롤 이름을 '지점'이 아니라 '구분'으로 둔다. 고를 수 있는 값에 '전체'가
# 들어 있어 지점만 고르는 칸이 아니다(→ metrics.scope_names).
SCOPE_LABEL = "구분"


def _scope_names(data: DashboardData) -> list[str]:
    return metrics.scope_names(data)


def _default_scope(_data: DashboardData) -> str:
    return TOTAL_LABEL


def _scope_select() -> Select:
    """차트 카드 헤더에 붙는 구분 선택.

    카드마다 따로 만든다. 한 Select를 여러 카드가 나눠 써도 동작은 같지만,
    자리마다 하나씩 두어야 선언을 읽을 때 어느 카드의 칸인지 분명하다
    (→ _channel_select).
    """
    return Select(
        key=SELECT_SCOPE,
        label=SCOPE_LABEL,
        options=_scope_names,
        default=_default_scope,
    )


def _table_scope_select(key: str, group: str) -> Select:
    """표 카드 헤더 안에 넣는 구분 선택.

    표는 자기 컨트롤을 갖지 못한다(→ registry.Table). 대신 그 표만 있는
    선택 줄을 만들고 컨트롤을 카드 안으로 넣어, 차트 카드와 같은 자리에
    같은 모양으로 나타나게 한다(→ registry.PLACE_TABLE).
    """
    return Select(
        key=key,
        label=SCOPE_LABEL,
        options=_scope_names,
        default=_default_scope,
        place=PLACE_TABLE,
        group=group,
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


def _menu_names(_data: DashboardData) -> list[str]:
    """고를 수 있는 메뉴 분류. 차례는 데이터 계층이 정한다.

    '공통고객'은 '전체'로 적는다. 고르는 값도 화면 이름이라, 데이터를 고르기
    전에 원본 이름으로 되돌린다(→ menu_category).
    """
    return [menu_label(name) for name in DIGITAL_MENU_CATEGORIES]


def _first_menu(_data: DashboardData) -> str:
    return menu_label(DIGITAL_MENU_CATEGORIES[0])


# 메뉴 분류 선택. 값이 여섯이라 라디오로 늘어놓으면 카드 헤더를 넘어간다.
# 채널 셋과 달리 펼쳐 고르는 드롭다운을 쓴다(→ _channel_select).
MENU_SELECT = Select(
    key=SELECT_MENU,
    label="",
    options=_menu_names,
    default=_first_menu,
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


def _menu_scatter(data: DashboardData, selection: dict):
    scope = _chosen(selection, SELECT_SCOPE, TOTAL_LABEL)
    label = _chosen(
        selection, SELECT_MENU, menu_label(DIGITAL_MENU_CATEGORIES[0])
    )
    scatter = metrics.menu_scatter(data, scope, menu_category(label))
    if scatter.empty:
        return shared_figures.empty_figure(MENU_EMPTY_NOTE)
    return figures.create_menu_scatter_figure(scatter, label, scope)


# --- 이용고객 프로필 표 ------------------------------------------------------
# 행에 놓을 항목. (표준 컬럼, 화면 이름, 표기 함수) 순이며 여기 적은 차례가
# 화면 차례다. **항목마다 단위가 다르다** — 세·원·%. 컬럼 하나의 표기
# 함수로는 적을 수 없어 행이 자기 문구를 들고 간다(→ metrics.channel_profile,
# grid.MONEY_FORMAT).
#
# 자산평균만 억원 숫자로 적는다. 원본은 원 단위로 담는데
# (→ data.DIGITAL_PROFILE_*) 조·억·만으로 풀어 쓰면 세 채널이
# '1억 9,074만원'·'4,297만원'처럼 자리 이름이 달라, 한 행에 나란히 놓고도
# 어느 채널이 몇 배인지 바로 읽히지 않는다. 단위는 행 이름이 말한다.
PROFILE_ITEMS: tuple[tuple[str, str, object], ...] = (
    ("average_age", "연령", fmt.format_age),
    ("average_assets_won", "자산평균(억원)", fmt.format_won_as_100m),
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

    고른 값은 이 표만의 선택 줄에서 온다(→ SELECT_PROFILE_SCOPE).
    """
    scope = _chosen(selection, SELECT_PROFILE_SCOPE, TOTAL_LABEL)
    rows = metrics.channel_profile(
        data, scope, PROFILE_ITEMS, DIGITAL_CHANNELS
    )
    return None, rows


# --- 메뉴 이용순위 표 --------------------------------------------------------
# 순위 컬럼 폭(px). 두 자리 숫자만 들어가므로 남는 폭을 나눠 갖지 않는다.
RANK_WIDTH = 76

# 메뉴 이름 컬럼의 최소 폭(px). 여섯이 나란히 서므로 좁으면 이름이
# 말줄임(…)으로 잘린다.
MENU_WIDTH = 118

# 아래 두 카드의 높이. 순위가 서른까지 있어 기본 높이(360px)로는 몇 줄만
# 보인다. **두 곳에 같은 값을 쓴다** — 표와 산점도가 한 줄에 나란히 서므로
# 한쪽만 높이면 아랫선이 어긋난다(→ registry.Chart.height).
MENU_CARD_HEIGHT = "560px"


def _menu_field(index: int) -> str:
    """메뉴 분류 하나가 쓰는 표 컬럼 이름.

    분류 이름이 한글이라 그대로 컬럼 이름으로 쓰지 않고 자리 번호로 만든다.
    원본이 분류 이름을 바꿔도 컬럼 이름은 그대로다.
    """
    return f"menu{index + 1}"


# (원본 분류 이름, 표 컬럼 이름) 짝. 계산 쪽이 이 표를 보고 셀을 채운다
# (→ metrics.menu_rank_table).
MENU_FIELDS: tuple[tuple[str, str], ...] = tuple(
    (category, _menu_field(index))
    for index, category in enumerate(DIGITAL_MENU_CATEGORIES)
)

MENU_COLUMNS: tuple[grid.Column, ...] = (
    grid.Column(
        field="menu_rank",
        header="순위",
        min_width=RANK_WIDTH,
        to_text=fmt.format_number,
        js_format=grid.NUMBER_FORMAT,
        width=RANK_WIDTH,
        flex=0,
    ),
    *(
        grid.Column(
            field=field,
            header=menu_column_header(category),
            min_width=MENU_WIDTH,
            to_text=str,
        )
        for category, field in MENU_FIELDS
    ),
)


def _menu_rank_rows(data: DashboardData, selection: dict):
    """표의 '전체' 고정 행과 본문 행.

    이 표에는 위에 고정할 합계 행이 없다. 행이 지점이 아니라 순위라 더할
    것이 없다.

    고른 값은 이 표만의 선택 줄에서 온다(→ SELECT_MENU_SCOPE).
    """
    scope = _chosen(selection, SELECT_MENU_SCOPE, TOTAL_LABEL)
    rows = metrics.menu_rank_table(data, scope, MENU_FIELDS)
    return None, rows


# --- 보조 문구 ---------------------------------------------------------------
def _month_text(data: DashboardData, frame_name: str, empty: str) -> str:
    """원본을 읽지 못했을 때의 안내 문구. 읽었으면 아무것도 적지 않는다.

    기준 월은 화면 제목 밑에 한 번 있으므로 카드마다 다시 적지 않는다
    (→ layout._page_header). 원본이 비면 왜 비었는지는 알려야 한다
    (→ AGENTS.md §11).
    """
    frame = getattr(data, frame_name)
    if frame is None or frame.empty:
        return empty
    return ""


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


def _menu_text(data: DashboardData) -> str:
    return _month_text(data, "digital_menu_rank", MENU_EMPTY_NOTE)


def _context(data: DashboardData) -> dict:
    return {
        "scope_names": metrics.scope_names(data),
        "channels": list(DIGITAL_CHANNELS),
        "menu_names": _menu_names(data),
    }


TAB = Tab(
    value="digital",
    label="디지털 채널",
    build_context=_context,
    # 표 카드의 구분 선택. 표는 자기 컨트롤을 갖지 못해 표마다 줄을 하나씩
    # 만들고 컨트롤을 그 표 카드 헤더 안에 넣는다(→ _table_scope_select).
    # 차트는 자기 선언에 직접 단다.
    selects=(
        _table_scope_select(SELECT_PROFILE_SCOPE, PROFILE_GROUP),
        _table_scope_select(SELECT_MENU_SCOPE, MENU_GROUP),
    ),
    charts=(
        # 상단 왼쪽 — 채널 하나를 골라 그 이용 고객 수와 비중을 함께 본다.
        Chart(
            key="trend",
            title="채널이용 고객 추이",
            build=_trend,
            selects=(_scope_select(), _channel_select()),
            description=_trend_text,
            order=1,
        ),
        # 상단 오른쪽 — 이용 비중이 높은 지점이 실제로 더 거래하는지 본다.
        Chart(
            key="activation",
            title="지점별 채널이용X거래활성화 분석",
            subtitle=ACTIVATION_SUBTITLE,
            build=_activation,
            selects=(_scope_select(), _channel_select()),
            description=_activation_text,
            note=ZOOM_GUIDE,
            # 점이 몰린 구간을 들여다볼 수 있게 확대·축소를 켠다.
            zoomable=True,
            order=2,
        ),
        # 중단 오른쪽 — 세 채널을 한 그림에 겹쳐 이용일수 분포를 견준다.
        Chart(
            key="usage-days",
            title="이용일수 구간별 거래활성화",
            subtitle=ACTIVATION_SUBTITLE,
            build=_usage_days,
            selects=(_scope_select(),),
            description=_days_text,
            order=4,
        ),
        # 하단 오른쪽 — 많이 보는 메뉴가 실제로 거래까지 이어지는지 본다.
        # 한 점이 메뉴 하나이고, 분류를 골라 그 분류의 메뉴만 그린다.
        Chart(
            key="menu-scatter",
            title=MENU_SCATTER_TITLE,
            subtitle=MENU_ACTIVATION_SUBTITLE,
            build=_menu_scatter,
            selects=(_scope_select(), MENU_SELECT),
            description=_menu_text,
            note=ZOOM_GUIDE,
            # 점이 몰린 구간을 들여다볼 수 있게 확대·축소를 켠다.
            zoomable=True,
            height=MENU_CARD_HEIGHT,
            order=6,
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
            group=PROFILE_GROUP,
            order=3,
        ),
        # 하단 왼쪽 — 행이 순위, 열이 메뉴 분류다. 분류마다 무엇을 많이
        # 보는지 한눈에 견준다.
        Table(
            title="앱 메뉴 이용 순위: 고객 세그먼트별",
            key="menu-rank",
            columns=MENU_COLUMNS,
            build=_menu_rank_rows,
            description=_menu_text,
            subtitle=MENU_SEGMENT_SUBTITLE,
            # 행 차례가 순위 차례다. 헤더로 다시 세우면 그 뜻이 사라진다.
            sortable=False,
            place=TABLE_PLACE_GRID,
            height=MENU_CARD_HEIGHT,
            group=MENU_GROUP,
            order=5,
        ),
    ),
)

__all__ = [
    "CHANNEL_EMPTY_NOTE",
    "ACTIVATION_SUBTITLE",
    "MENU_ACTIVATION_SUBTITLE",
    "MENU_SCATTER_TITLE",
    "MENU_SEGMENT_SUBTITLE",
    "MENU_SEGMENT_SUFFIX",
    "MENU_TOTAL_CATEGORY",
    "menu_column_header",
    "DAYS_EMPTY_NOTE",
    "MENU_CARD_HEIGHT",
    "MENU_COLUMNS",
    "MENU_EMPTY_NOTE",
    "MENU_FIELDS",
    "MENU_GROUP",
    "MENU_LABELS",
    "MENU_SELECT",
    "PROFILE_COLUMNS",
    "PROFILE_EMPTY_NOTE",
    "PROFILE_GROUP",
    "PROFILE_ITEMS",
    "SCOPE_LABEL",
    "SELECT_CHANNEL",
    "SELECT_MENU",
    "SELECT_MENU_SCOPE",
    "SELECT_PROFILE_SCOPE",
    "SELECT_SCOPE",
    "TAB",
    "figures",
    "menu_category",
    "menu_label",
    "metrics",
]
