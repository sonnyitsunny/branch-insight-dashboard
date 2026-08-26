"""디지털 채널 탭의 계산.

데이터를 직접 읽지 않는다. `DashboardData`가 들고 있는 표준 프레임을 받아
화면이 쓸 모양으로만 바꾼다(→ AGENTS.md §9).

원본이 이미 계산해 담은 값을 그대로 옮긴다. 비중을 인원수에서 다시 만들지
않는다(→ dashboard/sources/digital1.py).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import TOTAL_LABEL

# 고른 대상이 '전체'인지 지점인지 알리는 컬럼. 그림에서 그 하나만 달리
# 그릴 때 쓴다(→ figures).
TOTAL_FLAG = "is_total"


def scope_names(data) -> list[str]:
    """맨 위 드롭다운이 고를 수 있는 값. '전체'가 맨 앞이다.

    지점 이름은 데이터에서 읽는다. 지점이 늘어도 코드를 고치지 않는다
    (→ AGENTS.md §10.1).
    """
    return [TOTAL_LABEL, *data.branch_names]


def scope_rows(frame: pd.DataFrame, total: pd.DataFrame, scope: str):
    """고른 대상의 행만 남긴다.

    '전체'는 지점 합계가 아니라 원본이 따로 담은 행이다. 지점에서 되계산하지
    않는다(→ AGENTS.md §9).
    """
    if frame is None or frame.empty:
        return frame
    if scope == TOTAL_LABEL:
        return total if total is not None else frame.iloc[0:0]
    return frame[frame["branch_name"] == scope]


def latest_month(frame: pd.DataFrame) -> str:
    """그 프레임이 담은 가장 최근 달. 비어 있으면 빈 문자열."""
    if frame is None or frame.empty:
        return ""
    return str(max(frame["base_month"]))


def channel_trend(data, scope: str, channel: str) -> pd.DataFrame:
    """고른 대상·채널의 월별 이용 고객 수와 이용 비중.

    되돌려주는 컬럼은 base_month·user_count·user_share 셋이며 월 순이다.
    """
    rows = scope_rows(
        data.digital_channel, data.digital_channel_total, scope
    )
    if rows is None or rows.empty:
        return pd.DataFrame()
    rows = rows[rows["channel"] == channel]
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.loc[:, ["base_month", "user_count", "user_share"]]
        .sort_values("base_month")
        .reset_index(drop=True)
    )


def activation_scatter(data, channel: str, month: str = "") -> pd.DataFrame:
    """지점마다 그 채널의 이용 비중과 거래활성화율을 짝지어 놓는다.

    가로가 이용 비중, 세로가 거래활성화율(거래고객비중)이다. 두 값이 서로
    다른 프레임에 있어 기준월·지점으로 맞춘다 — 이용 비중은 채널 축이 있는
    프레임에, 거래고객비중은 채널로 나뉘지 않아 월별 프레임에 있다
    (→ data.MONTHLY_DIGITAL_COLUMNS).

    한 달만 그린다. 두 축이 모두 그 달의 값이라야 한 점이 한 지점의 그 달을
    가리킨다. 비우면 이용 비중 프레임의 가장 최근 달을 쓴다.

    '전체' 행도 함께 담고 `TOTAL_FLAG`로 표시한다. 그림이 그 하나만 달리
    그린다.
    """
    shares = data.digital_channel
    if shares is None or shares.empty:
        return pd.DataFrame()
    month = month or latest_month(shares)

    parts = []
    for frame, monthly, is_total in (
        (shares, data.monthly, False),
        (data.digital_channel_total, data.monthly_total, True),
    ):
        rows = _month_channel(frame, month, channel)
        if rows.empty:
            continue
        joined = _with_activation(rows, monthly, month)
        joined[TOTAL_FLAG] = is_total
        parts.append(joined)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _month_channel(
    frame: pd.DataFrame, month: str, channel: str
) -> pd.DataFrame:
    """그 달·그 채널의 행만 남긴다."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    picked = frame[
        (frame["base_month"] == month) & (frame["channel"] == channel)
    ]
    return picked.loc[
        :, ["branch_id", "branch_name", "user_share"]
    ].reset_index(drop=True)


def _with_activation(
    rows: pd.DataFrame, monthly: pd.DataFrame, month: str
) -> pd.DataFrame:
    """거래활성화율을 지점 코드로 맞춰 붙인다.

    원본에 그 값이 없으면 비운 채로 둔다. 0으로 채우면 '거래한 고객이
    없음'이 아니라 '0%로 측정됨'이 된다(→ AGENTS.md §9).
    """
    joined = rows.copy()
    joined["activation"] = pd.NA
    if monthly is None or monthly.empty:
        return joined
    same = monthly[monthly["base_month"] == month]
    if same.empty:
        return joined
    values = same.set_index("branch_id")["digital_trade_customer_share"]
    joined["activation"] = (
        joined["branch_id"].map(values).astype("Float64")
    )
    return joined


