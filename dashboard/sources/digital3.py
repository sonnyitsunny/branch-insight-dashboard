"""원본 파일 — 이용일수 구간별 채널 이용 비중.

기준월·지점·이용일수 구간마다 한 행이고, 그 한 행에 채널 셋(HTS·MTS·WEB)의
비중이 가로로 붙어 있다. 지점 행 외에 '전체' 행도 같은 모양으로 들어 있으며,
데이터 계층이 그 행을 따로 떼어 둔다(→ dashboard/data.py).

**채널이 가로로 펼쳐져 있다.** 디지털채널1·2와 같은 모양이라 여기서도 한
줄에 한 채널인 표준 형태로 편다. 행 수는 채널 수만큼 늘어난다
(→ data.DIGITAL_USAGE_DAYS_COLUMNS).

기간 — 원본이 가장 최근 달만 담고 있을 수 있다. 월별 파일보다 적은 달을
담는 것은 정상이며, 월별 파일에 없는 달이 있을 때만 멈춘다
(→ dashboard/sources/__init__.py 의 check_months_within).

구간 이름 — 원본은 `1)0일(미사용)`처럼 앞에 차례를 적어 담고, 물결 좌우의
공백도 있을 수도 없을 수도 있다. 번호를 떼고 공백을 흡수하는 일과 그 차례가
화면 차례와 같은지 보는 일은 다른 구간 원본들과 같은 규칙이라 데이터 계층의
함수를 함께 쓴다(→ data.to_ordered_label_column).

비중 — 원본이 이미 %로 계산해 담고 있어 그대로 넘긴다. 100을 곱하거나
나누지 않고, 다른 값과 견주지도 않는다(→ AGENTS.md §9). 표기(`%`, 천 단위
쉼표, 앞의 `+`)만 떼고 숫자로 읽는다.

**구간 여섯의 합이 100%가 되는지 확인하지 않는다.** 원본이 어떤 기준으로
나눈 몫인지 확정되지 않았고, 원본 값을 그대로 쓰기로 했다(→ AGENTS.md §17).

빈 칸 — 그 구간에 든 고객이 없는 지점·채널이 있을 수 있다. 비운 채로 넘겨
화면에 `-`로 나타나게 하고 0으로 채우지 않는다. 0%는 '0으로 측정됨'이라
'값이 없다'와 다르다(→ AGENTS.md §9).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    DIGITAL_CHANNELS,
    DIGITAL_USAGE_DAY_GROUPS,
    plain_text,
    to_month_column,
    to_optional_number_column,
    to_ordered_label_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "디지털채널_3.pkl"        → data/디지털채널_3.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "디지털채널_3.pkl"
FILE_ENV = "DASHBOARD_DIGITAL3_FILE"

LABEL = "디지털 채널 이용일수"

# 원본이 이용일수 구간을 담는 컬럼. 오류 문구에 이 이름을 적어야 파일의
# 어디를 봐야 하는지 알 수 있다.
GROUP_SOURCE = "이용일수"

# 채널 → 펴기 전까지만 쓰는 비중 컬럼 이름.
CHANNEL_COLUMNS: dict[str, str] = {
    channel: f"{channel.lower()}_day_group_share"
    for channel in DIGITAL_CHANNELS
}

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    GROUP_SOURCE: "usage_day_group",
    **{
        f"{channel}_이용비중": share
        for channel, share in CHANNEL_COLUMNS.items()
    },
}

# 펴기 전 키 컬럼. 채널마다 이 넷에 비중 하나가 붙는다.
KEY_COLUMNS = ["base_month", "branch_id", "branch_name", "usage_day_group"]


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 채널인 형태로 편다.

    되돌려주는 컬럼은 `data.DIGITAL_USAGE_DAYS_COLUMNS`와 그 선택 컬럼이다.
    행 수는 원본의 채널 수만큼 늘어난다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다. 구간 이름의 번호를 떼고 표기만 떼어 낸다.
    """
    wide = frame.loc[:, list(COLUMNS.values())].copy()
    wide["base_month"] = to_month_column(wide["base_month"], "digital3")
    wide["usage_day_group"] = to_ordered_label_column(
        wide["usage_day_group"],
        LABEL,
        GROUP_SOURCE,
        DIGITAL_USAGE_DAY_GROUPS,
        "DIGITAL_USAGE_DAY_GROUPS",
    )
    _check_keys(wide)

    parts = []
    for channel, share in CHANNEL_COLUMNS.items():
        part = wide.loc[:, [*KEY_COLUMNS, share]].rename(
            columns={share: "day_group_share"}
        )
        part.insert(len(KEY_COLUMNS), "channel", channel)
        part["day_group_share"] = _share(
            part["day_group_share"], f"{channel}_이용비중"
        )
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _share(series: pd.Series, column: str) -> pd.Series:
    """비중. 원본이 담은 %를 그대로 넘긴다.

    뒤에 붙은 `%`, 천 단위 쉼표, 앞에 붙은 `+`를 떼고 읽는다. 100을 곱하거나
    나누지 않는다(→ AGENTS.md §9).
    """
    return to_optional_number_column(
        series, LABEL, column, "비중은 %로 계산된 숫자여야 합니다."
    )


def _check_keys(wide: pd.DataFrame) -> None:
    """한 지점·달의 한 구간이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면에는 그중 하나가 조용히
    골라져 나타난다. 펴기 전에 확인해야 채널 수만큼 부풀지 않는다.
    """
    keys = pd.MultiIndex.from_arrays(
        [
            wide["base_month"],
            plain_text(wide["branch_id"]),
            wide["usage_day_group"],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, group = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 기준월·지점·구간이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} {group}. "
            "한 구간은 한 번만 있어야 합니다."
        )


__all__ = [
    "CHANNEL_COLUMNS",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "GROUP_SOURCE",
    "KEY_COLUMNS",
    "LABEL",
    "build",
]
