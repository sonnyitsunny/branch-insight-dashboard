"""상담 탭 선언.

무엇을 보여줄지 여기에 한 번만 적는다. Dash 화면과 정적 HTML이 이 선언을
함께 읽는다(→ dashboard/tabs/registry.py).

탭 맨 위의 지점·기준월 선택은 이 탭 전체에 걸린다. 표 셋이 같은 값을 받아
같은 지점·같은 달을 보여준다.

상담구분의 값 이름은 여기 적지 않는다. 원본에 있는 값마다 표를 하나씩
그리므로, 분류가 늘거나 이름이 바뀌어도 이 파일을 고치지 않는다.
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard.data import TOTAL_LABEL, DashboardData, reference_month
from dashboard.grid import NUMBER_FORMAT, PERCENT_FORMAT, Column
from dashboard.tabs.consulting import metrics
from dashboard.tabs.registry import Select, Tab, Table

# 표의 조작 안내. 켜 둔 기능만 적는다(→ grid.DEFAULT_COL_DEF).
# 이 표는 정렬을 끈다. 번호 순서가 원본이 매긴 순위라 다시 세우면 그 뜻이
# 사라진다.
TABLE_GUIDE = "번호 순 · 경계 드래그로 너비 조절 · 행 클릭 강조"

# 보여줄 행이 없을 때의 안내. 원본을 못 읽으면 지점·기준월 목록까지 비어
# 아무 반응이 없는 화면이 된다. 그때 왜 비었는지 여기서 알린다.
EMPTY_NOTE = (
    "상담 원본을 읽지 못했습니다."
    " 상담1.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)

# 선택 컨트롤 키. 콜백과 정적 HTML이 같은 이름을 쓴다.
SELECT_BRANCH = "branch"
SELECT_MONTH = "month"

# 지점 칸에 적는 이름. '지점'이 아니라 '구분'으로 둔다. 고를 수 있는 값에
# '전체'가 들어 있어 지점만 고르는 칸이 아니다(→ metrics.scope_names).
BRANCH_LABEL = "구분"

# 표를 나누는 기준 컬럼. 이 컬럼의 값마다 표가 하나씩 생기고 값이 제목이 된다.
GROUP_FIELD = "consulting_type"

# 번호 컬럼 폭(px). 한 자리 숫자만 들어가므로 남는 폭을 나눠 갖지 않는다.
RANK_COLUMN_WIDTH = 90

TABLE_COLUMNS = (
    Column(
        field="topic_rank",
        header="번호",
        min_width=RANK_COLUMN_WIDTH,
        to_text=fmt.format_number,
        js_format=NUMBER_FORMAT,
        width=RANK_COLUMN_WIDTH,
        flex=0,
    ),
    Column(
        field="topic",
        header="토픽",
        min_width=160,
        to_text=str,
        flex=2,
    ),
    # 문장이 들어가는 칸이라 남는 폭을 가장 많이 갖는다. 좁으면 말줄임(…)
    # 으로 잘린다.
    Column(
        field="topic_summary",
        header="주요내용",
        min_width=260,
        to_text=str,
        flex=5,
    ),
    Column(
        field="topic_share",
        header="비중",
        min_width=110,
        to_text=fmt.format_percent,
        js_format=PERCENT_FORMAT,
    ),
)


# --- 선택 목록 ---------------------------------------------------------------
def _branch_names(data: DashboardData) -> list[str]:
    return metrics.scope_names(
        data.consulting, data.consulting_total, TOTAL_LABEL
    )


def _default_branch(data: DashboardData) -> str:
    names = _branch_names(data)
    return TOTAL_LABEL if TOTAL_LABEL in names else (
        names[0] if names else ""
    )


def _months(data: DashboardData) -> list[str]:
    return metrics.months(data.consulting)


def _default_month(data: DashboardData) -> str:
    """첫 화면의 기준월. 화면 전체의 기준 월과 같으면 그 달을 쓴다."""
    available = _months(data)
    if not available:
        return ""
    current = reference_month(data)
    return current if current in available else available[0]


# --- 표 만들기 ---------------------------------------------------------------
def _table_rows(data: DashboardData, selection: dict):
    """고른 지점·기준월의 행. 표를 나누기 전의 전체 목록이다.

    선택이 비어 있으면 첫 화면의 기본값을 쓴다. 표를 몇 개 그릴지 셀 때도
    이 함수를 부르기 때문이다(→ registry.Table.groups).
    """
    branch_name = selection.get(SELECT_BRANCH) or _default_branch(data)
    base_month = selection.get(SELECT_MONTH) or _default_month(data)
    rows = metrics.consulting_rows(
        data.consulting,
        data.consulting_total,
        branch_name,
        base_month,
        TOTAL_LABEL,
    )
    # 상담 표에는 합계 행이 없다. 토픽은 더할 수 있는 값이 아니다.
    return None, rows


def _table_text(data: DashboardData) -> str:
    """카드 오른쪽 위 문구.

    원본을 못 읽으면 지점·기준월 목록까지 비어 아무 반응이 없는 화면이
    된다. 그때 왜 비었는지 여기서 알린다(→ AGENTS.md §11).
    """
    if data.consulting.empty and data.consulting_total.empty:
        return EMPTY_NOTE
    return ""


def _context(data: DashboardData) -> dict:
    return {
        "branch_names": _branch_names(data),
        "months": _months(data),
    }


TAB = Tab(
    value="consulting",
    label="상담",
    build_context=_context,
    selects=(
        Select(
            key=SELECT_BRANCH,
            label=BRANCH_LABEL,
            options=_branch_names,
            default=_default_branch,
        ),
        Select(
            key=SELECT_MONTH,
            label="기준월",
            options=_months,
            default=_default_month,
        ),
    ),
    tables=(
        Table(
            # 제목은 상담구분 값이 채운다. 여기 적은 값은 원본에 분류가
            # 없을 때만 쓰인다.
            title="상담 토픽",
            columns=TABLE_COLUMNS,
            build=_table_rows,
            description=_table_text,
            guide=TABLE_GUIDE,
            group_field=GROUP_FIELD,
            auto_height=True,
            # 번호가 원본이 매긴 순위다. 헤더로 다시 세우면 그 뜻이
            # 사라지므로 정렬을 끈다.
            sortable=False,
        ),
    ),
)

__all__ = ["TAB", "TABLE_COLUMNS", "metrics"]
