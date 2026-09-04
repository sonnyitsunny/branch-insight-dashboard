"""원본 파일 — 지점 상담 토픽.

기준월 × 지점 × 상담구분마다 번호 1..N의 토픽이 들어 있다. 지점 행 외에
'전체' 행도 같은 모양으로 들어 있으며, 데이터 계층이 그 행을 따로 떼어
둔다(→ dashboard/data.py).

숫자가 아니라 글이 본체인 첫 원본이다. 토픽·주요내용은 그대로 화면까지
가고, 비중만 숫자로 다룬다.

번호는 화면에 쓰지 않는다. 원본이 성한지 보는 데만 쓴다 — 한 묶음에
번호가 겹치는지 확인하는 자리다(→ check_topic_numbers). 화면의 순위는
비중이 큰 것부터 다시 매긴다(→ dashboard/tabs/consulting/metrics.py).

비중 단위 — 원본이 `16%`처럼 값에 기호를 달고 온다. 기호를 떼고 숫자로
읽으며, 기호가 붙어 있으면 %(0~100)라는 뜻이므로 단위를 더 따지지 않는다.
기호 없이 숫자만 오는 파일이면 %(0~100)로 보고, 0~1 비율이면
`SHARE_IN_RATIO`를 True로 바꾼다. 값을 보고 저절로 바꾸지 않는다.
10%를 0.1로 적어 두면 화면에는 "0.1%"가 뜨는데, 그 숫자만으로는 틀린 줄
알 수 없기 때문이다. 대신 전부 1 이하이면 설정이 어긋났다고 보고 멈춘다.

원본 컬럼 이름이 바뀌면 이 파일의 `COLUMNS`만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    plain_text,
    to_month_column,
    to_numeric_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "상담1.pkl"              → data/상담1.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "상담1.pkl"
FILE_ENV = "DASHBOARD_CONSULTING1_FILE"

LABEL = "지점 상담1"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "지점코드": "branch_id",
    "지점명": "branch_name",
    "상담구분": "consulting_type",
    "번호": "topic_rank",
    "토픽": "topic",
    "주요내용": "topic_summary",
    "비중": "topic_share",
}

# 값에 붙어 오는 기호. 떼고 숫자로 읽는다.
PERCENT_SIGN = "%"

# 기호 없이 숫자만 오고 그 숫자가 0~1 비율이면 True로 바꾼다. 그러면 100을
# 곱해 %로 맞춘다. 값에 기호가 붙어 있으면 이미 %라는 뜻이라 함께 켤 수 없다.
SHARE_IN_RATIO = False

# 글로 다루는 컬럼. 숫자 코드로 들어와도 문자열로 맞춘다.
TEXT_COLUMNS: tuple[str, ...] = ("consulting_type", "topic", "topic_summary")


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 상담 프레임을 만든다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    행 순서(번호)는 데이터 계층이 정렬로 다시 맞추므로 여기서는 값만 본다.
    """
    consulting = frame.loc[:, list(COLUMNS.values())].copy()
    consulting["base_month"] = to_month_column(
        consulting["base_month"], "consulting1"
    )
    for column in TEXT_COLUMNS:
        consulting[column] = _text(consulting[column], column)
    consulting["topic_share"] = _share(consulting["topic_share"])
    check_topic_numbers(consulting)
    return consulting


def _text(series: pd.Series, column: str) -> pd.Series:
    """글 컬럼. 비어 있으면 어느 컬럼인지 알리며 멈춘다.

    빈 칸을 그대로 넘기면 화면에는 빈 셀로 나타나, 원본이 비어 있는 것인지
    읽다가 흘린 것인지 구분할 수 없다.
    """
    text = plain_text(series)
    blank = text.isin(("", "nan", "None", "NaT"))
    if blank.any():
        raise ValueError(
            f"{LABEL} 파일의 {column} 이 비어 있는 행이"
            f" {int(blank.sum())}건 있습니다."
        )
    return text


def _share(series: pd.Series) -> pd.Series:
    """비중을 %(0~100) 숫자로 맞춘다.

    `16%`처럼 기호가 붙어 오면 기호만 뗀다. 숫자로 읽을 수 없는 값은 조용히
    버리지 않고 그 값을 알리며 멈춘다(→ to_numeric_column).

    설정과 실제 값이 어긋나도 멈춘다. 조용히 넘기면 화면 숫자가 100배
    어긋난 채로 그럴듯하게 보인다.
    """
    values, signed = _strip_percent_sign(series)
    if signed and SHARE_IN_RATIO:
        raise ValueError(
            f"{LABEL} 파일의 비중에 '{PERCENT_SIGN}' 기호가 붙어 있는데"
            " consulting1.py 의 SHARE_IN_RATIO 가 켜져 있습니다. "
            "기호가 붙어 있으면 이미 %이므로 SHARE_IN_RATIO 를 False 로"
            " 두세요."
        )
    numbers = to_numeric_column(values, LABEL, "비중")
    if SHARE_IN_RATIO:
        numbers = numbers * 100.0
    outside = ~numbers.between(0, 100)
    if outside.any():
        raise ValueError(
            f"{LABEL} 파일의 비중이 0~100 범위를 벗어난 행이"
            f" {int(outside.sum())}건 있습니다. "
            f"예: {numbers[outside].head(3).tolist()}. "
            "원본이 0~1 비율이면 consulting1.py 의 SHARE_IN_RATIO 를 True 로"
            " 바꿔 주세요."
        )
    # 기호가 붙어 있으면 단위가 분명하므로 더 따지지 않는다.
    if (
        not signed
        and not SHARE_IN_RATIO
        and numbers.max() <= 1
        and numbers.nunique() > 1
    ):
        raise ValueError(
            f"{LABEL} 파일의 비중이 모두 1 이하입니다. 원본이 0~1 비율이면"
            " consulting1.py 의 SHARE_IN_RATIO 를 True 로 바꿔 주세요. "
            "이미 %라면 이 확인을 지워 주세요."
        )
    return numbers.astype(float)


def _strip_percent_sign(series: pd.Series) -> tuple[pd.Series, bool]:
    """`16%`에서 기호를 뗀다. 기호가 하나라도 있었는지 함께 돌려준다.

    숫자로 들어오는 파일도 있으므로 글일 때만 손댄다.
    """
    if not pd.api.types.is_object_dtype(series):
        return series, False
    text = series.astype(str).str.strip()
    signed = bool(text.str.endswith(PERCENT_SIGN).any())
    if not signed:
        return text, False
    return text.str.removesuffix(PERCENT_SIGN).str.strip(), True


def check_topic_numbers(consulting: pd.DataFrame) -> None:
    """한 묶음 안에서 번호가 겹치지 않는지 본다.

    기준월·지점·상담구분마다 번호가 1..N으로 한 번씩 나와야 한다. 겹치면
    표에 같은 순위가 두 번 나오고, 어느 쪽이 맞는지 화면에서는 알 수 없다.
    """
    keys = ["base_month", "branch_id", "consulting_type", "topic_rank"]
    duplicated = consulting.duplicated(subset=keys)
    if duplicated.any():
        row = consulting.loc[duplicated].iloc[0]
        raise ValueError(
            f"{LABEL} 파일에 같은 번호가 두 번 이상 있습니다: "
            f"{row['base_month']} {row['branch_name']} "
            f"{row['consulting_type']} {row['topic_rank']}번. "
            f"겹치는 행이 {int(duplicated.sum())}건입니다."
        )
