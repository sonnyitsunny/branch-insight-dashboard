"""원본 파일 — 월별 지점 수익.

기준월·지점마다 한 행이고 '전체' 합계 행이 월마다 하나 더 있다. 리테일
상품이 가로로 펼쳐져 상품마다 수익 컬럼과 비중 컬럼을 차지한다. 데이터
계층은 한 줄에 한 분류인 형태로 편다. 상품이 늘어도 표준 프레임의 컬럼은
늘지 않는다.

**'전체'와 '공통'** — 컬럼 이름의 '전체'는 전체고객, '공통'은 공통고객을
가리킨다. 지점 축의 '전체'(합계 행)와는 다른 뜻이다. 화면이 주로 보는 값은
공통고객 쪽이라 표준 컬럼의 기본 이름(`revenue_amount`)을 공통고객에 주고,
전체고객 값은 `all_revenue_amount`에 담는다. 전체고객 수익은 상품별로
나뉘어 있지 않아 '리테일'·'퇴직'·'최종' 세 분류에만 있다.

단위 — 수익은 **원**이다. 거래·자산 프레임의 억원과 다르다. 원본이 원으로
담고 있으므로 여기서 억원으로 바꾸지 않는다. 나누어 두면 원본과 화면
숫자가 반올림만큼 달라진다(→ AGENTS.md §9).

부호 — 수익은 손실이 나면 음수가 될 수 있다. 인원수와 달리 음수를 막지
않는다.

비중 — 원본이 이미 %로 계산해 담고 있어 그대로 넘긴다. 여기서 다시 만들지
않는다. 인원수나 금액에서 되계산하면 반올림 때문에 화면 숫자가 원본과
달라진다(→ AGENTS.md §9).

분모는 두 가지다. 상품 9개와 '퇴직'의 비중은 `수익_공통_최종`이 분모라
열이 100%를 이룬다. `수익_공통_비중`만 분모가 달라 `수익_공통_최종 ÷
수익_전체_최종`, 즉 전체고객 수익 중 공통고객이 차지하는 몫이다. 뜻이 다른
값이라 같은 컬럼에 담지 않고 `common_revenue_share`로 나눠 담는다.

합이 100인지는 확인하지 않는다. 소수점 첫째 자리까지 반올림된 값 10개를
더하면 원래 100에서 조금 벗어날 수 있어, 맞는 데이터를 틀렸다고 막게 된다.

묶음 값 — '리테일'과 '퇴직'을 더하면 '최종'이 된다. 전체고객·공통고객
양쪽에서 성립하므로 읽을 때 대조한다(→ GROUP_SUMS). 어긋나면 어느 쪽이
맞는지 사람이 판단해야 하므로 값을 고치지 않고 멈춘다. 다만 '최종'을 더해서
만들지는 않는다. 원본이 담고 있는 값을 그대로 화면까지 보낸다.

'리테일'이 상품 9개의 합인지는 확인하지 않는다. 그렇게 담는다는 약속이 없다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dashboard.data import (
    ALL_REVENUE_TYPES,
    REVENUE_FINAL,
    REVENUE_PENSION,
    REVENUE_RETAIL,
    plain_text,
    to_month_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익1.pkl"              → data/수익1.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익1.pkl"
FILE_ENV = "DASHBOARD_REVENUE1_FILE"

LABEL = "지점 수익1"

# 원본 컬럼명 → 내부 표준 컬럼명.
# 수익 컬럼은 이름 하나가 분류와 지표를 함께 가리키므로 아래 표에 따로 적는다.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
}

_KEY_COLUMNS = ("base_month", "branch_id", "branch_name")

# 수익 분류 → (공통고객 수익, 전체고객 수익, 비중) 컬럼.
# None이면 원본에 그 컬럼이 없다는 뜻이다. 비운 채로 넘겨 화면에 `-`로
# 나타나게 한다. 0으로 채우지 않는다.
#
# 원본에서 컬럼 이름이 바뀌면 오른쪽만 고친다. 왼쪽 이름은 화면까지 그대로
# 가며 `dashboard.data.ALL_REVENUE_TYPES`와 같아야 한다.
TYPE_COLUMNS: dict[str, tuple[str, str | None, str | None]] = {
    "국내주식": (
        "수익_공통_국내주식",
        None,
        "수익_공통_국내주식_비중",
    ),
    "국내ETF": (
        "수익_공통_국내ETF",
        None,
        "수익_공통_국내ETF_비중",
    ),
    "해외주식": (
        "수익_공통_해외주식",
        None,
        "수익_공통_해외주식_비중",
    ),
    "예수금": ("수익_공통_예수금", None, "수익_공통_예수금_비중"),
    "신용": ("수익_공통_신용", None, "수익_공통_신용_비중"),
    "펀드": ("수익_공통_펀드", None, "수익_공통_펀드_비중"),
    "채권": ("수익_공통_채권", None, "수익_공통_채권_비중"),
    "CMA발행어음RP": (
        "수익_공통_CMA발행어음RP",
        None,
        "수익_공통_CMA발행어음RP_비중",
    ),
    "기타": ("수익_공통_기타", None, "수익_공통_기타_비중"),
    # 묶음 값. 전체고객 수익은 이 셋에만 있다.
    REVENUE_RETAIL: ("수익_공통_리테일", "수익_전체_리테일", None),
    REVENUE_PENSION: (
        "수익_공통_퇴직",
        "수익_전체_퇴직",
        "수익_공통_퇴직_비중",
    ),
    REVENUE_FINAL: ("수익_공통_최종", "수익_전체_최종", None),
}

# 묶음 값의 관계 — (합 컬럼, 부분 컬럼들). 리테일과 퇴직을 더하면 최종이
# 되며 전체고객·공통고객 양쪽에서 성립한다. 원본 컬럼 이름이 바뀌면 위
# TYPE_COLUMNS 와 함께 여기도 고친다.
GROUP_SUMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("수익_전체_최종", ("수익_전체_리테일", "수익_전체_퇴직")),
    ("수익_공통_최종", ("수익_공통_리테일", "수익_공통_퇴직")),
)

AMOUNT_COLUMN = "revenue_amount"
ALL_AMOUNT_COLUMN = "all_revenue_amount"
SHARE_COLUMN = "revenue_share"
COMMON_SHARE_COLUMN = "common_revenue_share"

_VALUE_COLUMNS = (AMOUNT_COLUMN, ALL_AMOUNT_COLUMN, SHARE_COLUMN)

# 공통고객 수익 비중(%) = 수익_공통_최종 ÷ 수익_전체_최종.
# 원본에 분류축이 없는 값이라 어느 한 분류에 담아야 한다. 분자·분모가 모두
# '최종'이므로 그 행에 둔다.
SOURCE_COMMON_SHARE = "수익_공통_비중"
COMMON_SHARE_TYPE = REVENUE_FINAL


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 분류인 형태로 편다.

    되돌려주는 컬럼은 base_month·branch_id·branch_name·revenue_type·
    revenue_amount·all_revenue_amount·revenue_share·common_revenue_share
    여덟 개다.

    기준 월은 `202601`이든 `2026-01`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다.
    """
    _check_columns(frame)
    _check_group_sums(frame)
    parts = [
        _type_part(frame, revenue_type, columns)
        for revenue_type, columns in TYPE_COLUMNS.items()
    ]
    long = pd.concat(parts, ignore_index=True)
    long["base_month"] = to_month_column(long["base_month"], "revenue1")
    _check_keys(long)
    return long


