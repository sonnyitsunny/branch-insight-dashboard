"""원본 파일 — 월별 지점 입출금.

기준월·지점마다 한 행이고, 증권·은행 채널이 가로로 펼쳐져 각각 입금·출금·
순입금 세 컬럼을 차지한다. 데이터 계층은 한 줄에 한 채널인 형태로 편다.

'전체' 채널에는 순입금만 있다. 원본이 입금·출금을 주지 않으므로 그 두 칸은
비운 채로 넘겨 화면에 `-`로 나타나게 한다. 순입금도 두 채널의 합으로 만들지
않고 원본 값을 그대로 쓴다(→ AGENTS.md §9).

단위 — 모두 **억원**이다. 거래1·거래2와 같은 약속이다.

부호 — 순입금은 빠져나간 달에 음수가 된다. 인원수와 달리 음수를 막지
않는다. 출금이 어떤 부호로 담겨 오는지는 원본이 정하며, 여기서 부호를
바꾸거나 `순입금 = 입금 - 출금`인지 확인하지 않는다. 확인하려면 규약을
먼저 정해야 하고, 잘못 정하면 맞는 데이터를 틀렸다고 막게 된다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dashboard.data import (
    CASH_FLOW_CHANNEL_TOTAL,
    CASH_FLOW_CHANNELS,
    plain_text,
    to_month_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "거래3.pkl"              → data/거래3.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "거래3.pkl"
FILE_ENV = "DASHBOARD_TRANSACTION3_FILE"

LABEL = "지점 거래3"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
}

_KEY_COLUMNS = ("base_month", "branch_id", "branch_name")

# 채널 → (입금 컬럼, 출금 컬럼, 순입금 컬럼).
# 입금·출금이 None이면 원본에 그 컬럼이 없다는 뜻이다. 비운 채로 넘긴다.
CHANNEL_COLUMNS: dict[str, tuple[str | None, str | None, str]] = {
    "증권": ("입금_증권", "출금_증권", "순입금_증권"),
    "은행": ("입금_은행", "출금_은행", "순입금_은행"),
    CASH_FLOW_CHANNEL_TOTAL: (None, None, "순입금_전체"),
}

DEPOSIT_COLUMN = "deposit_amount"
WITHDRAWAL_COLUMN = "withdrawal_amount"
NET_COLUMN = "net_amount"


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 채널인 형태로 편다.

    되돌려주는 컬럼은 base_month·branch_id·branch_name·channel·
    deposit_amount·withdrawal_amount·net_amount 일곱 개다.
    """
    _check_columns(frame)
    parts = []
    for channel, columns in CHANNEL_COLUMNS.items():
        parts.append(_channel_part(frame, channel, columns))
    long = pd.concat(parts, ignore_index=True)
    long["base_month"] = to_month_column(long["base_month"], "transaction3")
    _check_keys(long)
    return long


def _channel_part(
    frame: pd.DataFrame,
    channel: str,
    columns: tuple[str | None, str | None, str],
) -> pd.DataFrame:
    """채널 하나를 표준 컬럼 이름으로 잘라 낸다."""
    standard = (DEPOSIT_COLUMN, WITHDRAWAL_COLUMN, NET_COLUMN)
    found = [column for column in columns if column is not None]
    part = frame.loc[:, [*_KEY_COLUMNS, *found]].rename(
        columns={
            column: name
            for column, name in zip(columns, standard)
            if column is not None
        }
    )
    for column, name in zip(columns, standard):
        if column is None:
            part[name] = np.nan
    part.insert(len(_KEY_COLUMNS), "channel", channel)
    return part.loc[:, [*_KEY_COLUMNS, "channel", *standard]]


def _check_columns(frame: pd.DataFrame) -> None:
    """채널 컬럼이 모두 있는지 본다. 없으면 이름을 알리며 멈춘다."""
    missing = [
        column
        for columns in CHANNEL_COLUMNS.values()
        for column in columns
        if column is not None and column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{LABEL} 파일에 다음 컬럼이 없습니다: {', '.join(missing)}. "
            "원본의 채널 컬럼 이름이 바뀌었으면 "
            "dashboard/sources/transaction3.py 의 CHANNEL_COLUMNS 를 고쳐 "
            f"주세요. 파일에 있는 컬럼: {', '.join(map(str, frame.columns))}"
        )
    allowed = {CASH_FLOW_CHANNEL_TOTAL, *CASH_FLOW_CHANNELS}
    unknown = sorted(set(CHANNEL_COLUMNS) - allowed)
    if unknown:
        raise ValueError(
            f"{LABEL} 의 CHANNEL_COLUMNS 에 화면이 모르는 채널이 있습니다: "
            f"{', '.join(unknown)}. dashboard/data.py 의 "
            "CASH_FLOW_CHANNELS 에도 더해 주세요."
        )


def _check_keys(long: pd.DataFrame) -> None:
    """한 지점의 한 달이 한 번씩만 있는지 본다."""
    keys = pd.MultiIndex.from_arrays(
        [
            long["base_month"],
            plain_text(long["branch_id"]),
            long["channel"],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, channel = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 기준월·지점이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} ({channel}). "
            "한 지점은 한 달에 한 행이어야 합니다."
        )
