"""상품 탭의 계산.

데이터를 직접 읽지 않는다. 데이터 계층이 넘긴 프레임을 받아 화면이 쓸
형태로만 고른다(→ AGENTS.md §9).

트리맵이 쓰는 두 변환도 여기 있다. 시가총액은 면적, 순매수금액은 색이
되는데 둘 다 편차가 커서 그대로 쓰면 그림이 읽히지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 업종이 비어 있는 종목을 묶을 이름. 트리맵은 모든 칸이 어느 묶음엔가
# 속해야 그려지므로 빈 값을 그대로 둘 수 없다. 데이터는 빈 값 그대로
# 두고 화면에서만 이 이름으로 부른다(→ AGENTS.md §9).
SECTOR_UNKNOWN = "미분류"

# 면적 로그 변환에서 가장 작은 종목에 남기는 몫. 0이면 그 칸이 사라져
# 보이지 않는다.
AREA_FLOOR = 0.3


def scope_names(
    stock: pd.DataFrame, stock_total: pd.DataFrame, total_label: str
) -> list[str]:
    """지점 선택 목록. 원본에 '전체' 행이 있으면 맨 앞에 둔다.

    원본이 없거나 걸러 낸 결과가 비면 컬럼조차 없는 빈 프레임이 올 수
    있다. 그때는 고를 값이 없다는 뜻이므로 빈 목록을 돌려준다
    (→ data._apply_filters).
    """
    names = (
        []
        if stock.empty or "branch_name" not in stock.columns
        else sorted(stock["branch_name"].unique().tolist())
    )
    if stock_total.empty:
        return names
    return [total_label, *names]


def branch_rows(
    stock: pd.DataFrame,
    stock_total: pd.DataFrame,
    branch_name: str,
    total_label: str,
) -> pd.DataFrame:
    """고른 지점의 행.

    '전체'는 지점 행을 더해 만들지 않는다. 원본이 따로 뽑아 둔 '전체' 행을
    그대로 쓴다. 상위 종목은 더할 수 있는 값이 아니라 따로 매긴 목록이다.
    """
    frame = stock_total if branch_name == total_label else stock
    if frame.empty or "branch_name" not in frame.columns:
        return frame
    if branch_name == total_label:
        return frame.reset_index(drop=True)
    return frame[frame["branch_name"] == branch_name].reset_index(drop=True)


def sector_label(value: object) -> str:
    """빈 업종을 화면에서 부를 이름으로 바꾼다."""
    text = "" if value is None else str(value).strip()
    return text or SECTOR_UNKNOWN


def area_floor(stock: pd.DataFrame) -> float:
    """면적 로그 변환의 기준이 되는 가장 작은 시가총액.

    지점마다 다시 구하지 않고 전체 종목에서 한 번 구한다. 시가총액은
    시장이 정하는 값이라 지점이 달라도 같으므로, 기준을 고정해야 같은
    종목의 칸 크기가 지점을 바꿔도 그대로 남는다.
    """
    if stock.empty or "market_cap" not in stock.columns:
        return 1.0
    values = pd.to_numeric(stock["market_cap"], errors="coerce").dropna()
    values = values[values > 0]
    if values.empty:
        return 1.0
    return float(values.min())


def area_values(market_cap: pd.Series, floor: float) -> pd.Series:
    """시가총액을 트리맵 면적으로 바꾼다.

    상위 종목과 하위 종목의 시가총액은 자릿수가 세 자리 넘게 벌어진다.
    그대로 면적에 넣으면 1위 종목 하나가 그림을 거의 다 덮고 나머지는
    실선처럼 눌린다. 로그를 씌워 자릿수 차이를 면적 차이로 바꾼다.

    `log10(시총) - log10(기준)`에 최소 몫(`AREA_FLOOR`)을 더한다. 1을 더한
    로그만 쓰면 값이 6.7 대 3.5로 모여 칸 크기가 거의 같아지고, 무엇이 큰
    종목인지 그림에서 읽히지 않는다. 기준을 빼면 가장 작은 종목이 가장
    작은 칸이 되어 크기 차이가 살아난다.

    **면적은 시가총액에 비례하지 않는다.** 칸 크기로 시총을 가늠하면
    안 되고 실제 값은 칸 안 글씨와 hover로 읽는다.
    """
    values = pd.to_numeric(market_cap, errors="coerce")
    base = np.log10(max(floor, 1.0))
    sizes = np.log10(values.where(values > 0)) - base + AREA_FLOOR
    return sizes.fillna(AREA_FLOOR).clip(lower=AREA_FLOOR)


def signed_log(amount: pd.Series) -> pd.Series:
    """순매수금액을 부호를 지킨 로그로 바꾼다.

    순매수금액도 편차가 커서, 큰 종목 하나가 색 눈금의 끝을 차지하면
    나머지가 모두 가운데 색으로 뭉개진다. 로그를 씌워 자릿수 차이를 색
    차이로 바꾼다.

    금액은 음수(순매도)가 될 수 있어 그냥 로그를 씌울 수 없다. 절댓값에
    로그를 씌우고 부호를 되붙인다. `log1p`를 쓰므로 0은 그대로 0이 되어
    발산형 색 눈금의 가운데(중립색)에 정확히 놓인다.
    """
    values = pd.to_numeric(amount, errors="coerce")
    return np.sign(values) * np.log1p(values.abs())


def treemap_rows(rows: pd.DataFrame, floor: float) -> pd.DataFrame:
    """트리맵이 바로 쓸 수 있는 형태로 만든다.

    되돌려주는 컬럼은 원본 값(stock_name·sector·market_cap·
    trade_customer_count·trade_value·net_buy_amount)에 화면용 세 개를
    더한 것이다 — 묶음 이름(`sector_label`), 면적(`area`), 색(`color`).

    값이 없는 행은 뺀다. 시가총액이 없으면 칸을 그릴 수 없고, 순매수금액이
    없으면 색을 정할 수 없다. 0으로 채우면 '없음'이 '0으로 측정됨'이
    된다(→ AGENTS.md §9).
    """
    if rows.empty:
        return rows
    ready = rows.dropna(subset=["market_cap", "net_buy_amount"]).copy()
    if ready.empty:
        return ready
    ready["sector_label"] = ready["sector"].map(sector_label)
    ready["area"] = area_values(ready["market_cap"], floor)
    ready["color"] = signed_log(ready["net_buy_amount"])
    return ready.reset_index(drop=True)


def color_limit(colors: pd.Series) -> float:
    """색 눈금의 양끝. 0을 가운데 두려면 두 끝이 같은 거리여야 한다.

    한쪽만 크면 그쪽으로 눈금이 치우쳐, 순매수 0인 종목이 중립색이 아니라
    한쪽 색으로 그려진다.
    """
    values = pd.to_numeric(colors, errors="coerce").abs().dropna()
    if values.empty:
        return 1.0
    return max(float(values.max()), 1.0)
