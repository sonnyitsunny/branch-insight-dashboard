"""수익률 탭의 계산.

데이터를 직접 읽지 않는다. 데이터 계층이 넘긴 프레임을 받아 화면이 쓸
형태로만 고른다(→ AGENTS.md §9).

수익률은 더할 수도 평균 낼 수도 없다. '전체' 값은 지점에서 되만들지 않고
원본이 담은 행을 그대로 쓴다(→ dashboard/sources/branch_return.py).
"""

from __future__ import annotations

import pandas as pd

# 지점 행과 '전체' 행을 가르는 표시. 그림이 색과 hover를 이 값으로 나눈다.
# '전체'를 지점 목록에 섞으면 순위가 한 칸씩 밀리고 색도 구분되지 않는다.
TOTAL_FLAG = "is_total"

RANK_COLUMNS = ("branch_name", "value", "rank", TOTAL_FLAG)
SCATTER_COLUMNS = ("branch_name", "x", "y", TOTAL_FLAG)


def _stack(
    returns: pd.DataFrame | None,
    total: pd.DataFrame | None,
    columns: dict[str, str],
) -> pd.DataFrame | None:
    """지점 행과 '전체' 행을 한 프레임으로 쌓는다.

    `columns`는 원본 컬럼 → 쓸 이름이다. 둘 중 한쪽만 있어도 되고, 둘 다
    없으면 None을 돌려준다.
    """
    parts = []
    for frame, is_total in ((returns, False), (total, True)):
        if frame is None or frame.empty:
            continue
        if any(column not in frame.columns for column in columns):
            continue
        part = frame.loc[
            :, ["branch_name", *columns]
        ].rename(columns=columns)
        part[TOTAL_FLAG] = is_total
        parts.append(part)
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True)


def return_rank(
    returns: pd.DataFrame | None,
    total: pd.DataFrame | None,
    column: str,
) -> pd.DataFrame:
    """수익률이 높은 순으로 줄 세운 목록. '전체' 행도 함께 줄 세운다.

    돌려주는 컬럼은 `RANK_COLUMNS` 넷이다.

    `rank`는 **지점 사이의** 순위이며 '전체'에는 붙이지 않는다. '전체'는
    지점이 아니라 견주는 기준이라 몇 위인지가 뜻을 갖지 않는다. 같은
    수익률이면 같은 등수를 준다.

    값이 없는 행은 뒤로 보내고 등수도 매기지 않는다. 0으로 채우면
    '수익이 0%였다'는 뜻이 되어 '값이 없다'와 달라진다(→ AGENTS.md §9).
    """
    ranked = _stack(returns, total, {column: "value"})
    if ranked is None:
        return pd.DataFrame(columns=list(RANK_COLUMNS))
    branch = ~ranked[TOTAL_FLAG]
    ranked["rank"] = (
        ranked["value"].where(branch).rank(ascending=False, method="min")
    )
    return (
        ranked.loc[:, list(RANK_COLUMNS)]
        .sort_values("value", ascending=False, na_position="last")
        .reset_index(drop=True)
    )


def branch_count(rank: pd.DataFrame) -> int:
    """줄 세운 목록에서 '전체'를 뺀 지점 수. hover의 '몇 곳 중'에 쓴다."""
    if rank.empty:
        return 0
    return int((~rank[TOTAL_FLAG]).sum())


def return_scatter(
    returns: pd.DataFrame | None,
    total: pd.DataFrame | None,
    x_column: str,
    y_column: str,
) -> pd.DataFrame:
    """가로·세로 두 수익률을 짝지은 점 목록.

    돌려주는 컬럼은 `SCATTER_COLUMNS` 넷이다.

    두 값이 모두 있는 행만 담는다. 한쪽이 비어 있으면 찍을 자리가 없다.
    빠진 값을 0으로 놓으면 그 지점이 원점 근처에 모여 없는 무리를
    만든다(→ AGENTS.md §9).
    """
    scatter = _stack(
        returns, total, {x_column: "x", y_column: "y"}
    )
    if scatter is None:
        return pd.DataFrame(columns=list(SCATTER_COLUMNS))
    return (
        scatter.loc[:, list(SCATTER_COLUMNS)]
        .dropna(subset=["x", "y"])
        .reset_index(drop=True)
    )


__all__ = [
    "RANK_COLUMNS",
    "SCATTER_COLUMNS",
    "TOTAL_FLAG",
    "branch_count",
    "return_rank",
    "return_scatter",
]
