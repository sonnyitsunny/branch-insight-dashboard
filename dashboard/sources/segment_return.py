"""원본 형태 — 구간별 수익률.

고객을 어떤 기준으로 갈라 그 무리의 1년·3년 수익률을 담은 원본들이다.
파일 이름이 모두 `수익률_seg_...` 로 시작한다. 기준월·지점·구간마다 한
행이고 그 행에 수익률 둘이 붙어 있다. 가르는 기준과 구간 목록만 다르고
단위·빈 칸·'전체' 행 규칙이 같아 조립을 여기 한 번만 적는다.

지금 쓰는 원본 — 국내주식·해외주식·ETF·개인연금 잔고 비중(→ 네 모듈이
`data.BALANCE_SHARE_GROUPS`를 함께 쓴다), 국내주식 회전율, 연령대.

**원본 파일 하나가 이 모듈을 쓰는 것이지, 이 모듈이 원본은 아니다.** 파일
이름·환경 변수·컬럼표·구간 목록은 그 원본 모듈에 그대로 남는다. 어느
원본의 컬럼 이름이 바뀌면 그 모듈의 표만 고친다(→ AGENTS.md §9). 원본
하나만 모양이 달라지면 그 모듈이 자기 `build`를 갖고 여기서 빠지면 된다.

이 모듈은 `SOURCES`에 오르지 않는다(→ dashboard/sources/__init__.py).

구간 이름 — 원본은 `1)5%미만`처럼 앞에 차례를 적어 담기도 한다. 그 번호는
떼고 읽되, 차례가 화면 차례와 같은지는 확인한다. 번호가 없는 원본(연령대)은
차례를 확인하지 않는다. 공백만 다른 표기도 같은 구간으로 읽는다
(→ data.to_ordered_label_column).

단위 — 수익률은 **%**다. 원본이 이미 %로 계산해 담고 있으므로 그대로
넘기고, 화면은 값에 `%`만 붙여 적는다. 손실이 난 기간에는 음수가 되며
0~100 범위 검사도 하지 않는다.

빈 칸 — 그 지점·구간에 고객이 없으면 수익률도 없다. 비운 채로 넘겨 화면에
`-`로 나타나게 하고 0으로 채우지 않는다. 0%는 '수익이 없었다'는 뜻이라
'값이 없다'와 다르다(→ AGENTS.md §9).

'전체' 행 — 지점 행 외에 '전체' 행도 같은 모양으로 들어 있으며, 데이터
계층이 그 행을 따로 떼어 둔다(→ dashboard/data.py). 지점 수익률의 평균이
아니라 따로 계산된 값이라 지점 합계와 대조하지 않는다.
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    plain_text,
    to_month_column,
    to_optional_number_column,
    to_ordered_label_column,
)

# 수익률 컬럼은 원본들이 이름까지 같다. 원본 이름은 오류 문구에 쓴다.
# 파일의 어디를 봐야 하는지 알려면 표준 이름이 아니라 원본 이름이어야 한다.
RATE_COLUMNS: dict[str, str] = {
    "return_1y": "수익률_1년",
    "return_3y": "수익률_3년",
}


def build(
    frame: pd.DataFrame,
    columns: dict[str, str],
    label: str,
    group_column: str,
    groups: tuple[str, ...],
    order_name: str,
) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 구간별 수익률 프레임을 만든다.

    `columns`는 그 원본 모듈의 컬럼표, `group_column`은 가르는 축의 표준
    컬럼 이름, `groups`는 그 축의 구간 목록이고 `order_name`은 목록을 적어
    둔 상수 이름이다(오류 문구에서 어디를 고치라고 알려 줄 때 쓴다).
    되돌려주는 컬럼은 컬럼표의 표준 이름 6개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    수익률 값은 고치지 않는다. 표기만 떼고 숫자로 읽는다.
    """
    segment = frame.loc[:, list(columns.values())].copy()
    segment["base_month"] = to_month_column(
        segment["base_month"], group_column
    )
    segment[group_column] = to_ordered_label_column(
        segment[group_column],
        label,
        _source_name(columns, group_column),
        groups,
        order_name,
    )
    for column, source_column in RATE_COLUMNS.items():
        segment[column] = to_optional_number_column(
            segment[column],
            label,
            source_column,
            "수익률은 %로 계산된 숫자여야 합니다.",
        )
    check_keys(segment, label, group_column)
    return segment


def _source_name(columns: dict[str, str], standard: str) -> str:
    """표준 이름에 짝이 되는 원본 컬럼 이름. 오류 문구에 쓴다."""
    for source_column, name in columns.items():
        if name == standard:
            return source_column
    return standard


def check_keys(
    segment: pd.DataFrame, label: str, group_column: str
) -> None:
    """한 지점의 한 구간이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면에는 그중 하나가 조용히
    골라져 나타난다.
    """
    keys = pd.MultiIndex.from_arrays(
        [
            segment["base_month"],
            plain_text(segment["branch_id"]),
            segment[group_column],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, group = keys[duplicated][0]
        raise ValueError(
            f"{label} 파일에 같은 지점·구간이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} {group}. "
            "한 구간은 한 번만 있어야 합니다."
        )


__all__ = ["RATE_COLUMNS", "build", "check_keys"]