def channel_profile(
    data, scope: str, items: tuple, channels: tuple, month: str = ""
) -> pd.DataFrame:
    """고른 대상의 채널별 고객 특성을 항목이 행, 채널이 열인 표로 만든다.

    `items`는 (표준 컬럼, 화면 이름, 표기 함수)를 담은 목록이다. 항목마다
    단위가 달라(세·원·%) 컬럼 하나의 표기 함수로는 적을 수 없으므로, 행이
    자기 문구를 함께 들고 간다(→ grid.MONEY_FORMAT).

    한 달만 담는다. 비우면 프레임의 가장 최근 달을 쓴다.
    """
    frame = data.digital_profile
    if frame is None or frame.empty:
        return pd.DataFrame()
    month = month or latest_month(frame)
    rows = scope_rows(frame, data.digital_profile_total, scope)
    if rows is None or rows.empty:
        return pd.DataFrame()
    rows = rows[rows["base_month"] == month]
    if rows.empty:
        return pd.DataFrame()

    values = rows.set_index("channel")
    built = []
    for field, label, to_text in items:
        record: dict = {"item": label}
        for channel in channels:
            value = _cell_value(values, channel, field)
            record[_column_key(channel)] = value
            # 화면에 적을 문구를 행이 들고 간다. 항목마다 단위가 다르다.
            record[f"{_column_key(channel)}__text"] = to_text(value)
        built.append(record)
    return pd.DataFrame(built)


def _column_key(channel: str) -> str:
    """채널 이름에서 만드는 표 컬럼 이름. 화면 ID 규칙과 같다."""
    return channel.lower()


def _cell_value(values: pd.DataFrame, channel: str, field: str):
    """그 채널·항목의 값. 없으면 None으로 두어 화면에 `-`가 나오게 한다."""
    if channel not in values.index:
        return None
    value = values.loc[channel, field]
    if isinstance(value, pd.Series):
        value = value.iloc[0]
    return None if pd.isna(value) else float(value)


def usage_days(data, scope: str, channels: tuple) -> pd.DataFrame:
    """고른 대상의 이용일수 구간별 채널 이용 비중.

    되돌려주는 컬럼은 usage_day_group·channel·day_group_share 셋이다.
    구간 차례는 데이터 계층이 정한 순서를 그대로 쓴다
    (→ data.DIGITAL_USAGE_DAY_GROUPS).
    """
    rows = scope_rows(
        data.digital_usage_days, data.digital_usage_days_total, scope
    )
    if rows is None or rows.empty:
        return pd.DataFrame()
    rows = rows[rows["channel"].isin(channels)]
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.loc[
            :, ["usage_day_group", "channel", "day_group_share"]
        ]
        .sort_values(["channel", "usage_day_group"])
        .reset_index(drop=True)
    )


def menu_rank_table(
    data, scope: str, fields: tuple, month: str = ""
) -> pd.DataFrame:
    """고른 대상의 메뉴 순위표를 순위가 행, 분류가 열인 표로 만든다.

    `fields`는 (메뉴 분류, 표 컬럼 이름) 짝을 담은 목록이다. 분류 이름이
    한글이라 표 컬럼 이름은 부르는 쪽이 정해서 넘긴다(→ tabs.digital).

    셀에는 그 분류·그 순위의 **메뉴 이름**만 담는다. 조회 건수는 옆 산점도가
    맡는다.

    분류마다 순위가 몇 위까지인지 다를 수 있다. 없는 자리는 비운 채로 두어
    화면에 `-`로 나타나게 한다(→ AGENTS.md §9).

    한 달만 담는다. 비우면 프레임의 가장 최근 달을 쓴다.
    """
    rows = _menu_rows(data, scope, month)
    if rows.empty:
        return pd.DataFrame()

    built = pd.DataFrame(
        {"menu_rank": sorted(rows["menu_rank"].unique().tolist())}
    )
    for category, field in fields:
        names = rows[rows["menu_category"] == category]
        built[field] = built["menu_rank"].map(
            names.set_index("menu_rank")["menu_name"]
        )
    return built


def menu_scatter(
    data, scope: str, category: str, month: str = ""
) -> pd.DataFrame:
    """고른 대상·분류의 메뉴마다 조회 건수와 거래 전환 비율을 짝지어 놓는다.

    가로가 조회 건수, 세로가 거래 전환 비율이다. 두 값이 같은 행에 있어
    다른 프레임과 맞출 것이 없다(→ data.DIGITAL_MENU_RANK_COLUMNS).

    되돌려주는 컬럼은 menu_rank·menu_name·view_count·
    trade_conversion_share 넷이며 순위 순이다.

    한 달만 그린다. 두 축이 모두 그 달의 값이라야 한 점이 한 메뉴의 그 달을
    가리킨다.
    """
    rows = _menu_rows(data, scope, month)
    if rows.empty:
        return pd.DataFrame()
    rows = rows[rows["menu_category"] == category]
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.loc[
            :,
            [
                "menu_rank",
                "menu_name",
                "view_count",
                "trade_conversion_share",
            ],
        ]
        .sort_values("menu_rank")
        .reset_index(drop=True)
    )


def _menu_rows(data, scope: str, month: str = "") -> pd.DataFrame:
    """고른 대상·그 달의 메뉴 순위 행. 없으면 빈 프레임."""
    frame = data.digital_menu_rank
    if frame is None or frame.empty:
        return pd.DataFrame()
    month = month or latest_month(frame)
    rows = scope_rows(frame, data.digital_menu_rank_total, scope)
    if rows is None or rows.empty:
        return pd.DataFrame()
    rows = rows[rows["base_month"] == month]
    return pd.DataFrame() if rows.empty else rows


__all__ = [
    "TOTAL_FLAG",
    "activation_scatter",
    "channel_profile",
    "channel_trend",
    "latest_month",
    "menu_rank_table",
    "menu_scatter",
    "scope_names",
    "scope_rows",
    "usage_days",
]
