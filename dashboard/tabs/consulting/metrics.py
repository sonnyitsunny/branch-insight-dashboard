"""상담 탭의 계산.

데이터를 직접 읽지 않는다. 데이터 계층이 넘긴 프레임을 받아 화면이 쓸
형태로만 고른다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

# 화면이 매기는 순위 컬럼. 원본의 번호(topic_rank)와 다른 값이라 이름을
# 따로 둔다(→ rank_by_share).
RANK_FIELD = "share_rank"


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


def rank_by_share(rows: pd.DataFrame, group_field: str) -> pd.DataFrame:
    """분류마다 비중이 큰 것부터 세우고 1..N 순위를 매긴다.

    원본의 번호는 쓰지 않는다. 원본이 매긴 번호와 비중 순서가 다를 수
    있고, 화면이 비중 순으로 보여주는 이상 순위도 그 순서에서 나와야
    한다. 번호는 원본이 성한지 보는 데만 남는다
    (→ dashboard/sources/consulting1.py).

    분류가 나온 순서는 건드리지 않는다. 표는 그 순서대로 하나씩 생기므로
    여기서 뒤섞으면 표 차례가 바뀐다(→ registry.Table.groups).

    비중이 같으면 원본에 있던 순서를 지킨다(안정 정렬). 같은 값끼리
    자리를 바꾸면 화면을 다시 그릴 때마다 순위가 달라 보인다.
    """
    if rows.empty:
        return rows
    appeared = {
        name: index
        for index, name in enumerate(dict.fromkeys(rows[group_field]))
    }
    ranked = rows.copy()
    ranked["_group_order"] = ranked[group_field].map(appeared)
    ranked = ranked.sort_values(
        ["_group_order", "topic_share"],
        ascending=[True, False],
        kind="stable",
    )
    ranked = ranked.drop(columns="_group_order").reset_index(drop=True)
    ranked[RANK_FIELD] = (
        ranked.groupby(group_field, sort=False, observed=True).cumcount() + 1
    )
    return ranked


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
