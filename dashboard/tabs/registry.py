"""탭 등록표의 자료형.

탭 하나가 무엇을 보여주는지 여기 정의한 형태로 한 번만 선언한다.
Dash 화면(`layout`·`callbacks`)과 정적 HTML(`export_html`)이 그 선언을
함께 읽으므로, 제목이나 선택 목록을 두 곳에 적을 자리가 없다.
두 산출물이 갈라지는 일을 구조로 막는 것이 이 모듈의 목적이다.

컴포넌트 ID는 직접 적지 않고 탭 값과 차트 키에서 만든다. 탭이 늘어도
ID가 겹치지 않고, 이름 규칙이 프로젝트 전체에서 같아진다(→ AGENTS.md §6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# 차트를 그리는 함수. (데이터, 선택값) -> Figure
# 선택 컨트롤이 없는 차트는 선택값으로 None을 받는다.
BuildFigure = Callable[[object, str | None], object]

# 선택 목록을 만드는 함수. 데이터 -> 고를 수 있는 값들
BuildOptions = Callable[[object], list[str]]

# 카드 오른쪽 위 보조 문구를 만드는 함수. 데이터 -> 문구
BuildText = Callable[[object], str]

# 표의 행을 만드는 함수. 데이터 -> (전체 행, 지점 행들)
BuildRows = Callable[[object], tuple[dict, object]]


@dataclass(frozen=True)
class Chart:
    """차트 카드 하나의 선언.

    `options`를 주면 선택 컨트롤이 붙고, 고를 수 있는 값마다 Figure를
    만들 수 있다. 정적 HTML은 그 값들을 미리 다 만들어 문서에 담는다.
    """

    key: str
    title: str
    build: BuildFigure
    options: BuildOptions | None = None
    default: Callable[[object], str] | None = None
    description: BuildText | None = None
    note: str = ""
    zoomable: bool = False

    def chart_id(self, tab_value: str) -> str:
        return f"{tab_value}-{self.key}-chart"

    def select_id(self, tab_value: str) -> str:
        return f"{tab_value}-{self.key}-select"


@dataclass(frozen=True)
class Table:
    """상세 표 하나의 선언.

    `columns`는 `dashboard.grid.Column` 목록이다. 화면의 AgGrid와 정적
    HTML 표가 같은 목록을 읽으므로 컬럼 순서·표기가 어긋나지 않는다.
    """

    title: str
    columns: tuple
    build: BuildRows
    description: BuildText | None = None
    guide: str = ""

    def table_id(self, tab_value: str) -> str:
        return f"{tab_value}-table"


@dataclass(frozen=True)
class Tab:
    """탭 하나의 선언.

    `charts`가 비어 있고 `table`이 없으면 아직 구현하지 않은 탭이다.
    화면에는 이름만 비활성으로 나타난다.
    """

    value: str
    label: str
    charts: tuple[Chart, ...] = ()
    table: Table | None = None
    build_context: Callable[[object], dict] = field(
        default=lambda data: {}
    )

    @property
    def implemented(self) -> bool:
        return bool(self.charts) or self.table is not None
