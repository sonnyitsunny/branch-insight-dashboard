"""원본 파일 — 지점별 AI 요약.

지점 고객2 파일과 같은 단위다. 기준 월 컬럼이 없고 지점마다 한 행인 한
시점 스냅샷이라, 월별 파일의 마지막 월을 기준 월로 받아 쓴다. 자산2와
같이 지점 요약 프레임에 컬럼 하나로 붙는다
(→ sources/__init__.py 의 merge_customer2_ai).

지점 코드 없이 지점명만 오는 첫 원본이다. 그래서 붙일 때 지점명으로
맞춘다. 지점명이 한 글자라도 다르면 어느 쪽에 없는 이름인지 알리며 멈춘다.

숫자가 아니라 글이 본체다. 한 지점의 값은 줄바꿈으로 나뉜 여러 줄이며,
줄 수는 여기서 정하지 않는다. 원본이 담은 줄을 그대로 화면까지 넘긴다.
줄 수를 세어 두면 원본이 두 줄이나 네 줄로 바뀌었을 때 값이 멀쩡한데도
멈춘다.

원본 컬럼 이름이 바뀌면 이 파일의 `COLUMNS`만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import AI_SUMMARY_LINE_BREAK

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "고객2_AI요약.pkl"       → data/고객2_AI요약.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "고객2_AI요약.pkl"
FILE_ENV = "DASHBOARD_CUSTOMER2_AI_FILE"

LABEL = "지점 고객2 AI요약"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "CSMT_ORZ_NM": "branch_name",
    "TOPIC_SUMMARY": "ai_summary",
}

# 지점 요약 프레임에 붙여 화면까지 넘길 컬럼.
# 지점명과 기준 월은 요약 프레임에 이미 있으므로 뺀다.
VALUE_COLUMNS: tuple[str, ...] = ("ai_summary",)

# 줄을 나누는 문자. 원본이 어떤 줄바꿈으로 오든 이 하나로 맞춘다.
# 맞추지 않으면 CRLF가 화면에서 빈 줄 하나로 더 보인다. 화면도 같은
# 문자로 다시 나누므로 값은 데이터 계층에 한 번만 적는다.
LINE_BREAK = AI_SUMMARY_LINE_BREAK

# 값이 없을 때 pandas가 만드는 표기. 글자로는 채워져 있어 보이지만 비어
# 있는 값이다.
BLANK_TEXTS = ("", "nan", "None", "NaT")


def build(frame: pd.DataFrame, base_month: str) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에 기준 월을 붙이고 줄바꿈을 맞춘다.

    원본에 기준 월 컬럼이 없으므로 월별 파일의 마지막 월을 받아 쓴다.
    글의 내용은 손대지 않는다.
    """
    summary = frame.loc[:, list(COLUMNS.values())].copy()
    summary["base_month"] = base_month
    summary["branch_name"] = _text(summary["branch_name"], "지점명")
    summary["ai_summary"] = _text(summary["ai_summary"], "요약")
    return summary


def _text(series: pd.Series, label: str) -> pd.Series:
    """글 컬럼. 줄바꿈만 맞추고 앞뒤 공백을 덜어 낸다.

    비어 있으면 몇 건인지 알리며 멈춘다. 빈 칸을 그대로 넘기면 화면에는
    빈 자리로 나타나, 원본이 비어 있는 것인지 읽다가 흘린 것인지 구분할
    수 없다(→ AGENTS.md §9).
    """
    text = (
        series.astype(str)
        .str.replace("\r\n", LINE_BREAK)
        .str.replace("\r", LINE_BREAK)
        .str.strip()
    )
    blank = text.isin(BLANK_TEXTS)
    if blank.any():
        raise ValueError(
            f"{LABEL} 파일의 {label}이 비어 있는 행이"
            f" {int(blank.sum())}건 있습니다."
        )
    return text
