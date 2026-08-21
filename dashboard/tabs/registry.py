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
from itertools import product, zip_longest
from typing import Callable

# 차트를 그리는 함수. (데이터, 선택값 묶음) -> Figure
# 선택 컨트롤이 없는 차트는 빈 dict를 받는다.
BuildFigure = Callable[[object, dict], object]

# 선택 목록을 만드는 함수. 데이터 -> 고를 수 있는 값들
BuildOptions = Callable[[object], list[str]]

# 카드 오른쪽 위 보조 문구를 만드는 함수. 데이터 -> 문구
BuildText = Callable[[object], str]

# 표의 행을 만드는 함수. (데이터, 선택값 묶음) -> (전체 행, 지점 행들)
# 선택에 따라 내용이 바뀌지 않는 표는 빈 dict를 받는다.
BuildRows = Callable[[object, dict], tuple[dict, object]]

# 선택 컨트롤 모양.
KIND_DROPDOWN = "dropdown"
KIND_RADIO = "radio"

# 선택 컨트롤을 카드 어디에 그릴지.
#   header — 카드 헤더 오른쪽. 대부분의 컨트롤이 여기 놓인다.
#   axis-x — 그래프 오른쪽 아래. 가로축을 고르는 칸을 그 축 옆에 둔다.
#   axis-y — 그래프 왼쪽 위. 세로축을 고르는 칸을 그 축 옆에 둔다.
#
# 축 옆 컨트롤은 그래프 위에 겹쳐 놓는다. 자리를 따로 만들면 그 카드만
# 높아져 옆 카드와 차트 시작선이 어긋난다(→ assets/style.css).
PLACE_HEADER = "header"
PLACE_AXIS_X = "axis-x"
PLACE_AXIS_Y = "axis-y"

# 선택 줄의 컨트롤을 어디에 그릴지(→ Tab.select_groups).
#   기본  — 그 줄의 카드들 위에 한 줄로 놓는다.
#   table — 그 줄 첫 표 카드의 헤더 안에 놓는다. 카드가 표 하나뿐인 줄에서
#           줄을 따로 만들지 않고 카드 안에 넣을 때 쓴다.
#
# 카드 헤더는 높이가 고정이라 세 줄이 들어가지 않는다. 컨트롤을 넣으면
# 조작 안내를 빼고 상태 문구만 남긴다(→ layout._table_header_right).
PLACE_TABLE = "table"

# 표를 화면 어디에 놓을지.
#   full — 화면 폭 전체를 쓰는 상세 표. 차트 아래에 쌓인다(→ AGENTS.md §4.1).
#   grid — 차트 그리드 안. 차트와 나란히 한 칸을 차지한다.
#
# 그리드 안의 순서는 `grid_order`가 정한다. 두 자료형이 따로 선언되어
# 서로의 순서를 적을 자리가 없으므로, 순서를 규칙으로 고정해 두 산출물이
# 같은 자리에 그리게 한다(→ layout, export_html).
TABLE_PLACE_FULL = "full"
TABLE_PLACE_GRID = "grid"

# 그리드 한 칸의 종류(→ grid_order).
GRID_TABLE = "table"
GRID_CHART = "chart"

# 선택 줄이 걸리는 범위(→ Tab.groups).
#
# 이름을 비우면 탭 맨 위 줄이고 그 탭의 카드 전체에 걸린다. 이름을 주면 같은
# 이름을 가진 표·차트 위에 줄이 하나 더 생기고 그 카드들만 움직인다. 한 탭에
# 서로 다른 원본을 나란히 놓을 때, 줄마다 따로 고를 수 있게 한다.
#
# 그룹을 나누면 정적 HTML이 담을 조합도 그룹 안에서만 곱해진다. 한 줄로 묶어
# 두면 선택 두 개의 조합이 28×28이 되어 담을 수 없다(→ export_html).
DEFAULT_GROUP = ""

# 정적 HTML이 선택 조합을 담는 방식.
#   product — 조합마다 Figure를 통째로 미리 담는다. 조합 수가 적을 때 쓴다.
#   slot    — 선택 하나가 그래프의 한 자리만 바꾸는 경우. Figure를 조합마다
#             담으면 27×27×27처럼 폭발하므로, 값만 담아 두고 브라우저에서
#             그 자리의 숫자를 갈아 끼운다(→ export_html).
VARIANTS_PRODUCT = "product"
VARIANTS_SLOT = "slot"


