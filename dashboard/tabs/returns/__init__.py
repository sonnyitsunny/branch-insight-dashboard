"""수익률 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.

쓰는 원본 — 지점별 수익률(지점 × 기준월의 1년·3년 수익률). 값은 이미
%이며 손실이 난 기간에는 음수다(→ dashboard/sources/branch_return.py).
아랫줄 왼쪽은 수익률 그룹별 비중 원본을 쓴다. 이쪽은 수익률이 아니라
그 구간에 든 고객의 비중(%)이다(→ dashboard/sources/return_group.py).
그 오른쪽부터는 `수익률_seg_...` 원본 일곱을 쓴다. 고객을 자산 규모·상품
비중·회전율·연령으로 갈라 그 무리의 수익률을 본다. 카드 모양이 모두 같아
선언표 하나로 만든다(→ SEGMENT_CARDS,
dashboard/sources/segment_return.py).

'전체' 행은 지점 수익률의 합도 평균도 아니라 따로 계산된 값이다. 모든 그림이
지점과 색을 달리해 함께 보여주고 되계산하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from dashboard import figures as shared_figures
from dashboard import format as fmt
from dashboard.data import (
    ASSET_GROUPS,
    BALANCE_SHARE_GROUPS,
    RETURN_AGE_GROUPS,
    RETURN_PERIODS,
    STOCK_TURNOVER_GROUPS,
    DashboardData,
    reference_month,
)
from dashboard.tabs.registry import KIND_RADIO, Chart, Select, Tab
from dashboard.tabs.returns import figures, metrics

ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"

# 원본이 아직 없을 때 그래프 자리에 적는 문구. 아무것도 없이 두면 고장인지
# 데이터가 없는 것인지 구분할 수 없다(→ AGENTS.md §11).
EMPTY_NOTE = "수익률 원본이 아직 없습니다"
# 구간별 비중은 다른 원본을 쓴다. 한쪽만 없을 수 있어 문구를 따로 둔다.
GROUP_EMPTY_NOTE = "수익률 그룹별 비중 원본이 아직 없습니다"

# --- 고를 수 있는 기간 -------------------------------------------------------
# 기간 이름은 데이터 계층이 정한다(→ data.RETURN_PERIODS). 그룹별 비중
# 원본도 같은 이름을 쓰므로 여기 다시 적으면 한 탭 안에서 같은 기간이 다른
# 이름으로 나타난다. 라디오는 라벨을 그리지 않지만 카드 제목이 '수익률'을
# 말하므로 기간 이름만으로 읽힌다.
#
# 여기서는 그 기간이 지점별 수익률 프레임의 어느 컬럼인지만 짝지어 둔다.
_COLUMN_BY_PERIOD: dict[str, str] = {
    RETURN_PERIODS[0]: "return_1y",
    RETURN_PERIODS[1]: "return_3y",
}


def measure_label(period: str) -> str:
    """축 이름과 hover에 적을 지표 이름.

    한 곳에서 만들어 두 그림의 이름이 갈라지지 않게 한다.
    """
    return f"{period} 수익률"


# 산점도의 두 축. 가로가 첫 기간(1년), 세로가 둘째 기간(3년)이다.
# 목록에서 가져오므로 기간 이름을 고치면 축 이름과 hover도 따라간다.
SCATTER_X_PERIOD = RETURN_PERIODS[0]
SCATTER_Y_PERIOD = RETURN_PERIODS[1]
SCATTER_X_COLUMN = _COLUMN_BY_PERIOD[SCATTER_X_PERIOD]
SCATTER_Y_COLUMN = _COLUMN_BY_PERIOD[SCATTER_Y_PERIOD]

# 산점도 카드 제목. 두 축이 무엇인지 제목에 적는다. 기간 이름을 고치면
# 축·hover와 함께 따라가도록 위 상수에서 만든다.
SCATTER_TITLE = (
    "영업점 수익률 분석"
    f" ({measure_label(SCATTER_X_PERIOD)}"
    f" X {measure_label(SCATTER_Y_PERIOD)})"
)

# 순위 막대 카드의 제목 아래 줄. 막대 값이 무엇을 잰 것인지 세로축
# 이름('1년 수익률(%)')만으로는 지점 하나의 값인지 그 지점 고객들의
# 평균인지 알 수 없다(→ registry.Chart.subtitle).
RANK_SUBTITLE = "단위: 고객 투자수익률 평균"

# --- 가로 스크롤 -------------------------------------------------------------
# 막대 하나가 차지할 폭과 축·여백에 드는 폭(px). 지점이 28곳이면 그래프가
# 카드보다 넓어지므로 카드 안에서 가로로 스크롤한다
# (→ registry.Chart.scroll_width).
#
# 막대 폭을 줄이면 스크롤은 짧아지지만 눈금의 지점 이름과 막대 위 값이
# 옆 칸과 붙는다.
RANK_BAR_WIDTH = 46
# 세로축 눈금·이름과 좌우 여백. figures의 margin과 같은 자리를 가리킨다.
RANK_SIDE_WIDTH = 120


def _rank_width(data: DashboardData) -> str:
    """지점 수에 맞춘 그래프 폭.

    원본이 없으면 비운다. 안내 문구만 있는 빈 그래프를 넓게 늘리면 문구가
    카드 밖으로 밀려 나간다.
    """
    rows = len(data.branch_return) + len(data.branch_return_total)
    if not rows:
        return ""
    return f"{RANK_SIDE_WIDTH + rows * RANK_BAR_WIDTH}px"


# --- 선택 목록 ---------------------------------------------------------------
def _period_labels(_data: DashboardData) -> list[str]:
    return list(RETURN_PERIODS)


def _first_period(_data: DashboardData) -> str:
    return RETURN_PERIODS[0]


PERIOD_SELECT = Select(
    key="period",
    label="기간",
    options=_period_labels,
    default=_first_period,
    kind=KIND_RADIO,
)


def _branch_names(data: DashboardData) -> list[str]:
    return list(data.branch_names)


def _first_branch(data: DashboardData) -> str:
    names = data.branch_names
    return names[0] if names else ""


# 구간별 비중 그림에서 '전체'와 견줄 지점. '전체'는 늘 그리므로 목록에
# 넣지 않는다. 넣으면 같은 막대가 두 번 나온다.
BRANCH_SELECT = Select(
    key="branch",
    label="영업점",
    options=_branch_names,
    default=_first_branch,
)


# --- Figure 만들기 -----------------------------------------------------------
def _period_of(selection: dict) -> tuple[str, str]:
    """고른 기간과 그 표준 컬럼. 값이 없거나 모르는 값이면 첫 기간을 쓴다."""
    period = selection.get("period") or RETURN_PERIODS[0]
    if period not in _COLUMN_BY_PERIOD:
        period = RETURN_PERIODS[0]
    return period, _COLUMN_BY_PERIOD[period]


def _rank(data: DashboardData, selection: dict):
    period, column = _period_of(selection)
    rank = metrics.return_rank(
        data.branch_return, data.branch_return_total, column
    )
    if rank.empty:
        return shared_figures.empty_figure(EMPTY_NOTE)
    return figures.create_return_rank_figure(rank, measure_label(period))


def _scatter(data: DashboardData, _selection: dict):
    scatter = metrics.return_scatter(
        data.branch_return,
        data.branch_return_total,
        SCATTER_X_COLUMN,
        SCATTER_Y_COLUMN,
    )
    if scatter.empty:
        return shared_figures.empty_figure(EMPTY_NOTE)
    return figures.create_return_scatter_figure(
        scatter,
        measure_label(SCATTER_X_PERIOD),
        measure_label(SCATTER_Y_PERIOD),
    )


def _group(data: DashboardData, selection: dict):
    period, _column = _period_of(selection)
    branch_name = selection.get("branch") or ""
    distribution = metrics.return_group_distribution(
        data.return_group,
        data.return_group_total,
        branch_name,
        period,
    )
    if distribution.empty:
        return shared_figures.empty_figure(GROUP_EMPTY_NOTE)
    return figures.create_return_group_figure(distribution, branch_name)


# --- 구간별 수익률 카드 ------------------------------------------------------
# `수익률_seg_...` 원본 일곱은 가르는 기준만 다르고 모양이 같다. 카드도
# 제목·축 이름·구간 목록만 다르므로, 카드마다 함수를 쓰지 않고 여기 한 줄씩
# 적어 만든다. 원본이 하나 더 들어오면 이 표에 한 줄 더한다.
#
# 계산은 `metrics.segment_returns`, 그림은
# `figures.create_segment_return_figure`가 함께 맡는다.
@dataclass(frozen=True)
class SegmentCard:
    """구간별 수익률 카드 하나의 선언.

    `frame`은 `DashboardData`의 프레임 이름이고, '전체' 행은 같은 이름의
    `_total` 프레임에서 온다(→ data.DashboardData.total_of).
    `direction`은 구간 축을 읽는 방향을 적은 문구다. 구간 차례가 무엇을
    뜻하는지 카드마다 다르므로 여기 적는다.

    `vertical`을 켜면 막대가 세로로 선다. 구간 이름이 짧아 가로축 눈금에
    눕히지 않고 들어가는 카드에 쓴다. 기본은 가로 막대다
    (→ figures.create_segment_return_figure).

    `subtitle`은 제목 아래 줄이다. 구간을 가른 값 자체에 단서가 붙는
    카드에만 적는다. 비우면 그리지 않는다(→ registry.Chart.subtitle).
    """

    key: str
    title: str
    label: str
    frame: str
    group_column: str
    groups: tuple[str, ...]
    axis_title: str
    direction: str
    vertical: bool = False
    subtitle: str = ""

    @property
    def empty_note(self) -> str:
        """원본이 없을 때 그래프 자리에 적는 문구."""
        return f"{self.label} 원본이 아직 없습니다"


SEGMENT_CARDS: tuple[SegmentCard, ...] = (
    SegmentCard(
        key="asset",
        title="자산 규모 구간별 수익률",
        label="자산규모별 수익률",
        frame="asset_return",
        group_column="asset_group",
        groups=ASSET_GROUPS,
        axis_title="자산 규모 구간",
        direction="위에서 아래로 자산 규모가 커진다",
    ),
    SegmentCard(
        key="stock-share",
        title="국내주식 비중 구간별 수익률",
        label="국내주식비중별 수익률",
        frame="stock_share_return",
        group_column="stock_share_group",
        groups=BALANCE_SHARE_GROUPS,
        axis_title="국내주식 잔고 비중 구간",
        direction="위에서 아래로 국내주식 비중이 높아진다",
    ),
    SegmentCard(
        key="overseas-share",
        title="해외주식 비중 구간별 수익률",
        label="해외주식비중별 수익률",
        frame="overseas_share_return",
        group_column="overseas_share_group",
        groups=BALANCE_SHARE_GROUPS,
        axis_title="해외주식 잔고 비중 구간",
        direction="위에서 아래로 해외주식 비중이 높아진다",
    ),
    SegmentCard(
        key="etf-share",
        title="ETF 비중 구간별 수익률",
        label="ETF비중별 수익률",
        frame="etf_share_return",
        group_column="etf_share_group",
        groups=BALANCE_SHARE_GROUPS,
        axis_title="ETF 잔고 비중 구간",
        direction="위에서 아래로 ETF 비중이 높아진다",
    ),
    SegmentCard(
        key="pension-share",
        title="개인연금 비중 구간별 수익률",
        label="개인연금비중별 수익률",
        frame="pension_share_return",
        group_column="pension_share_group",
        groups=BALANCE_SHARE_GROUPS,
        axis_title="개인연금 잔고 비중 구간",
        direction="위에서 아래로 개인연금 비중이 높아진다",
    ),
    SegmentCard(
        key="stock-turnover",
        title="국내주식 회전율 구간별 수익률",
        label="국내주식회전율별 수익률",
        frame="stock_turnover_return",
        group_column="stock_turnover_group",
        groups=STOCK_TURNOVER_GROUPS,
        axis_title="국내주식 회전율 구간",
        direction="위에서 아래로 회전율이 높아진다",
        subtitle="국내주식 회전율은 1개월 기준",
    ),
    # 연령대만 세로 막대다. 구간 이름이 `10대이하`처럼 짧아 가로축에
    # 눕히지 않고 들어간다.
    SegmentCard(
        key="age",
        title="연령대별 수익률",
        label="연령대별 수익률",
        frame="age_return",
        group_column="return_age_group",
        groups=RETURN_AGE_GROUPS,
        axis_title="연령대",
        direction="왼쪽에서 오른쪽으로 나이가 많아진다",
        vertical=True,
    ),
)


def _segment_build(card: SegmentCard):
    """그 카드의 Figure를 만드는 함수."""

    def build(data: DashboardData, selection: dict):
        period, column = _period_of(selection)
        branch_name = selection.get("branch") or ""
        distribution = metrics.segment_returns(
            getattr(data, card.frame),
            data.total_of(card.frame),
            branch_name,
            card.group_column,
            card.groups,
            column,
        )
        if distribution.empty:
            return shared_figures.empty_figure(card.empty_note)
        return figures.create_segment_return_figure(
            distribution,
            branch_name,
            card.axis_title,
            measure_label(period),
            vertical=card.vertical,
        )

    return build


def _segment_text(card: SegmentCard):
    """그 카드의 보조 문구를 만드는 함수."""

    def text(data: DashboardData) -> str:
        if getattr(data, card.frame).empty:
            return card.empty_note
        month = fmt.format_month(reference_month(data))
        return f"{month} 기준 · {card.direction}"

    return text


def _segment_chart(card: SegmentCard) -> Chart:
    """선언 하나를 차트 카드로 만든다. 일곱 카드가 같은 컨트롤을 쓴다."""
    return Chart(
        key=card.key,
        title=card.title,
        build=_segment_build(card),
        subtitle=card.subtitle,
        selects=(PERIOD_SELECT, BRANCH_SELECT),
        description=_segment_text(card),
    )


# --- 보조 문구 ---------------------------------------------------------------
def _scatter_text(data: DashboardData) -> str:
    """산점도 카드의 보조 문구.

    원본을 읽지 못했을 때만 왜 비었는지 알린다(→ AGENTS.md §11). 그림이
    그려지면 아무것도 적지 않는다 — 기준 월은 화면 제목 밑에 한 번 있고,
    어느 축이 어느 기간인지는 카드 제목이 말한다(→ SCATTER_TITLE).
    """
    if data.branch_return.empty:
        return EMPTY_NOTE
    return ""


def _group_text(data: DashboardData) -> str:
    """구간별 비중 카드의 보조 문구. 무엇과 무엇을 견주는지 적는다."""
    if data.return_group.empty:
        return GROUP_EMPTY_NOTE
    month = fmt.format_month(reference_month(data))
    return f"{month} 기준 · 전체와 고른 영업점 비교"


def _context(data: DashboardData) -> dict:
    return {
        "branch_names": list(data.branch_names),
        "branch_count": len(data.branch_names),
    }


TAB = Tab(
    value="return",
    label="수익률",
    build_context=_context,
    charts=(
        Chart(
            key="rank",
            title="영업점 수익률 분석",
            subtitle=RANK_SUBTITLE,
            build=_rank,
            selects=(PERIOD_SELECT,),
            scroll_width=_rank_width,
        ),
        Chart(
            key="scatter",
            title=SCATTER_TITLE,
            build=_scatter,
            description=_scatter_text,
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
        # 앞의 둘이 한 줄을 채우므로 이 카드가 둘째 줄 왼쪽에 놓인다
        # (→ assets/style.css 의 차트 그리드).
        Chart(
            key="group",
            title="수익률 구간별 고객 비중",
            build=_group,
            selects=(PERIOD_SELECT, BRANCH_SELECT),
            description=_group_text,
        ),
        # 둘째 줄 오른쪽부터는 구간별 수익률 카드가 이어진다. 카드마다
        # 자기 선택을 가지므로 한 카드의 지점을 바꿔도 옆 카드는 그대로다
        # (→ registry.Chart).
        *(_segment_chart(card) for card in SEGMENT_CARDS),
    ),
)

__all__ = [
    "BRANCH_SELECT",
    "EMPTY_NOTE",
    "GROUP_EMPTY_NOTE",
    "PERIOD_SELECT",
    "RANK_SUBTITLE",
    "SEGMENT_CARDS",
    "SCATTER_TITLE",
    "SCATTER_X_COLUMN",
    "SCATTER_X_PERIOD",
    "SCATTER_Y_COLUMN",
    "SCATTER_Y_PERIOD",
    "SegmentCard",
    "TAB",
    "figures",
    "measure_label",
    "metrics",
]


# 산점도는 축이 둘뿐이라 기간도 둘을 전제로 한다. 기간이 늘면 어느 둘을
# 놓을지 정해야 하므로, 늘어난 것을 모르고 지나가지 않게 여기서 확인한다.
if len(RETURN_PERIODS) != 2:  # pragma: no cover - 설정 확인
    raise ValueError(
        "수익률 산점도는 기간 두 개를 전제로 합니다. "
        f"현재 기간: {', '.join(RETURN_PERIODS)}. "
        "dashboard/tabs/returns/__init__.py 의 산점도 축을 함께 "
        "고쳐 주세요."
    )