def _type_part(
    frame: pd.DataFrame,
    revenue_type: str,
    columns: tuple[str, str | None, str | None],
) -> pd.DataFrame:
    """수익 분류 하나를 표준 컬럼 이름으로 잘라 낸다."""
    found = [column for column in columns if column is not None]
    part = frame.loc[:, [*_KEY_COLUMNS, *found]].rename(
        columns={
            column: name
            for column, name in zip(columns, _VALUE_COLUMNS)
            if column is not None
        }
    )
    for column, name in zip(columns, _VALUE_COLUMNS):
        if column is None:
            part[name] = np.nan
    part[COMMON_SHARE_COLUMN] = (
        frame[SOURCE_COMMON_SHARE]
        if revenue_type == COMMON_SHARE_TYPE
        else np.nan
    )
    part.insert(len(_KEY_COLUMNS), "revenue_type", revenue_type)
    return part.loc[
        :,
        [
            *_KEY_COLUMNS,
            "revenue_type",
            *_VALUE_COLUMNS,
            COMMON_SHARE_COLUMN,
        ],
    ]


def _check_columns(frame: pd.DataFrame) -> None:
    """수익 컬럼이 모두 있는지 본다. 없으면 이름을 알리며 멈춘다.

    키 컬럼은 `sources.rename`이 이미 확인했다. 여기서는 수익 컬럼만 본다.
    """
    expected = [
        column
        for columns in TYPE_COLUMNS.values()
        for column in columns
        if column is not None
    ]
    expected.append(SOURCE_COMMON_SHARE)
    missing = [
        column for column in expected if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{LABEL} 파일에 다음 컬럼이 없습니다: {', '.join(missing)}. "
            "원본의 수익 컬럼 이름이 바뀌었으면 "
            "dashboard/sources/revenue1.py 의 TYPE_COLUMNS 를 고쳐 "
            f"주세요. 파일에 있는 컬럼: {', '.join(map(str, frame.columns))}"
        )
    unknown = sorted(set(TYPE_COLUMNS) - set(ALL_REVENUE_TYPES))
    if unknown:
        raise ValueError(
            f"{LABEL} 의 TYPE_COLUMNS 에 화면이 모르는 수익 분류가 "
            f"있습니다: {', '.join(unknown)}. "
            "dashboard/data.py 의 REVENUE_PRODUCT_TYPES 에도 더해 주세요."
        )


