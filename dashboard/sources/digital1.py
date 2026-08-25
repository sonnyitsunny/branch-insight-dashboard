"""원본 파일 — 지점 디지털 채널 이용 현황.

기준월·지점마다 한 행이고 '전체' 합계 행이 하나 더 있다. 그 한 행에 채널
셋(HTS·MTS·WEB)의 이용 고객 수와 이용 비중이 가로로 붙어 있다.

**한 행에 두 가지 단위가 섞여 있다.** 채널로 나뉘는 값과 그렇지 않은 값이
같이 온다. 그래서 이 모듈은 프레임을 둘로 나눠 내놓는다.

- `build` — 표준 이름으로 맞춘 지점 × 기준월 프레임. `VALUE_COLUMNS`가
  월별 프레임에 붙는다(→ dashboard/sources/__init__.py 의
  merge_digital_values).
- `build_channel` — 위 프레임을 한 줄에 한 채널인 형태로 편 것
  (→ data.DIGITAL_CHANNEL_COLUMNS).

값 — 원본이 담은 값을 그대로 화면까지 넘긴다. 인원수에서 비중을 다시
만들지도, 비중을 인원수와 견주지도 않는다(→ AGENTS.md §9). 표기(`%`, 천
단위 쉼표, 앞의 `+`)만 떼고 숫자로 읽는다.

고객수·거래고객수 — 채널로 나뉘지 않아 월별 프레임에 붙는다. **월별 파일이
주는 값과 견주지 않는다.** 이 파일의 고객수는 `digital_customer_count`로,
월별 파일의 값은 `customer_count`로 따로 간다. 두 값이 다르면 다른 대로
두고 어느 쪽으로도 덮지 않는다. 어느 쪽이 맞는지 가릴 근거가 없기 때문이다
(→ data.MONTHLY_DIGITAL_COLUMNS).

거래고객수는 **거래1이 주는 '전체' 상품 거래고객수와 같은 지표인지 확인되지
않았다.** 같은 값이면 이름을 하나로 합쳐야 하는데 어느 쪽인지 정해지지 않아
지금은 따로 들고 간다(→ AGENTS.md §17).

**세 채널의 비중을 더하면 100%를 넘을 수 있다.** 한 고객이 HTS와 MTS를 모두
쓰면 양쪽에 들어간다. 구성비가 아니므로 100%가 되는지 확인하지 않고, 화면도
100% 누적 막대로 그리지 않는다(→ data.DIGITAL_CHANNELS).

빈 칸 — 그 채널을 쓴 고객이 원본에 없는 지점·달이 있을 수 있다. 비운 채로
넘겨 화면에 `-`로 나타나게 하고 0으로 채우지 않는다. 0명은 '아무도 쓰지
않았다'는 뜻이라 '값이 없다'와 다르다(→ AGENTS.md §9).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    DIGITAL_CHANNELS,
    DIGITAL_CUSTOMER_COLUMN,
    DIGITAL_TRADE_COUNT_COLUMN,
    DIGITAL_TRADE_SHARE_COLUMN,
    MONTHLY_DIGITAL_COLUMNS,
    check_not_negative,
    plain_text,
    to_month_column,
    to_optional_number_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "디지털채널_1.pkl"        → data/디지털채널_1.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "디지털채널_1.pkl"
FILE_ENV = "DASHBOARD_DIGITAL1_FILE"

LABEL = "디지털 채널 이용"

# 채널 → (이용 고객 수, 이용 비중)의 표준 컬럼 이름. 채널 이름은 데이터
# 계층이 정한다(→ data.DIGITAL_CHANNELS). 여기 다시 적으면 한 화면 안에서
# 같은 채널이 다른 이름으로 나타난다.
CHANNEL_COLUMNS: dict[str, tuple[str, str]] = {
    channel: (
        f"{channel.lower()}_user_count",
        f"{channel.lower()}_user_share",
    )
    for channel in DIGITAL_CHANNELS
}

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "고객수": DIGITAL_CUSTOMER_COLUMN,
    "거래고객수": DIGITAL_TRADE_COUNT_COLUMN,
    "거래고객비중": DIGITAL_TRADE_SHARE_COLUMN,
    **{
        f"{channel}_이용고객수": count
        for channel, (count, _share) in CHANNEL_COLUMNS.items()
    },
    **{
        f"{channel}_이용비중": share
        for channel, (_count, share) in CHANNEL_COLUMNS.items()
    },
}

# 월별 프레임에 붙일 컬럼(→ dashboard/sources/__init__.py 의
# merge_digital_values).
VALUE_COLUMNS = MONTHLY_DIGITAL_COLUMNS

# 표준 컬럼 → 원본 컬럼 이름. 오류 문구에 원본 이름을 적어야 파일의 어디를
# 봐야 하는지 알 수 있다.
SOURCE_NAMES: dict[str, str] = {
    standard: source for source, standard in COLUMNS.items()
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 지점 × 기준월 프레임을 만든다.

    되돌려주는 컬럼은 `COLUMNS`의 표준 이름 12개다. 채널로 펴는 일은
    `build_channel`이 맡는다.

    기준 월은 `202507`이든 `2025-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다. 표기만 떼고 숫자로 읽는다.
    """
    usage = frame.loc[:, list(COLUMNS.values())].copy()
    usage["base_month"] = to_month_column(usage["base_month"], "digital1")
    for count, share in CHANNEL_COLUMNS.values():
        usage[count] = _optional_count(usage[count])
        usage[share] = _share(usage[share])
    usage[DIGITAL_CUSTOMER_COLUMN] = _optional_count(
        usage[DIGITAL_CUSTOMER_COLUMN]
    )
    usage[DIGITAL_TRADE_COUNT_COLUMN] = _optional_count(
        usage[DIGITAL_TRADE_COUNT_COLUMN]
    )
    usage[DIGITAL_TRADE_SHARE_COLUMN] = _share(
        usage[DIGITAL_TRADE_SHARE_COLUMN]
    )
    _check_keys(usage)
    return usage


