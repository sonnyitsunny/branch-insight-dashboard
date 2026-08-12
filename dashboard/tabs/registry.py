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
from itertools import product
from typing import Callable

# 차트를 그리는 함수. (데이터, 선택값 묶음) -> Figure
# 선택 컨트롤이 없는 차트는 빈 dict를 받는다.
BuildFigure = Callable[[object, dict], object]

# 선택 목록을 만드는 함수. 데이터 -> 고를 수 있는 값들
BuildOptions = Callable[[object], list[str]]

# 카드 오른쪽 위 보조 문구를 만드는 함수. 데이터 -> 문구
BuildText = Callable[[object], str]

# 표의 행을 만드는 함수. 데이터 -> (전체 행, 지점 행들)
BuildRows = Callable[[object], tuple[dict, object]]

# 선택 컨트롤 모양.
KIND_DROPDOWN = "dropdown"
KIND_RADIO = "radio"

# 정적 HTML이 선택 조합을 담는 방식.
#   product — 조합마다 Figure를 통째로 미리 담는다. 조합 수가 적을 때 쓴다.
#   slot    — 선택 하나가 그래프의 한 자리만 바꾸는 경우. Figure를 조합마다
#             담으면 27×27×27처럼 폭발하므로, 값만 담아 두고 브라우저에서
#             그 자리의 숫자를 갈아 끼운다(→ export_html).
VARIANTS_PRODUCT = "product"
VARIANTS_SLOT = "slot"


@dataclass(frozen=True)
class Select:
    """차트에 붙는 선택 컨트롤 하나의 선언."""

    key: str
    label: str
    options: BuildOptions
    default: Callable[[object], str]
    kind: str = KIND_DROPDOWN


@dataclass(frozen=True)
class Chart:
    """차트 카드 하나의 선언.

    `selects`를 주면 컨트롤이 순서대로 붙고, 고를 수 있는 값마다 Figure를
    만들 수 있다. 정적 HTML은 그 값들을 미리 만들어 문서에 담는다.

    `slot_values`는 `variants=slot`일 때 쓴다. 데이터를 받아
    {선택 키: {선택값: [그 자리에 들어갈 숫자들]}} 를 돌려준다.
    """

    key: str
    title: str
    build: BuildFigure
    selects: tuple[Select, ...] = ()
    description: BuildText | None = None
    note: str = ""
    zoomable: bool = False
    variants: str = VARIANTS_PRODUCT
    slot_values: Callable[[object], dict] | None = None

    def chart_id(self, tab_value: str) -> str:
        return f"{tab_value}-{self.key}-chart"

    def select_id(self, tab_value: str, select_key: str) -> str:
        return f"{tab_value}-{self.key}-{select_key}-select"

    def defaults(self, data: object) -> dict[str, str]:
        """첫 화면에 고를 값. 기본값이 목록에 없으면 목록의 첫 값을 쓴다."""
        chosen: dict[str, str] = {}
        for select in self.selects:
            options = list(select.options(data))
            value = select.default(data)
            if value not in options:
                value = options[0] if options else ""
            chosen[select.key] = value
        return chosen

    def option_map(self, data: object) -> dict[str, list[str]]:
        return {
            select.key: list(select.options(data)) for select in self.selects
        }

    def combinations(self, data: object) -> list[dict[str, str]]:
        """정적 HTML이 미리 담아야 할 선택 조합.

        `variants=slot`이면 조합을 담지 않는다. 브라우저가 값만 갈아
        끼우므로 Figure는 첫 화면 것 하나면 된다.
        """
        if not self.selects or self.variants == VARIANTS_SLOT:
            return []
        options = self.option_map(data)
        keys = [select.key for select in self.selects]
        return [
            dict(zip(keys, values))
            for values in product(*(options[key] for key in keys))
        ]


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


def variant_key(selection: dict[str, str]) -> str:
    """선택 조합을 정적 HTML이 찾아 쓸 문자열 키로 만든다."""
    return "|".join(str(value) for value in selection.values())
