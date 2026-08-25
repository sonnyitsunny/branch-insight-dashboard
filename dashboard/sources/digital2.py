"""원본 파일 — 채널별 이용 고객의 특성.

기준월·지점마다 한 행이고 '전체' 합계 행이 하나 더 있다. **채널 셋이
가로로 펼쳐져 있다.** `HTS_연령`처럼 채널 이름을 앞머리로 붙인 컬럼이
채널마다 여덟 벌 있어, 한 줄에 한 채널인 표준 형태로 편다.

담는 값 — 그 채널을 쓴 고객의 평균 연령, 평균 자산, 그리고 상품별 잔고
비중 여섯이다. 채널 축은 디지털채널1과 같다(→ data.DIGITAL_CHANNELS).

단위 — `자산평균`은 **원**이다. 월별 프레임의 평균 자산(백만원)과 달라
표준 이름도 `average_assets_won`으로 갈라 둔다. 같은 이름을 쓰면 화면에서
단위를 잘못 붙여도 드러나지 않는다(→ data.DIGITAL_PROFILE_OPTIONAL_COLUMNS).

비중 — 원본이 이미 %로 계산해 담고 있어 그대로 넘긴다. 0~1 비율을 100으로
곱하지 않는다(→ AGENTS.md §9). **여섯 상품의 합이 100%가 되는지 확인하지
않는다.** 예수금처럼 이 여섯에 들어가지 않는 잔고가 있을 수 있어, 합이
100%보다 작은 것이 정상이다. 대신 값 하나하나가 0~100 안에 있는지는
확인한다. 원본이 0~1 비율로 바뀌면 화면의 모든 비중이 0%에 가깝게
나오는데, 그것은 이 검사로 잡히지 않으므로 눈으로 확인해야 한다.

빈 칸 — 그 채널을 쓴 고객이 없는 지점·달은 평균을 낼 대상이 없다. 비운
채로 넘겨 화면에 `-`로 나타나게 하고 0으로 채우지 않는다. 평균 연령 0세는
'고객이 없다'가 아니라 '0세로 측정됨'을 뜻한다(→ AGENTS.md §9).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    DIGITAL_CHANNELS,
    plain_text,
    to_month_column,
    to_optional_number_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "디지털채널_2.pkl"        → data/디지털채널_2.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "디지털채널_2.pkl"
FILE_ENV = "DASHBOARD_DIGITAL2_FILE"

LABEL = "디지털 채널 고객 특성"

# 채널 뒤에 붙는 원본 이름 → 표준 컬럼명. 채널마다 같은 여덟 값이 되풀이돼
# 스물넷이 되므로, 손으로 다 적지 않고 여기 한 번만 적어 채널을 곱한다.
# 스물넷을 늘어놓으면 한 곳만 고쳐지고 나머지가 남는다.
MEASURES: dict[str, str] = {
    "연령": "average_age",
    "자산평균": "average_assets_won",
    "국내주식비중": "domestic_stock_share",
    "해외주식비중": "overseas_stock_share",
    "국내ETF비중": "etf_share",
    "채권비중": "bond_share",
    "펀드비중": "fund_share",
    "개인연금비중": "pension_share",
}

# 0~100 안에 있어야 하는 값. 연령과 자산평균은 비중이 아니라 여기 없다.
SHARE_MEASURES = tuple(
    standard
    for source, standard in MEASURES.items()
    if source.endswith("비중")
)

KEY_COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
}


def wide_name(channel: str, standard: str) -> str:
    """펴기 전 표준 프레임에서 그 채널·값이 쓰는 컬럼 이름."""
    return f"{channel.lower()}_{standard}"


# 원본 컬럼명 → 내부 표준 컬럼명. 채널이 붙은 컬럼은 펴기 전까지만 쓰는
# 이름이라 `hts_average_age`처럼 채널을 앞에 남겨 둔다(→ build).
COLUMNS: dict[str, str] = {
    **KEY_COLUMNS,
    **{
        f"{channel}_{source}": wide_name(channel, standard)
        for channel in DIGITAL_CHANNELS
        for source, standard in MEASURES.items()
    },
}

# 표준 컬럼 → 원본 컬럼 이름. 오류 문구에 원본 이름을 적어야 파일의 어디를
# 봐야 하는지 알 수 있다.
SOURCE_NAMES: dict[str, str] = {
    standard: source for source, standard in COLUMNS.items()
}

# 연령으로 읽을 수 있는 범위. 사람의 나이라 이 밖의 값은 원본을 읽는
# 방법이 틀렸다는 뜻이다(→ data.py 의 summary.average_age 검사와 같은 범위).
AGE_RANGE = (0.0, 120.0)


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 채널인 형태로 편다.

    되돌려주는 컬럼은 `data.DIGITAL_PROFILE_COLUMNS`와 그 선택 컬럼이다.
    행 수는 원본의 채널 수만큼 늘어난다.

    기준 월은 `202507`이든 `2025-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다. 표기만 떼고 숫자로 읽는다.
    """
    wide = frame.loc[:, list(COLUMNS.values())].copy()
    wide["base_month"] = to_month_column(wide["base_month"], "digital2")
    _check_keys(wide)

    keys = list(KEY_COLUMNS.values())
    parts = []
    for channel in DIGITAL_CHANNELS:
        columns = {
            wide_name(channel, standard): standard
            for standard in MEASURES.values()
        }
        part = wide.loc[:, [*keys, *columns]].rename(columns=columns)
        part.insert(len(keys), "channel", channel)
        parts.append(part)
    profile = pd.concat(parts, ignore_index=True)

    for standard in MEASURES.values():
        profile[standard] = _number(profile[standard], standard)
    _check_ranges(profile)
    return profile