@dataclass(frozen=True)
class Select:
    """차트에 붙는 선택 컨트롤 하나의 선언.

    `place`로 카드 어디에 그릴지 정한다. 기본은 카드 헤더 오른쪽이다.
    """

    key: str
    label: str
    options: BuildOptions
    default: Callable[[object], str]
    kind: str = KIND_DROPDOWN
    place: str = PLACE_HEADER
    # 탭 맨 위 줄에 놓을 때는 비워 둔다. 이름을 주면 같은 이름을 가진
    # 표·차트 위에 이 컨트롤만의 줄이 생긴다(→ DEFAULT_GROUP).
    group: str = DEFAULT_GROUP


@dataclass(frozen=True)
class Chart:
    """차트 카드 하나의 선언.

    `selects`를 주면 컨트롤이 순서대로 붙고, 고를 수 있는 값마다 Figure를
    만들 수 있다. 정적 HTML은 그 값들을 미리 만들어 문서에 담는다.

    `slot_values`는 `variants=slot`일 때 쓴다. 데이터를 받아
    {선택 키: {선택값: [그 자리에 들어갈 숫자들]}} 를 돌려준다.

    `follows_tab`을 켜면 탭 전체 선택(→ `Tab.selects`)을 그대로 받는다.
    표와 차트가 같은 지점을 함께 보여줘야 할 때 쓴다. 컨트롤을 카드마다
    또 두면 두 값이 어긋나 서로 다른 지점을 보여주게 된다.

    `height`는 그래프 높이(CSS 길이)다. 비우면 모든 차트가 함께 쓰는
    `layout.CHART_HEIGHT`를 따른다. 칸이 많아 기본 높이로는 글씨가
    들어가지 않는 그림에서만 적는다. 옆에 나란히 서는 카드가 있으면
    그 카드에도 같은 값을 적어야 아랫선이 맞는다(→ `Table.height`).
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
    follows_tab: bool = False
    height: str = ""
    # 어느 선택 줄을 따르는지(→ DEFAULT_GROUP).
    group: str = DEFAULT_GROUP

    @property
    def header_selects(self) -> tuple[Select, ...]:
        """카드 헤더 오른쪽에 그리는 컨트롤."""
        return tuple(
            select
            for select in self.selects
            if select.place == PLACE_HEADER
        )

    @property
    def axis_selects(self) -> tuple[Select, ...]:
        """그래프 위 축 옆에 겹쳐 그리는 컨트롤."""
        return tuple(
            select
            for select in self.selects
            if select.place != PLACE_HEADER
        )

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

    선택에 따라 컬럼 이름이 달라지는 표는 `columns`에 목록 대신 함수를
    준다. 선택값 묶음을 받아 그때의 목록을 돌려주며, 화면은 콜백이
    `columnDefs`도 함께 내보내고 정적 HTML은 값마다 컬럼 이름을 담아 두고
    갈아 끼운다(→ callbacks, export_html). 컬럼 수와 순서는 선택이 바뀌어도
    같아야 한다. 자리가 달라지면 정렬해 둔 순서와 조절해 둔 너비가 어긋난다.

    `key`는 한 탭에 표가 둘 이상일 때 ID를 가르는 이름이다. 하나뿐이면
    비워 둔다.

    `group_field`를 주면 그 컬럼의 값마다 표를 하나씩 그리고 값이 표 제목이
    된다. 값 목록은 데이터에서 읽으므로, 분류 이름을 선언에 적지 않는다.
    그러면 원본의 분류가 늘거나 이름이 바뀌어도 코드를 고치지 않는다.

    `auto_height`를 켜면 표 높이를 행 수에 맞춘다. 행이 늘 몇 개뿐인 표는
    고정 높이를 주면 아래가 빈 채로 남는다.

    `sortable`을 끄면 헤더를 눌러도 다시 세우지 않는다. 행 순서 자체가
    뜻을 갖는 표(예: 원본이 매긴 번호)는 순서를 바꾸면 그 뜻이 사라진다.

    원본이 없어 표가 비면 왜 비었는지 `description`으로 알린다. 아무것도
    없이 두면 고장인지 데이터가 없는 것인지 구분할 수 없다(→ AGENTS.md
    §11). 그 문구는 탭 모듈이 만든다.

    `place`를 `grid`로 두면 화면 폭 전체가 아니라 차트 그리드 안에 놓여
    차트와 나란히 선다(→ TABLE_PLACE_GRID).

    `height`는 표가 스크롤하는 높이(CSS 길이)다. 비우면 자리에 따른
    기본값을 따른다(→ `layout.table_style`). 나란히 서는 차트의 높이를
    바꿨을 때 그 값을 여기에도 적어 아랫선을 맞춘다(→ `Chart.height`).
    `auto_height`를 켠 표에는 뜻이 없다.
    """

    title: str
    columns: tuple
    build: BuildRows
    description: BuildText | None = None
    guide: str = ""
    key: str = ""
    group_field: str = ""
    auto_height: bool = False
    sortable: bool = True
    place: str = TABLE_PLACE_FULL
    height: str = ""
    # 어느 선택 줄을 따르는지(→ DEFAULT_GROUP).
    group: str = DEFAULT_GROUP

    @property
    def in_grid(self) -> bool:
        return self.place == TABLE_PLACE_GRID

    @property
    def dynamic_columns(self) -> bool:
        """선택에 따라 컬럼 이름이 달라지는 표인지."""
        return callable(self.columns)

    def columns_of(self, selection: dict | None = None) -> tuple:
        """그 선택에서 쓸 컬럼 목록.

        고정 목록이면 그대로 돌려준다. 부르는 쪽은 어느 쪽인지 모르고
        써도 된다.
        """
        if not self.dynamic_columns:
            return self.columns
        return self.columns(selection or {})

    def table_id(self, tab_value: str, index: int = 0) -> str:
        """표 하나의 컴포넌트 ID.

        표가 하나뿐인 탭은 예전과 같은 `<탭>-table`을 그대로 쓴다.
        """
        name = f"{tab_value}-{self.key}" if self.key else tab_value
        return f"{name}-table" if not self.group_field else (
            f"{name}-table-{index + 1}"
        )

    def groups(self, data: object) -> list[str]:
        """표를 나눌 값 목록. 나누지 않으면 빈 이름 하나.

        원본에 나온 순서를 그대로 쓴다. 가나다순으로 다시 세우면 원본이
        의도한 순서(예: 상담 유형 순)가 사라진다.
        """
        if not self.group_field:
            return [""]
        _total, rows = self.build(data, {})
        if rows is None or len(rows) == 0:
            return []
        return list(dict.fromkeys(rows[self.group_field].tolist()))


