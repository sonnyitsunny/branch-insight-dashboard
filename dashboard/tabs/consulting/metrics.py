"""상담 탭의 계산.

데이터를 직접 읽지 않는다. 데이터 계층이 넘긴 프레임을 받아 화면이 쓸
형태로만 고른다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd


def consulting_rows(
    consulting: pd.DataFrame,
    consulting_total: pd.DataFrame,
    branch_name: str,
    base_month: str,
    total_label: str,
) -> pd.DataFrame:
    """고른 지점·기준월의 상담 행.

    '전체'는 지점 행을 더해 만들지 않는다. 원본이 따로 뽑아 둔 '전체' 행을
    그대로 쓴다. 토픽은 더할 수 있는 값이 아니라 지점마다 다른 목록이다.
    """
    frame = (
        consulting_total if branch_name == total_label else consulting
    )
    if frame.empty:
        return frame
    chosen = frame
    if branch_name != total_label:
        chosen = chosen[chosen["branch_name"] == branch_name]
    if base_month:
        chosen = chosen[chosen["base_month"] == base_month]
    return chosen.reset_index(drop=True)


def scope_names(
    consulting: pd.DataFrame,
    consulting_total: pd.DataFrame,
    total_label: str,
) -> list[str]:
    """지점 선택 목록. 원본에 '전체' 행이 있으면 맨 앞에 둔다."""
    names = sorted(consulting["branch_name"].unique().tolist())
    if consulting_total.empty:
        return names
    return [total_label, *names]


def months(consulting: pd.DataFrame) -> list[str]:
    """기준월 선택 목록. 최근 달이 위로 오게 한다."""
    return sorted(consulting["base_month"].unique().tolist(), reverse=True)