def _check_group_sums(frame: pd.DataFrame) -> None:
    """'리테일 + 퇴직 = 최종'인지 본다. 어긋나면 멈춘다.

    한 파일 안에서 앞뒤가 맞는지 보는 대조라 파일 사이 대조와 달리 허용치를
    두지 않는다. 원 단위까지 맞아야 한다(→ AGENTS.md §9). 원본이 실수로
    담고 있을 수 있어 원 단위로 반올림한 뒤 견준다.

    셋 중 하나라도 비어 있는 행은 견주지 않는다. 빈 칸을 0으로 보면 맞는
    데이터를 틀렸다고 막게 된다. 공통고객 쪽이 비어 있으면 표준 프레임의
    필수 컬럼 검사에서 따로 걸린다(→ dashboard/data.py 의 REVENUE_COLUMNS).
    """
    for total, parts in GROUP_SUMS:
        columns = [frame[total], *(frame[part] for part in parts)]
        numbers = [
            pd.to_numeric(column, errors="coerce").round()
            for column in columns
        ]
        readable = ~pd.concat(numbers, axis=1).isna().any(axis=1)
        if not readable.any():
            continue
        gap = (numbers[0] - sum(numbers[1:])).abs().where(readable, 0)
        over = gap > 0
        if not over.any():
            continue
        row = frame[over].iloc[0]
        raise ValueError(
            f"{LABEL} 파일의 {total} 이 {' + '.join(parts)} 와 다릅니다. "
            f"{row['base_month']} 지점 {row['branch_id']} — "
            f"{numbers[0][over].iloc[0]:,.0f} vs "
            f"{sum(numbers[1:])[over].iloc[0]:,.0f} "
            f"(차이 {gap[over].iloc[0]:,.0f}원). "
            f"어긋난 곳이 {int(over.sum())}곳입니다. "
            "어느 쪽이 맞는지 확인한 뒤 원본을 맞춰 주세요."
        )


def _check_keys(long: pd.DataFrame) -> None:
    """한 지점의 한 달이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면의 합계는 조용히 두 배가
    된다.
    """
    keys = pd.MultiIndex.from_arrays(
        [
            long["base_month"],
            plain_text(long["branch_id"]),
            long["revenue_type"],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, revenue_type = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 기준월·지점이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} ({revenue_type}). "
            "한 지점은 한 달에 한 행이어야 합니다."
        )
