"""원본 파일 — 지점별 수익률.

기준월·지점마다 한 행이고 '전체' 합계 행이 하나 더 있다. 그 한 행에 1년
수익률과 3년 수익률이 붙어 있다. 분류축이 없어 순위표들보다 단순하다.

단위 — 수익률은 **%**다. 원본이 이미 %로 계산해 담고 있으므로 그대로
넘기고, 화면은 값에 `%`만 붙여 적는다(→ dashboard/format.py 의
format_signed_percent). 0~1 비율로 보고 100을 곱하면 값이 100배가 된다.
반대로 원본이 0~1로 바뀌었는데 그대로 쓰면 모든 수익률이 0%로 보인다.

부호 — 수익률은 손실이 난 기간에 음수가 된다. 인원수와 달리 음수를 막지
않는다. 0~100 범위 검사도 하지 않는다. 수익률은 100%를 넘을 수도, 0보다
작을 수도 있다.

빈 칸 — 그 기간의 수익률이 없는 지점이 있을 수 있다. 비운 채로 넘겨
화면에 `-`로 나타나게 하고 0으로 채우지 않는다. 0%는 '수익이 없었다'는
뜻이라 '값이 없다'와 다르다(→ AGENTS.md §9).

'전체' 행 — 지점 수익률의 평균이 아니라 따로 계산된 값이다. 수익률은
더할 수 없으므로 지점 합계와 대조하지 않는다
(→ dashboard/data.py 의 _TOTAL_CHECK_COLUMNS).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    plain_text,
    strip_number_marks,
    to_month_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익률_지점별.pkl"     → data/수익률_지점별.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_지점별.pkl"
FILE_ENV = "DASHBOARD_BRANCH_RETURN_FILE"

LABEL = "지점별 수익률"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "수익률_1년": "return_1y",
    "수익률_3년": "return_3y",
}

# 수익률 컬럼 → 원본 컬럼 이름. 오류 문구에 원본 이름을 적어야 파일의
# 어디를 봐야 하는지 알 수 있다.
RATE_COLUMNS: dict[str, str] = {
    "return_1y": "수익률_1년",
    "return_3y": "수익률_3년",
}

# 비어 있는 값으로 읽는 표기. 부호만 있고 숫자가 없는 `-`는 수익률이 될 수
# 없으므로 여기 넣는다. `-5.2`처럼 숫자가 붙은 값은 통째로 견주므로 걸리지
# 않는다.
BLANK_RATE = ("", "-", "+", "nan", "None", "NaT")


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 지점별 수익률 프레임을 만든다.

    되돌려주는 컬럼은 `COLUMNS`의 표준 이름 5개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    수익률 값은 고치지 않는다. 표기만 떼고 숫자로 읽는다.
    """
    returns = frame.loc[:, list(COLUMNS.values())].copy()
    returns["base_month"] = to_month_column(
        returns["base_month"], "branch_return"
    )
    for column, label in RATE_COLUMNS.items():
        returns[column] = _rate(returns[column], label)
    _check_keys(returns)
    return returns


def _rate(series: pd.Series, column: str) -> pd.Series:
    """수익률을 소수로 맞춘다.

    뒤에 붙은 `%`, 천 단위 쉼표, 앞에 붙은 `+`를 떼고 읽는다. 비어 있는
    칸은 비운 채로 두고(→ BLANK_RATE) 0으로 채우지 않는다. 값이 있는데
    숫자로 읽을 수 없으면 어떤 값인지 알리며 멈춘다.
    """
    text = strip_number_marks(
        plain_text(series).str.removesuffix("%").str.strip()
    )
    blank = text.isin(BLANK_RATE)
    numbers = pd.to_numeric(text.where(~blank), errors="coerce")
    unreadable = numbers.isna() & ~blank
    if unreadable.any():
        raise ValueError(
            f"{LABEL} 파일의 {column} 을 숫자로 읽을 수 없는 값이"
            f" {int(unreadable.sum())}건 있습니다. "
            f"예: {text[unreadable].head(3).tolist()}. "
            "수익률은 %로 계산된 숫자여야 합니다."
        )
    return numbers.astype(float)


def _check_keys(returns: pd.DataFrame) -> None:
    """한 지점의 한 달이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면에는 그중 하나가 조용히
    골라져 나타난다.
    """
    keys = pd.MultiIndex.from_arrays(
        [returns["base_month"], plain_text(returns["branch_id"])]
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
    "BLANK_RATE",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "LABEL",
    "RATE_COLUMNS",
    "build",
]
