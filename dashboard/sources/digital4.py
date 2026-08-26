"""원본 파일 — 분류별 메뉴 이용 순위.

기준월·지점·순위마다 한 행이고, 그 한 행에 **메뉴 분류 여섯이 가로로
펼쳐져** 있다. 분류마다 메뉴 이름·조회 건수·거래 전환 비율 세 컬럼을 갖는다.
지점 행 외에 '전체' 행도 같은 모양으로 들어 있으며, 데이터 계층이 그 행을
따로 떼어 둔다(→ dashboard/data.py).

데이터 계층이 이것을 한 줄에 한 분류인 형태로 편다(→ build). 연금통합1이
상품을 펴는 것과 같은 방식이고, 여기서는 축이 하나라 한 행이 여섯 줄이 된다
(→ dashboard/sources/pension1.py).

컬럼 이름 — 메뉴 이름은 분류 이름이 곧 컬럼 이름(`국내주식`)이고, 조회
건수와 거래 전환 비율만 뒤에 말이 붙는다(`국내주식_조회건수`,
`국내주식_r`). 여섯이 같은 규칙을 따르므로 표를 손으로 적지 않고 규칙에서
만든다. 규칙이 깨지면 `BLOCK_COLUMNS`만 고친다
(→ data.DIGITAL_MENU_CATEGORIES).

**메뉴 이름이 빈 칸이면 그 줄을 만들지 않는다.** 가로로 펼친 파일에서 빈
칸은 '그 분류는 이 순위까지 없다'는 뜻이다. 이름이 없으면 화면에 적을 것이
없으므로 줄이 아예 없는 것으로 읽는다. 값을 지어내 채우지 않는다
(→ AGENTS.md §9). 지점마다 분류마다 순위 수가 달라질 수 있다.

기간 — 원본이 가장 최근 달만 담고 있을 수 있다. 월별 파일보다 적은 달을
담는 것은 정상이며, 월별 파일에 없는 달이 있을 때만 멈춘다
(→ dashboard/sources/__init__.py 의 check_months_within).

조회 건수 — 그 메뉴에 들어간 **횟수**이며 사람 수가 아니다. 한 고객이 여러
번 들어가면 그만큼 더해지므로 지점 고객 수를 넘을 수 있다. 음수일 수는
없으므로 음수가 있으면 멈춘다.

거래 전환 비율(`<분류>_r`) — 그 메뉴를 조회한 뒤 거래까지 이어진 몫이다.
원본이 이미 %로 계산해 담고 있어 그대로 넘긴다. 100을 곱하거나 나누지 않고
조회 건수와 견주지도 않는다(→ AGENTS.md §9). 표기(`%`, 천 단위 쉼표, 앞의
`+`)만 떼고 숫자로 읽는다.

값이 0~100 안에 있는지는 확인한다. 조회한 것 중의 몫이라 100%를 넘을 수
없다. 벗어난 값은 원본을 읽는 방법이 틀렸다는 뜻이다. 다만 원본이 0~1
비율로 바뀌면 이 검사에 걸리지 않으므로 화면 숫자를 눈으로 확인해야 한다.

빈 칸 — 비율을 낼 수 없는 자리는 비운 채로 넘겨 화면에 `-`로 나타나게 한다.
0으로 채우지 않는다. 0%는 '거래로 이어지지 않았다'는 측정값이라 '값이
없다'와 다르다(→ AGENTS.md §9).

**분모가 무엇인지는 확정되지 않았다.** 조회 건수인지 조회한 고객 수인지
알 수 없으므로, 조회 건수와 곱해 거래 건수를 만들지 않는다
(→ AGENTS.md §17).

**순위를 무엇으로 매겼는지 확인하지 않는다.** 조회 건수 순으로 보이지만
원본이 그렇다고 말하지 않았고, 확정되지 않은 것을 임의로 정하지 않는다
(→ AGENTS.md §17). 순위가 내려갈수록 건수가 줄어드는지 견주지 않고 원본이
담은 순위를 그대로 쓴다.

**분류끼리 더하지 않는다.** '공통고객'은 나머지 다섯을 합친 값이 아니라
다섯과 나란한 하나의 분류다(→ data.DIGITAL_MENU_CATEGORIES).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    DIGITAL_MENU_CATEGORIES,
    check_not_negative,
    check_unique_rows,
    strip_number_marks,
    to_label_column,
    to_month_column,
    to_numeric_column,
    to_optional_number_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "디지털채널_4.pkl"        → data/디지털채널_4.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "디지털채널_4.pkl"
FILE_ENV = "DASHBOARD_DIGITAL4_FILE"

LABEL = "디지털 채널 메뉴 순위"

# 원본 컬럼명 → 내부 표준 컬럼명. 한 행에 함께 있는 열쇠 컬럼만 적는다.
# 분류별 컬럼은 규칙에서 만든다(→ BLOCK_COLUMNS).
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "순위": "menu_rank",
}

KEY_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "menu_rank",
)

# 분류마다 붙어 있는 세 컬럼. 표준 이름 → 원본 컬럼 이름에서 분류 뒤에
# 붙는 말. 메뉴 이름은 분류 이름이 곧 컬럼 이름이라 뒤에 붙는 말이 없다.
BLOCK_COLUMNS: dict[str, str] = {
    "menu_name": "",
    "view_count": "_조회건수",
    "trade_conversion_share": "_r",
}

# 거래 전환 비율이 있을 수 있는 범위. 조회한 것 중의 몫이라 100%를 넘을 수
# 없다(→ _check_share_range).
SHARE_RANGE = (0.0, 100.0)


def block_column(category: str, field: str) -> str:
    """분류 하나의 원본 컬럼 이름. 규칙은 `<분류><항목>`이다."""
    return f"{category}{BLOCK_COLUMNS[field]}"


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 분류인 형태로 편다.

    되돌려주는 컬럼은 `data.DIGITAL_MENU_RANK_COLUMNS`와 거래 전환 비율을
    더한 여덟이다. 행 수는 원본의 분류 수만큼 늘어나되, 메뉴 이름이 빈
    칸이던 자리는 빠진다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    순위 차례는 데이터 계층이 정렬로 다시 맞추므로 여기서는 값만 본다.
    """
    _check_columns(frame)
    parts = []
    for category in DIGITAL_MENU_CATEGORIES:
        columns = {
            block_column(category, field): field
            for field in BLOCK_COLUMNS
        }
        part = frame.loc[
            :, [*KEY_COLUMNS, *columns]
        ].rename(columns=columns)
        part.insert(len(KEY_COLUMNS), "menu_category", category)
        parts.append(part)
    long = pd.concat(parts, ignore_index=True)

    long["base_month"] = to_month_column(long["base_month"], "digital4")
    # 메뉴 이름이 빈 칸인 자리는 그 분류에 그 순위가 없다는 뜻이라 줄을
    # 만들지 않는다. 빈 칸을 가리는 규칙은 `to_label_column`에 있는 것을
    # 그대로 쓴다. 여기서 따로 적으면 원본이 빈 칸을 NaN으로 담았을 때
    # 한쪽만 걸러 내고 다른 쪽이 멈춘다.
    long["menu_name"] = to_label_column(
        long["menu_name"], LABEL, "menu_name", required=False
    )
    long = long[long["menu_name"] != ""].reset_index(drop=True)
    # 오류 문구에는 원본 컬럼 이름을 적는다. 표준 이름을 적으면 원본
    # 어디를 봐야 하는지 알 수 없다.
    long["menu_rank"] = _number(long["menu_rank"], "순위")
    long["menu_rank"] = long["menu_rank"].round().astype(int)
    long["view_count"] = _number(long["view_count"], "조회건수")
    long["trade_conversion_share"] = _share(
        long["trade_conversion_share"]
    )
    check_ranks(long)
    return long


