"""원본 파일 — 지점 수익률 그룹별 고객 비중.

기준월·지점·기간·수익률 구간마다 한 행이다. 기간이 둘(1년·3년), 구간이
열이라 한 지점이 스무 행을 갖는다. 지점 행 외에 '전체' 행도 같은 모양으로
들어 있으며, 데이터 계층이 그 행을 따로 떼어 둔다(→ dashboard/data.py).

기간 코드 — 원본은 기간을 `MM12_ERN_R`·`MM36_ERN_R` 코드로 담는다. 화면에
보이는 이름은 데이터 계층이 정하므로(→ data.RETURN_PERIODS) 여기서 코드에
이름을 붙인다. 코드가 바뀌면 `PERIOD_CODES`만 고친다.

구간 이름 — 원본은 `0)-20%미만`처럼 앞에 차례를 적어 담고, 물결 좌우의
공백도 있을 수도 없을 수도 있다. 번호를 떼고 공백을 흡수하는 일과 그
차례가 화면 차례와 같은지 보는 일은 자산규모별 수익률 원본과 같은 규칙이라
데이터 계층의 함수를 함께 쓴다(→ data.to_ordered_label_column).

고객 수 — `고객수`는 그 구간에 든 고객 수, `고객수_지점합계`는 그 지점·기간의
고객 수 전체다. 뒤엣것이 비중의 분모이며 한 지점·기간의 구간 열 개에 같은
값이 반복해 들어 있다. 반복된 값이 서로 다르거나 구간 열 개의 합이 그 값과
맞지 않으면 원본 안에서 숫자가 어긋났다는 뜻이라 멈춘다
(→ check_branch_totals).

비중 — 원본이 이미 %로 계산해 담고 있어 그대로 넘긴다. 인원수에서 다시
만들지 않는다. 반올림 때문에 화면 숫자가 원본과 달라진다(→ AGENTS.md §9).
대신 인원수에서 계산한 값과 크게 어긋나지는 않는지 확인한다
(→ check_shares).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    RETURN_GROUPS,
    RETURN_PERIODS,
    SHARE_TOLERANCE_PP,
    check_not_negative,
    plain_text,
    strip_number_marks,
    to_month_column,
    to_numeric_column,
    to_optional_number_column,
    to_ordered_label_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익률_수익률그룹별비중.pkl"
#       → data/수익률_수익률그룹별비중.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_수익률그룹별비중.pkl"
FILE_ENV = "DASHBOARD_RETURN_GROUP_FILE"

LABEL = "수익률 그룹별 비중"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "수익률_구분": "return_period",
    "수익률_그룹": "return_group",
    "고객수": "customer_count",
    "고객수_지점합계": "branch_customer_count",
    "고객비중": "customer_share",
}

# 원본이 담는 기간 코드 → 화면에 보이는 이름(→ data.RETURN_PERIODS).
PERIOD_CODES: dict[str, str] = {
    "MM12_ERN_R": RETURN_PERIODS[0],
    "MM36_ERN_R": RETURN_PERIODS[1],
}

# 인원수 컬럼 → 원본 컬럼 이름. 오류 문구에 원본 이름을 적어야 파일의
# 어디를 봐야 하는지 알 수 있다.
COUNT_COLUMNS: dict[str, str] = {
    "customer_count": "고객수",
    "branch_customer_count": "고객수_지점합계",
}

# 한 지점·기간을 가르는 키. 구간 열 개가 이 키 하나를 이룬다.
BRANCH_KEYS = ["base_month", "branch_id", "return_period"]


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 수익률 그룹별 비중 프레임을 만든다.

    되돌려주는 컬럼은 `COLUMNS`의 표준 이름 8개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다. 기간 코드에 이름을 붙이고 표기만 떼어 낸다.
    """
    group = frame.loc[:, list(COLUMNS.values())].copy()
    group["base_month"] = to_month_column(
        group["base_month"], "return_group"
    )
    group["return_period"] = _period_names(group["return_period"])
    group["return_group"] = to_ordered_label_column(
        group["return_group"],
        LABEL,
        "수익률_그룹",
        RETURN_GROUPS,
        "RETURN_GROUPS",
    )
    for column, label in COUNT_COLUMNS.items():
        group[column] = _count(group[column], label)
    group["customer_share"] = to_optional_number_column(
        group["customer_share"],
        LABEL,
        "고객비중",
        "비중은 %로 계산된 숫자여야 합니다.",
    )
    _check_keys(group)
    check_branch_totals(group)
    check_shares(group)
    return group


def _period_names(series: pd.Series) -> pd.Series:
    """기간 코드에 화면 이름을 붙인다.

    코드가 아니라 이름(`1년`·`3년`)으로 들어와도 그대로 둔다. 모르는 값은
    고치지 않고 넘겨, 어떤 값이 문제인지 데이터 계층이 알리게 한다
    (→ data._to_category).
    """
    text = plain_text(series)
    return text.map(lambda value: PERIOD_CODES.get(value, value))


