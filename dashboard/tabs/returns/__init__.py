"""수익률 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.

쓰는 원본 — 지점별 수익률(지점 × 기준월의 1년·3년 수익률). 값은 이미
%이며 손실이 난 기간에는 음수다(→ dashboard/sources/branch_return.py).

'전체' 행은 지점 수익률의 합도 평균도 아니라 따로 계산된 값이다. 두 그림
모두 지점과 색을 달리해 함께 보여주고 되계산하지 않는다.
"""

from __future__ import annotations

from dashboard import figures as shared_figures
from dashboard import format as fmt
from dashboard.data import DashboardData, reference_month
from dashboard.tabs.registry import KIND_RADIO, Chart, Select, Tab
from dashboard.tabs.returns import figures, metrics

ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"

# 원본이 아직 없을 때 그래프 자리에 적는 문구. 아무것도 없이 두면 고장인지
# 데이터가 없는 것인지 구분할 수 없다(→ AGENTS.md §11).
EMPTY_NOTE = "수익률 원본이 아직 없습니다"

# --- 고를 수 있는 기간 -------------------------------------------------------
# (라디오에 보일 이름, 표준 컬럼). 라디오는 라벨을 그리지 않으므로 이름만
# 보고도 무엇인지 알 수 있어야 한다. 카드 제목이 '수익률'을 말하므로
# 여기서는 기간만 적는다.
RETURN_PERIODS: tuple[tuple[str, str], ...] = (
    ("1년", "return_1y"),
    ("3년", "return_3y"),
)
_COLUMN_BY_PERIOD = dict(RETURN_PERIODS)


def measure_label(period: str) -> str:
    """축 이름과 hover에 적을 지표 이름.

    한 곳에서 만들어 두 그림의 이름이 갈라지지 않게 한다.
    """
    return f"{period} 수익률"


# 산점도의 두 축. 가로가 1년, 세로가 3년이다. 위 목록에서 가져오므로 기간
# 이름을 고치면 축 이름과 hover도 함께 따라간다.
SCATTER_X_PERIOD, SCATTER_X_COLUMN = RETURN_PERIODS[0]
SCATTER_Y_PERIOD, SCATTER_Y_COLUMN = RETURN_PERIODS[1]

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
    return [period for period, _column in RETURN_PERIODS]


def _first_period(_data: DashboardData) -> str:
    return RETURN_PERIODS[0][0]


PERIOD_SELECT = Select(
    key="period",
    label="기간",
    options=_period_labels,
    default=_first_period,
    kind=KIND_RADIO,
)


# --- Figure 만들기 -----------------------------------------------------------
def _period_of(selection: dict) -> tuple[str, str]:
    """고른 기간과 그 표준 컬럼. 값이 없거나 모르는 값이면 첫 기간을 쓴다."""
    period = selection.get("period") or RETURN_PERIODS[0][0]
    if period not in _COLUMN_BY_PERIOD:
        period = RETURN_PERIODS[0][0]
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


# --- 보조 문구 ---------------------------------------------------------------
def _scatter_text(data: DashboardData) -> str:
    """산점도 카드의 보조 문구. 기간·지점 수는 데이터에서 읽는다."""
    if data.branch_return.empty:
        return EMPTY_NOTE
    month = fmt.format_month(reference_month(data))
    return (
        f"{month} 기준 · 가로 {SCATTER_X_PERIOD} · "
        f"세로 {SCATTER_Y_PERIOD} · 지점 {len(data.branch_return)}곳"
    )


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
            title="지점 수익률 순위",
            build=_rank,
            selects=(PERIOD_SELECT,),
            scroll_width=_rank_width,
        ),
        Chart(
            key="scatter",
            title="장단기 수익률 비교",
            build=_scatter,
            description=_scatter_text,
            note=ZOOM_GUIDE,
            zoomable=True,
        ),
    ),
)

__all__ = [
    "EMPTY_NOTE",
    "RETURN_PERIODS",
    "SCATTER_X_COLUMN",
    "SCATTER_X_PERIOD",
    "SCATTER_Y_COLUMN",
    "SCATTER_Y_PERIOD",
    "TAB",
    "figures",
    "measure_label",
    "metrics",
]


# 산점도는 축이 둘뿐이라 기간도 둘을 전제로 한다. 기간이 늘면 어느 둘을
# 놓을지 정해야 하므로, 늘어난 것을 모르고 지나가지 않게 여기서 확인한다.
if len(RETURN_PERIODS) != 2:  # pragma: no cover - 설정 확인
    raise ValueError(
        "장단기 수익률 비교는 기간 두 개를 전제로 합니다. "
        f"현재 기간: {', '.join(p for p, _ in RETURN_PERIODS)}. "
        "dashboard/tabs/returns/__init__.py 의 산점도 축을 함께 "
        "고쳐 주세요."
    )