def _share(series: pd.Series) -> pd.Series:
    """거래 전환 비율. 원본이 담은 %를 그대로 넘긴다.

    뒤에 붙은 `%`, 천 단위 쉼표, 앞에 붙은 `+`를 떼고 읽는다. 100을 곱하거나
    나누지 않는다(→ AGENTS.md §9). 비어 있는 칸은 비운 채로 둔다.

    오류 문구에는 분류가 붙은 원본 이름 대신 뒤에 붙는 말만 적는다. 편 뒤라
    어느 분류의 행인지는 `menu_category` 컬럼이 말해 준다.
    """
    numbers = to_optional_number_column(
        series,
        LABEL,
        BLOCK_COLUMNS["trade_conversion_share"],
        "거래 전환 비율은 %로 계산된 숫자여야 합니다.",
    )
    _check_share_range(numbers)
    return numbers


def _check_share_range(numbers: pd.Series) -> None:
    """거래 전환 비율이 0~100 안에 있는지 본다. 빈 칸은 넘어간다.

    조회한 것 중의 몫이라 100%를 넘을 수 없다. 벗어난 값은 원본을 읽는
    방법이 틀렸다는 뜻이며, 조용히 넘기면 화면에 그대로 그려져 틀린 숫자가
    맞는 것처럼 보인다(→ AGENTS.md §9).
    """
    low, high = SHARE_RANGE
    values = numbers.dropna()
    outside = ~values.between(low, high)
    if not outside.any():
        return
    raise ValueError(
        f"{LABEL} 파일의 거래 전환 비율이 {low:g}~{high:g} 범위를 벗어난 "
        f"값이 {int(outside.sum())}건 있습니다. "
        f"예: {values[outside].head(3).tolist()}. "
        "원본이 0~1 비율이면 100을 곱해 담아 주세요."
    )