def _number(series: pd.Series, standard: str) -> pd.Series:
    """값을 숫자로 맞추되 비어 있는 칸은 비운 채로 둔다.

    오류 문구에는 채널이 붙은 원본 이름 대신 값의 이름만 적는다. 편 뒤라
    어느 채널의 행인지는 `channel` 컬럼이 말해 준다.
    """
    hint = (
        "비중은 %로 계산된 숫자여야 합니다."
        if standard in SHARE_MEASURES
        else "숫자로 담아 주세요."
    )
    return to_optional_number_column(series, LABEL, standard, hint)


def _check_ranges(profile: pd.DataFrame) -> None:
    """값이 있을 수 있는 범위 안에 있는지 본다.

    범위를 벗어난 값은 원본을 읽는 방법이 틀렸다는 뜻이다. 조용히 넘기면
    화면에 그대로 그려져 틀린 숫자가 맞는 것처럼 보인다(→ AGENTS.md §9).
    """
    _check_between(profile, "average_age", *AGE_RANGE)
    for standard in SHARE_MEASURES:
        _check_between(profile, standard, 0.0, 100.0)

    assets = profile["average_assets_won"]
    negative = assets < 0
    if negative.any():
        raise ValueError(
            f"{LABEL} 파일의 자산평균에 음수가 "
            f"{int(negative.sum())}건 있습니다. "
            f"예: {assets[negative].head(3).tolist()}"
        )


def _check_between(
    profile: pd.DataFrame, column: str, low: float, high: float
) -> None:
    """한 컬럼이 범위 안에 있는지 본다. 비어 있는 칸은 넘어간다."""
    values = profile[column].dropna()
    if values.empty:
        return
    outside = ~values.between(low, high)
    if not outside.any():
        return
    index = values[outside].index[0]
    row = profile.loc[index]
    raise ValueError(
        f"{LABEL} 파일의 {column}이 {low:g}~{high:g} 범위를 벗어난 행이 "
        f"{int(outside.sum())}건 있습니다. "
        f"예: {row['branch_name']} {row['base_month']} "
        f"{row['channel']} — {row[column]}. "
        "원본이 0~1 비율이면 100을 곱해 담아 주세요."
    )


def _check_keys(wide: pd.DataFrame) -> None:
    """한 지점의 한 달이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면에는 그중 하나가 조용히
    골라져 나타난다. 펴기 전에 확인해야 채널 수만큼 부풀지 않는다.
    """
    keys = pd.MultiIndex.from_arrays(
        [wide["base_month"], plain_text(wide["branch_id"])]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 기준월·지점이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id}. "
            "한 지점은 한 달에 한 행이어야 합니다."
        )


__all__ = [
    "AGE_RANGE",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "KEY_COLUMNS",
    "LABEL",
    "MEASURES",
    "SHARE_MEASURES",
    "SOURCE_NAMES",
    "build",
    "wide_name",
]