def _count(series: pd.Series, column: str) -> pd.Series:
    """인원수를 숫자로 맞춘다. 천 단위 쉼표와 앞에 붙은 `+`를 떼고 읽는다."""
    numbers = to_numeric_column(
        strip_number_marks(series), LABEL, column
    )
    check_not_negative(numbers, LABEL, column)
    return numbers.astype(float)


def _check_keys(group: pd.DataFrame) -> None:
    """한 지점·기간·구간이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면의 막대 높이는 조용히
    두 배가 된다.
    """
    keys = pd.MultiIndex.from_arrays(
        [
            group["base_month"],
            plain_text(group["branch_id"]),
            group["return_period"],
            group["return_group"],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, period, name = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 지점·기간·구간이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} {period} {name}. "
            "한 구간은 한 번만 있어야 합니다."
        )


def check_branch_totals(group: pd.DataFrame) -> None:
    """원본 안에서 인원수가 앞뒤로 맞는지 본다.

    두 가지를 본다. 한 지점·기간의 `고객수_지점합계`가 구간마다 같은지,
    그리고 구간 인원수를 모두 더하면 그 값이 되는지다.

    한 파일 안에서 앞뒤가 맞는지 보는 대조라 허용치를 두지 않는다. 사람
    단위까지 맞아야 한다(→ AGENTS.md §9, profile.check_equal_counts).
    맞지 않으면 막대 높이(비중)와 hover의 고객 수가 서로 다른 이야기를
    하게 된다.
    """
    if group.empty:
        return
    by_branch = group.groupby(BRANCH_KEYS, observed=True)

    spread = by_branch["branch_customer_count"].nunique()
    if (spread > 1).any():
        key = spread[spread > 1].index[0]
        rows = group[_matches(group, key)]
        raise ValueError(
            f"{LABEL} 파일의 '고객수_지점합계'가 구간마다 다릅니다: "
            f"{' '.join(map(str, key))} — "
            f"{sorted(set(rows['branch_customer_count']))[:4]}. "
            "한 지점·기간의 구간 10개에는 같은 값이 들어 있어야 합니다."
        )

    computed = by_branch["customer_count"].sum()
    given = by_branch["branch_customer_count"].first()
    mismatch = computed.round() != given.round()
    if not mismatch.any():
        return
    key = mismatch[mismatch].index[0]
    raise ValueError(
        f"{LABEL} 파일에서 구간 인원수의 합이 '고객수_지점합계'와 "
        f"다른 지점이 {int(mismatch.sum())}곳 있습니다. "
        f"예: {' '.join(map(str, key))} — "
        f"구간 합 {computed[key]:,.0f}명 vs "
        f"지점 합계 {given[key]:,.0f}명. "
        "구간 10개가 그 지점의 고객을 모두 담고 있는지 확인해 주세요."
    )


def _matches(group: pd.DataFrame, key: tuple) -> pd.Series:
    """`BRANCH_KEYS`가 그 값인 행. 오류 문구에 실제 값을 싣는다."""
    picked = pd.Series(True, index=group.index)
    for column, value in zip(BRANCH_KEYS, key):
        picked &= group[column] == value
    return picked


def check_shares(group: pd.DataFrame) -> None:
    """원본이 담은 비중이 인원수에서 계산한 비중과 맞는지 확인한다.

    반올림 차이는 넘어가고, 집계 기준이 달라 크게 벌어질 때만 멈춘다
    (→ data.SHARE_TOLERANCE_PP). 막대 높이는 이 비중으로, hover의 고객 수는
    인원수로 그리므로 둘이 크게 어긋나면 화면 안에서 숫자가 서로 맞지 않게
    된다.

    비중이 비어 있는 행은 견주지 않는다. 고객이 하나도 없는 지점·기간은
    나눌 분모가 없다.
    """
    if group.empty:
        return
    total = group["branch_customer_count"]
    computed = (
        group["customer_count"] / total * 100.0
    ).where(total > 0)
    gap = (group["customer_share"] - computed).abs()
    over = gap > SHARE_TOLERANCE_PP
    if not over.any():
        return
    index = gap.idxmax()
    row = group.loc[index]
    raise ValueError(
        f"{LABEL} 파일의 '고객비중'이 인원수에서 계산한 비중과 다른 행이 "
        f"{int(over.sum())}건 있습니다. "
        f"예: {row['branch_name']} {row['return_period']} "
        f"{row['return_group']} — "
        f"원본 {row['customer_share']:.4f}% vs "
        f"인원수 기준 {computed[index]:.4f}% "
        f"(차이 {gap[index]:.4f}%p, 허용 {SHARE_TOLERANCE_PP}%p). "
        "원본의 비중이 0~1 비율이면 100을 곱해 담아 주세요."
    )


__all__ = [
    "BRANCH_KEYS",
    "COLUMNS",
    "COUNT_COLUMNS",
    "FILE",
    "FILE_ENV",
    "LABEL",
    "PERIOD_CODES",
    "build",
    "check_branch_totals",
    "check_shares",
]