def _number(series: pd.Series, column: str) -> pd.Series:
    """숫자로 맞춘다. 천 단위 쉼표와 앞에 붙은 `+`를 떼고 읽는다.

    순위도 조회 건수도 음수일 수 없다. 음수가 나왔다면 원본을 읽는 방법이
    틀렸다는 뜻이라 멈춘다.
    """
    numbers = to_numeric_column(
        strip_number_marks(series), LABEL, column
    )
    check_not_negative(numbers, LABEL, column)
    return numbers.astype(float)


def _check_columns(frame: pd.DataFrame) -> None:
    """분류 컬럼이 모두 있는지 본다. 없으면 이름을 알리며 멈춘다."""
    missing = [
        block_column(category, field)
        for category in DIGITAL_MENU_CATEGORIES
        for field in BLOCK_COLUMNS
        if block_column(category, field) not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{LABEL} 파일에 다음 컬럼이 없습니다:"
            f" {', '.join(missing[:8])}"
            f" (모두 {len(missing)}개). "
            "원본의 분류 컬럼 이름이 바뀌었으면 "
            "dashboard/data.py 의 DIGITAL_MENU_CATEGORIES 와 "
            "dashboard/sources/digital4.py 의 BLOCK_COLUMNS 를 고쳐 "
            f"주세요. 파일에 있는 컬럼: {', '.join(map(str, frame.columns))}"
        )


def check_ranks(long: pd.DataFrame) -> None:
    """한 지점·한 분류 안에서 순위와 메뉴가 겹치지 않는지 본다.

    순위가 겹치면 표에 같은 등수가 두 번 나오고, 메뉴가 겹치면 같은 메뉴가
    두 줄이 되어 조회 건수가 두 번 더해진다. 어느 행이 맞는지 화면에서는
    알 수 없으므로 멈춘다(→ data.check_unique_rows).

    순위가 몇 위까지 있는지는 보지 않는다. 메뉴 이름이 빈 칸이던 자리는 줄이
    없으므로 분류마다 끝나는 자리가 다르다.
    """
    keys = ["base_month", "branch_id", "menu_category"]
    for column, label in (("menu_rank", "순위"), ("menu_name", "메뉴")):
        check_unique_rows(long, LABEL, keys, column, label)


__all__ = [
    "BLOCK_COLUMNS",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "KEY_COLUMNS",
    "LABEL",
    "SHARE_RANGE",
    "block_column",
    "build",
    "check_ranks",
]