@dataclass(frozen=True)
class SelectGroup:
    """선택 줄 하나와 그 줄이 움직이는 카드들.

    선언에서 만들어지는 값이라 탭 모듈이 직접 적지 않는다. 같은 `group`
    이름을 가진 컨트롤·표·차트를 묶은 것이다(→ Tab.select_groups).

    `key`는 컴포넌트 ID와 정적 HTML의 DOM 이름을 만드는 이름이다. 기본
    그룹은 탭 값을 그대로 써서, 줄이 하나뿐이던 탭의 ID가 달라지지 않는다.
    """

    tab_value: str
    name: str
    selects: tuple[Select, ...]
    tables: tuple[Table, ...]
    charts: tuple[Chart, ...]

    @property
    def key(self) -> str:
        if not self.name:
            return self.tab_value
        return f"{self.tab_value}-{self.name}"

    @property
    def grid_tables(self) -> tuple[Table, ...]:
        return tuple(table for table in self.tables if table.in_grid)

    @property
    def full_tables(self) -> tuple[Table, ...]:
        return tuple(table for table in self.tables if not table.in_grid)

    @property
    def row_selects(self) -> tuple[Select, ...]:
        """카드들 위에 한 줄로 그리는 컨트롤."""
        return tuple(
            select
            for select in self.selects
            if select.place != PLACE_TABLE
        )

    @property
    def table_selects(self) -> tuple[Select, ...]:
        """첫 표 카드의 헤더 안에 그리는 컨트롤(→ PLACE_TABLE)."""
        return tuple(
            select
            for select in self.selects
            if select.place == PLACE_TABLE
        )

    @property
    def followers(self) -> tuple[Chart, ...]:
        """이 줄의 선택을 따르는 차트(→ Chart.follows_tab)."""
        return tuple(chart for chart in self.charts if chart.follows_tab)

    def select_id(self, select_key: str) -> str:
        return f"{self.key}-{select_key}-select"

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

        이 줄의 컨트롤만 곱한다. 탭의 컨트롤을 모두 곱하면 줄이 둘일 때
        조합이 28×28로 불어난다(→ DEFAULT_GROUP).
        """
        if not self.selects:
            return []
        options = self.option_map(data)
        keys = [select.key for select in self.selects]
        return [
            dict(zip(keys, values))
            for values in product(*(options[key] for key in keys))
        ]


@dataclass(frozen=True)
class Tab:
    """탭 하나의 선언.

    `charts`가 비어 있고 `tables`가 없으면 아직 구현하지 않은 탭이다.
    화면에는 이름만 비활성으로 나타난다.

    `selects`는 탭 전체에 걸리는 선택 컨트롤이다. 탭 맨 위에 한 줄로 놓이며
    그 탭의 모든 표가 같은 값을 받는다. 차트마다 붙는 컨트롤과 함께 쓸 수
    있다(→ AGENTS.md §4.1).
    """

    value: str
    label: str
    charts: tuple[Chart, ...] = ()
    tables: tuple[Table, ...] = ()
    selects: tuple[Select, ...] = ()
    build_context: Callable[[object], dict] = field(
        default=lambda data: {}
    )

    @property
    def implemented(self) -> bool:
        return bool(self.charts) or bool(self.tables)

    @property
    def grid_tables(self) -> tuple[Table, ...]:
        """차트와 나란히 그리드 안에 놓는 표."""
        return tuple(table for table in self.tables if table.in_grid)

    @property
    def full_tables(self) -> tuple[Table, ...]:
        """화면 폭 전체를 쓰는 표. 차트 아래에 쌓인다."""
        return tuple(table for table in self.tables if not table.in_grid)

    @property
    def followers(self) -> tuple[Chart, ...]:
        """선택 줄을 따르는 차트(→ Chart.follows_tab)."""
        return tuple(chart for chart in self.charts if chart.follows_tab)

    @property
    def select_groups(self) -> tuple[SelectGroup, ...]:
        """선택 줄과 그 줄이 움직이는 카드들. 선언에 나온 순서다.

        컨트롤·표·차트를 `group` 이름으로 묶는다. 이름을 아무 데도 적지
        않은 탭은 줄 하나짜리 그룹 하나가 되어 지금까지와 같다
        (→ DEFAULT_GROUP).
        """
        names: list[str] = []
        for item in (*self.selects, *self.tables, *self.charts):
            if item.group not in names:
                names.append(item.group)
        return tuple(
            SelectGroup(
                tab_value=self.value,
                name=name,
                selects=tuple(
                    item for item in self.selects if item.group == name
                ),
                tables=tuple(
                    item for item in self.tables if item.group == name
                ),
                charts=tuple(
                    item for item in self.charts if item.group == name
                ),
            )
            for name in names or [DEFAULT_GROUP]
        )

    @property
    def grid_rows(self) -> tuple[tuple[SelectGroup, ...], ...]:
        """한 그리드에 함께 놓는 선택 줄들. 선언에 나온 순서다.

        선택 줄은 보통 자기 그리드를 하나 연다. 카드들 위에 컨트롤 한 줄이
        놓이고 그 아래 그리드가 오기 때문이다.

        컨트롤을 카드 안에 넣은 줄(→ PLACE_TABLE)은 카드 위에 놓을 것이
        없다. 그래서 자기 그리드를 열지 않고 앞의 그런 줄과 한 그리드에
        이어 붙는다. 표 하나짜리 줄이 둘이면 두 표가 나란히 선다.
        """
        rows: list[list[SelectGroup]] = []
        for group in self.select_groups:
            joins = (
                bool(rows)
                and not group.row_selects
                and not rows[-1][-1].row_selects
            )
            if joins:
                rows[-1].append(group)
            else:
                rows.append([group])
        return tuple(tuple(row) for row in rows)

    def select_id(self, select_key: str) -> str:
        return f"{self.value}-{select_key}-select"

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
        """정적 HTML이 미리 담아야 할 탭 선택 조합.

        표의 내용이 선택에 따라 바뀌므로, 서버가 없는 정적 HTML은 고를 수
        있는 조합의 행을 모두 담아 두고 보이기만 바꾼다(→ export_html).
        """
        if not self.selects:
            return []
        options = self.option_map(data)
        keys = [select.key for select in self.selects]
        return [
            dict(zip(keys, values))
            for values in product(*(options[key] for key in keys))
        ]


def grid_order(tables: list, charts: tuple) -> list[tuple[str, object]]:
    """차트 그리드에 놓을 순서. 표와 차트를 번갈아 놓는다.

    그리드는 두 칸씩 한 줄이므로(→ assets/style.css) 표와 차트가 짝을
    이뤄 한 줄에 나란히 선다. 표를 모두 앞에 몰면 표끼리 한 줄, 차트끼리
    다음 줄이 되어 짝이 갈라진다.

    수가 맞지 않으면 남는 것을 뒤에 붙인다. 표가 없는 탭은 차트만 순서대로
    놓이므로 지금까지와 같다.

    `tables`에 무엇이 들었는지는 부르는 쪽이 정한다. 화면은 계산이 끝난
    카드를, 정적 HTML은 (번호, 카드) 쌍을 넣는다. 여기서는 순서만 정하고
    내용은 건드리지 않는다.
    """
    order: list[tuple[str, object]] = []
    for table, chart in zip_longest(tables, charts):
        if table is not None:
            order.append((GRID_TABLE, table))
        if chart is not None:
            order.append((GRID_CHART, chart))
    return order


def variant_key(selection: dict[str, str]) -> str:
    """선택 조합을 정적 HTML이 찾아 쓸 문자열 키로 만든다."""
    return "|".join(str(value) for value in selection.values())
