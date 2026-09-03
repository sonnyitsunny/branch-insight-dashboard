"""원본 파일 — 상품 탭의 AI 요약.

앞의 AI요약 파일들과 컬럼도 값 형식도 같다. 읽는 일은 `ai_summary`가
맡고, 여기에는 그 파일만의 것 — 파일 이름, 환경 변수, 어느 탭의 글인지 —
만 적는다(→ revenue2_ai.py와 같은 골격).

**글의 짜임만 다르다.** 이 파일의 요약은 상품 묶음(국내주식·해외주식·
국내ETF·펀드)마다 머리줄 하나와 그 아래 몇 줄로 되어 있다. 머리줄은
원본이 `■`로 시작하게 담아 오며, 화면은 그 줄만 점 없이 굵게 적는다
(→ dashboard/metrics.py 의 is_section). 데이터 계층은 줄을 나누기만 하고
글의 짜임에는 손대지 않으므로 여기서 따로 할 일은 없다.
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import AI_TOPIC_PRODUCT
from dashboard.sources import ai_summary

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "상품_AI요약.pkl"       → data/상품_AI요약.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "상품_AI요약.pkl"
FILE_ENV = "DASHBOARD_PRODUCT_AI_FILE"

LABEL = "상품 AI요약"

# 어느 탭의 글인지 가르는 값(→ data.AI_TOPICS).
TOPIC = AI_TOPIC_PRODUCT

# 원본 컬럼명 → 내부 표준 컬럼명. AI 요약 파일이 모두 같은 이름을 쓴다.
COLUMNS = ai_summary.COLUMNS


def build(frame: pd.DataFrame, base_month: str) -> pd.DataFrame:
    return ai_summary.build(frame, base_month, TOPIC, LABEL)
