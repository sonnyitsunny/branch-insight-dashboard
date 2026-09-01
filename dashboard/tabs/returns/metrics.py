"""수익률 탭의 계산.

데이터를 직접 읽지 않는다. 데이터 계층이 넘긴 프레임을 받아 화면이 쓸
형태로만 고른다(→ AGENTS.md §9).

수익률은 더할 수도 평균 낼 수도 없다. '전체' 값은 지점에서 되만들지 않고
원본이 담은 행을 그대로 쓴다(→ dashboard/sources/branch_return.py).
고객 비중도 원본이 이미 계산해 담고 있으면 그 값을 그대로 쓴다
(→ dashboard/sources/return_group.py).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import RETURN_GROUPS, TOTAL_LABEL
from dashboard.metrics import resolve_current_month, share_percent

# 지점 행과 '전체' 행을 가르는 표시. 그림이 색과 hover를 이 값으로 나눈다.
# '전체'를 지점 목록에 섞으면 순위가 한 칸씩 밀리고 색도 구분되지 않는다.
TOTAL_FLAG = "is_total"

RANK_COLUMNS = ("branch_name", "value", "rank", TOTAL_FLAG)
SCATTER_COLUMNS = ("branch_name", "x", "y", TOTAL_FLAG)
# 구간별 비중 그림이 쓰는 컬럼. `scope`는 '전체'이거나 고른 지점 이름이며,
# 그림이 이 값으로 계열을 나눈다.
GROUP_COLUMNS = ("return_group", "scope", "customer_count", "share")
# 구간별 수익률 그림이 쓰는 컬럼. 가르는 축이 무엇이든 같은 이름을 쓴다.
# `수익률_seg_...` 원본 일곱이 한 함수를 함께 쓰기 때문이다
# (→ segment_returns).
SEGMENT_COLUMNS = ("segment", "scope", "value")


def _stack(
    returns: pd.DataFrame | None,
    total: pd.DataFrame | None,
    columns: dict[str, str],
) -> pd.DataFrame | None:
    """지점 행과 '전체' 행을 한 프레임으로 쌓는다.

    `columns`는 원본 컬럼 → 쓸 이름이다. 둘 중 한쪽만 있어도 되고, 둘 다
    없으면 None을 돌려준다.

    원본이 여러 달을 담고 있으면 최신 월만 남긴다. 두 달이 섞여 들어오면
    지점마다 막대가 두 개씩 서고 산점도에도 같은 지점 점이 여럿 찍힌다.
    오류 없이 그럴듯하게 그려져 알아채기 어렵다(→ _month_period).

    기준 월은 지점 행에서 정하고 '전체' 행에도 같은 달을 쓴다. 두 프레임은
    한 파일에서 갈라져 나온 것이라 달이 어긋날 수 없다.
    """
    month = _latest_of(returns, total)
    parts = []
    for frame, is_total in ((returns, False), (total, True)):
        if frame is None or frame.empty:
            continue
        if any(column not in frame.columns for column in columns):
            continue
        rows = frame
        if month is not None:
            rows = rows[rows["base_month"] == month]
            if rows.empty:
                continue
        part = rows.loc[
            :, ["branch_name", *columns]
        ].rename(columns=columns)
        part[TOTAL_FLAG] = is_total
        parts.append(part)
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True)


def _latest_of(*frames: pd.DataFrame | None) -> str | None:
    """먼저 오는 비어 있지 않은 프레임의 최신 월. 없으면 None.

    기준 월 컬럼이 없는 프레임을 받으면 None이 되어 거르지 않는다. 그런
    프레임은 이미 한 달치만 골라 넘긴 것이다.
    """
    for frame in frames:
        if frame is None or frame.empty:
            continue
        return resolve_current_month(frame, None)
    return None


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


def return_group_distribution(
    return_group: pd.DataFrame | None,
    total: pd.DataFrame | None,
    branch_name: str,
    period: str,
) -> pd.DataFrame:
    """'전체'와 고른 지점의 수익률 구간별 고객 비중.

    돌려주는 컬럼은 `GROUP_COLUMNS` 넷이고, 구간마다 계열이 둘(전체·지점)
    나온다. 지점 하나만 골라도 '전체'는 늘 함께 담는다. 견줄 기준이 없으면
    한 지점의 분포가 높은지 낮은지 알 수 없다.

    기간(1년·3년)은 원본이 한 컬럼에 담고 있어 여기서 걸러 낸다
    (→ data.RETURN_PERIODS).

    '전체'는 원본의 '전체' 행을 그대로 쓴다. 그 행이 없을 때만 지점 행을
    모아 만든다. 비중은 더할 수 없으므로 그때는 인원수에서 다시 계산한다.

    원본이 한 달만 담고 있어도 최신 월만 남긴다. 두 달이 섞여 들어오면
    같은 구간이 두 번 세어져 막대 높이가 두 배가 된다.
    """
    empty = pd.DataFrame(columns=list(GROUP_COLUMNS))
    if return_group is None or return_group.empty:
        return empty

    rows = _month_period(return_group, period)
    if rows.empty:
        return empty

    total_rows = (
        pd.DataFrame()
        if total is None or total.empty
        else _month_period(total, period)
    )
    frames = [
        _group_frame(
            total_rows if not total_rows.empty else rows, TOTAL_LABEL
        )
    ]
    branch_rows = rows[rows["branch_name"] == branch_name]
    if not branch_rows.empty:
        frames.append(_group_frame(branch_rows, branch_name))
    return pd.concat(frames, ignore_index=True)


def _month_period(frame: pd.DataFrame, period: str) -> pd.DataFrame:
    """최신 월의 그 기간 행만 고른다."""
    month = resolve_current_month(frame, None)
    if month is None:
        return frame.iloc[0:0]
    return frame[
        (frame["base_month"] == month)
        & (frame["return_period"] == period)
    ]


def segment_returns(
    segment: pd.DataFrame | None,
    total: pd.DataFrame | None,
    branch_name: str,
    group_column: str,
    groups: tuple[str, ...],
    column: str,
) -> pd.DataFrame:
    """'전체'와 고른 지점의 구간별 수익률.

    돌려주는 컬럼은 `SEGMENT_COLUMNS` 셋이고, 구간마다 계열이 둘(전체·
    지점) 나온다. `group_column`은 가르는 축의 컬럼(예: `asset_group`),
    `groups`는 그 축의 구간 차례, `column`은 고른 기간의 수익률 컬럼이다.
    `수익률_seg_...` 원본 일곱이 모두 이 모양이라 함께 쓴다
    (→ dashboard/sources/segment_return.py).

    수익률은 더할 수도 평균 낼 수도 없다. '전체'는 원본의 '전체' 행을
    그대로 쓰고, 그 행이 없으면 비워 둔다. 지점 값에서 되만들지
    않는다(→ AGENTS.md §9).

    값이 없는 구간은 비운 채로 남긴다. 0으로 채우면 '수익이 0%였다'는
    뜻이 되어 '값이 없다'와 달라진다.
    """
    empty = pd.DataFrame(columns=list(SEGMENT_COLUMNS))
    if segment is None or segment.empty:
        return empty
    if group_column not in segment.columns or column not in segment.columns:
        return empty

    frames = []
    for rows, scope in (
        (total, TOTAL_LABEL),
        (segment[segment["branch_name"] == branch_name], branch_name),
    ):
        if rows is None or rows.empty:
            continue
        frames.append(
            _segment_frame(rows, scope, group_column, groups, column)
        )
    if not frames:
        return empty
    return pd.concat(frames, ignore_index=True)


def _segment_frame(
    rows: pd.DataFrame,
    scope: str,
    group_column: str,
    groups: tuple[str, ...],
    column: str,
) -> pd.DataFrame:
    """한 계열의 구간별 값. 구간은 늘 같은 차례로 늘어선다.

    한 구간에 행이 둘 이상이면 첫 행을 쓴다. 원본 모듈이 이미 한 지점의
    한 구간이 한 번씩만 있는지 확인했으므로 그런 일은 없어야 한다
    (→ dashboard/sources/segment_return.py 의 check_keys).
    """
    values = (
        rows.drop_duplicates(subset=[group_column])
        .set_index(group_column)[column]
        .reindex(list(groups))
    )
    return pd.DataFrame(
        {
            "segment": list(groups),
            "scope": scope,
            "value": values.to_numpy(dtype=float),
        }
    )


def _group_frame(rows: pd.DataFrame, scope: str) -> pd.DataFrame:
    """구간별 고객 수와 비중. 구간은 늘 같은 차례로 늘어선다.

    원본이 담은 비중을 그대로 쓴다. 인원수에서 다시 만들면 반올림 때문에
    화면 숫자가 원본과 달라진다(→ AGENTS.md §9). 다만 그 비중은 지점
    하나를 기준으로 계산된 값이라 여러 지점을 묶을 때는 쓸 수 없다.
    그때와 원본이 비중을 아예 담지 않았을 때만 인원수에서 계산한다.

    원본에 없는 구간은 비워 둔다. 0으로 채우면 '그 구간 고객이 0명'이
    되어 '값이 없다'와 뜻이 달라진다. 한 계열 안에서 어떤 구간은 원본
    값을, 어떤 구간은 인원수 기준 값을 쓰지 않는다. 기준이 섞이면 막대
    높이끼리 견줄 수 없다.
    """
    counts = (
        rows.groupby("return_group", observed=True)["customer_count"]
        .sum(min_count=1)
        .reindex(list(RETURN_GROUPS))
    )
    denominator = float(counts.sum())
    shares = [share_percent(value, denominator) for value in counts]
    if "customer_share" in rows.columns and rows["branch_id"].nunique() == 1:
        given = (
            rows.set_index("return_group")["customer_share"]
            .reindex(list(RETURN_GROUPS))
        )
        if given.notna().any():
            shares = [
                None if pd.isna(value) else float(value) for value in given
            ]
    return pd.DataFrame(
        {
            "return_group": list(RETURN_GROUPS),
            "scope": scope,
            "customer_count": counts.to_numpy(),
            "share": shares,
        }
    )


__all__ = [
    "GROUP_COLUMNS",
    "RANK_COLUMNS",
    "SCATTER_COLUMNS",
    "SEGMENT_COLUMNS",
    "TOTAL_FLAG",
    "branch_count",
    "return_group_distribution",
    "return_rank",
    "return_scatter",
    "segment_returns",
]
