"""원본 파일 — 수익 탭의 AI 요약.

앞의 AI요약 파일들과 컬럼도 값 형식도 같다. 읽는 일은 `ai_summary`가
맡고, 여기에는 그 파일만의 것 — 파일 이름, 환경 변수, 어느 탭의 글인지 —
만 적는다(→ customer2_ai.py와 같은 골격).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import AI_TOPIC_REVENUE
from dashboard.sources import ai_summary

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익2_AI요약.pkl"       → data/수익2_AI요약.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익2_AI요약.pkl"
FILE_ENV = "DASHBOARD_REVENUE2_AI_FILE"

LABEL = "지점 수익2 AI요약"

# 어느 탭의 글인지 가르는 값(→ data.AI_TOPICS).
TOPIC = AI_TOPIC_REVENUE

# 원본 컬럼명 → 내부 표준 컬럼명. AI 요약 파일이 모두 같은 이름을 쓴다.
COLUMNS = ai_summary.COLUMNS


def build(frame: pd.DataFrame, base_month: str) -> pd.DataFrame:
    return ai_summary.build(frame, base_month, TOPIC, LABEL)
