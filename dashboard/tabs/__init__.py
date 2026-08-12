"""탭 등록표.

탭을 추가하려면 이 폴더에 모듈을 하나 만들고 아래 `TABS`에 한 줄 더한다.
Dash 화면과 정적 HTML이 이 목록을 함께 읽으므로 두 곳을 따로 고칠 일이
없다. 아직 만들지 않은 탭은 `TAB_ORDER`에만 두면 이름이 비활성으로
나타난다.

탭 순서는 `TAB_ORDER`가 정한다. 구현 여부와 순서를 한 곳에서 보게 해서,
구현한 탭을 목록에서 빼는 일을 잊지 않도록 한다.
"""

from __future__ import annotations

from dashboard.tabs import asset, customer
from dashboard.tabs.registry import (
    KIND_DROPDOWN,
    KIND_RADIO,
    Chart,
    Select,
    Table,
    Tab,
    variant_key,
)

# 구현한 탭. 각 모듈이 내놓는 선언을 그대로 담는다.
TABS: tuple[Tab, ...] = (customer.TAB, asset.TAB)

# 화면에 보여줄 탭 순서와 이름. 구현하지 않은 탭도 여기 적어 두면
# 이름만 비활성으로 나타난다. 업무 영역이 확정되면 값과 이름을 고친다.
TAB_ORDER: tuple[tuple[str, str], ...] = (
    ("customer", "고객"),
    ("asset", "자산"),
    ("product", "상품"),
    ("transaction", "거래"),
    ("return", "수익률"),
    ("app", "앱 이용"),
    ("consulting", "상담"),
)

_BY_VALUE = {tab.value: tab for tab in TABS}


def find(value: str) -> Tab | None:
    """구현한 탭을 값으로 찾는다. 없으면 None."""
    return _BY_VALUE.get(value)


def default_value() -> str:
    """처음 열리는 탭. 구현한 탭 중 순서상 가장 앞에 있는 것."""
    for value, _label in TAB_ORDER:
        if value in _BY_VALUE:
            return value
    return TAB_ORDER[0][0] if TAB_ORDER else ""


__all__ = [
    "TABS",
    "TAB_ORDER",
    "Chart",
    "KIND_DROPDOWN",
    "KIND_RADIO",
    "Select",
    "Table",
    "Tab",
    "find",
    "default_value",
    "variant_key",
]
