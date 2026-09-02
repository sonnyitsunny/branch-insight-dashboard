"""원본 파일 — 탭별 AI 요약을 읽는 공통 부분.

탭마다 파일이 하나씩 오고 컬럼 이름도 값 형식도 모두 같다. 그래서 읽는
일은 여기 한 번만 적고, 파일 이름·환경 변수·어느 탭 것인지만 원본 모듈이
따로 갖는다(→ customer2_ai.py, asset5_ai.py, transaction4_ai.py).

**이 모듈 자체는 원본이 아니다.** `SOURCES`에 올리지 않는다. 읽을 파일을
갖지 않고, 다른 원본 모듈이 불러 쓰는 도구다.

지점 코드 없이 지점명만 오므로 지점 코드는 여기서 붙이지 않는다. 다른
원본과 맞춰 봐야 하는 일이라 `sources/__init__.py`가 맡는다
(→ attach_branch_ids).

숫자가 아니라 글이 본체다. 한 지점의 값은 줄바꿈으로 나뉜 여러 줄이며,
줄 수는 여기서 정하지 않는다. 원본이 담은 줄을 그대로 화면까지 넘긴다.
줄 수를 세어 두면 원본이 두 줄이나 네 줄로 바뀌었을 때 값이 멀쩡한데도
멈춘다.

원본 컬럼 이름이 바뀌면 이 파일의 `COLUMNS`만 고친다. 파일마다 이름이
갈라지면 그때 원본 모듈이 제 컬럼표를 갖는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    AI_SUMMARY_COLUMN,
    AI_SUMMARY_LINE_BREAK,
)

# 원본 컬럼명 → 내부 표준 컬럼명. 두 파일이 같은 이름을 쓴다.
COLUMNS: dict[str, str] = {
    "CSMT_ORZ_NM": "branch_name",
    "TOPIC_SUMMARY": AI_SUMMARY_COLUMN,
}

# 줄을 나누는 문자. 원본이 어떤 줄바꿈으로 오든 이 하나로 맞춘다.
# 맞추지 않으면 CRLF가 화면에서 빈 줄 하나로 더 보인다. 화면도 같은
# 문자로 다시 나누므로 값은 데이터 계층에 한 번만 적는다.
LINE_BREAK = AI_SUMMARY_LINE_BREAK

# 값이 없을 때 pandas가 만드는 표기. 글자로는 채워져 있어 보이지만 비어
# 있는 값이다.
BLANK_TEXTS = ("", "nan", "None", "NaT")


def build(
    frame: pd.DataFrame, base_month: str, topic: str, label: str
) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에 기준 월과 탭 이름을 붙인다.

    원본에 기준 월 컬럼이 없으므로 월별 파일의 마지막 월을 받아 쓴다.
    `topic`은 어느 탭의 글인지 가르는 값이며 원본이 아니라 부르는 쪽이
    정한다(→ data.AI_TOPICS). 글의 내용은 손대지 않고 줄바꿈만 맞춘다.
    """
    summary = frame.loc[:, list(COLUMNS.values())].copy()
    summary["base_month"] = base_month
    summary["topic"] = topic
    summary["branch_name"] = _text(summary["branch_name"], "지점명", label)
    summary[AI_SUMMARY_COLUMN] = _text(
        summary[AI_SUMMARY_COLUMN], "요약", label
    )
    return summary


def _text(series: pd.Series, name: str, label: str) -> pd.Series:
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
            f"{label} 파일의 {name}이 비어 있는 행이"
            f" {int(blank.sum())}건 있습니다."
        )
    return text