def build_channel(usage: pd.DataFrame) -> pd.DataFrame:
    """지점 × 기준월 프레임을 한 줄에 한 채널인 형태로 편다.

    되돌려주는 컬럼은 `data.DIGITAL_CHANNEL_COLUMNS`와 그 선택 컬럼이다.
    행 수는 채널 수만큼 늘어난다.
    """
    keys = ["base_month", "branch_id", "branch_name"]
    parts = []
    for channel, (count, share) in CHANNEL_COLUMNS.items():
        part = usage.loc[:, [*keys, count, share]].rename(
            columns={count: "user_count", share: "user_share"}
        )
        part.insert(len(keys), "channel", channel)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _optional_count(series: pd.Series) -> pd.Series:
    """이용 고객 수. 비어 있는 칸은 비운 채로 둔다.

    숫자로 읽을 수 있는 값 중에 음수가 있으면 멈춘다. 사람 수가 음수일
    수는 없으므로 원본을 읽는 방법이 틀렸다는 뜻이다.
    """
    name = SOURCE_NAMES.get(series.name, str(series.name))
    numbers = to_optional_number_column(
        series, LABEL, name, "이용 고객 수는 사람 수여야 합니다."
    )
    check_not_negative(numbers.dropna(), LABEL, name)
    return numbers


def _share(series: pd.Series) -> pd.Series:
    """이용 비중. 원본이 담은 %를 그대로 넘긴다.

    뒤에 붙은 `%`, 천 단위 쉼표, 앞에 붙은 `+`를 떼고 읽는다. 100을 곱하거나
    나누지 않고, 인원수에서 다시 만들지도 않는다(→ AGENTS.md §9).
    """
    name = SOURCE_NAMES.get(series.name, str(series.name))
    return to_optional_number_column(
        series, LABEL, name, "비중은 %로 계산된 숫자여야 합니다."
    )


def _check_keys(usage: pd.DataFrame) -> None:
    """한 지점의 한 달이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면에는 그중 하나가 조용히
    골라져 나타난다. 펴기 전에 확인해야 채널 수만큼 부풀지 않는다.
    """
    keys = pd.MultiIndex.from_arrays(
        [usage["base_month"], plain_text(usage["branch_id"])]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 기준월·지점이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id}. "
            "한 지점은 한 달에 한 행이어야 합니다."
        )


__all__ = [
    "CHANNEL_COLUMNS",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "LABEL",
    "SOURCE_NAMES",
    "VALUE_COLUMNS",
    "build",
    "build_channel",
]
