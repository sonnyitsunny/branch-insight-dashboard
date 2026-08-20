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

# 시가총액을 읽을 수 없는 행에 주는 최소 면적. 0이면 그 칸이 사라져
# 보이지 않는다.
AREA_FLOOR = 0.3

# 면적 압축 지수. 시가총액을 이 지수로 눌러 칸 크기로 쓴다.
#
# 1이면 시총에 그대로 비례한다. 낮출수록 큰 종목의 칸이 작아져 작은
# 종목이 보이지만, 큰 종목과 작은 종목의 차이도 그만큼 지워진다.
# 화면이 한두 종목에 덮이면 낮추고, 크기 차이가 안 읽히면 올린다.
#
# **0에 가깝게 낮추지 않는다.** 0에 가까울수록 로그와 비슷해지는데,
# 로그는 종목 수가 많은 업종이 시총이 큰 업종을 이기게 만든다
# (→ area_values).
AREA_EXPONENT = 0.5


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


# 시가총액 컬럼의 기본 이름. 해외주식은 달러라 이름이 다르므로 부르는 쪽이
# 넘긴다(→ dashboard/data.py 의 OVERSEAS_STOCK_CAP_COLUMNS).
CAP_COLUMN = "market_cap"


def area_floor(
    stock: pd.DataFrame, cap_column: str = CAP_COLUMN
) -> float:
    """면적의 기준이 되는 가장 작은 시가총액.

    지점마다 다시 구하지 않고 전체 종목에서 한 번 구한다. 시가총액은
    시장이 정하는 값이라 지점이 달라도 같으므로, 기준을 고정해야 같은
    종목의 칸 크기가 지점을 바꿔도 그대로 남는다.

    기준은 배율일 뿐이라 칸끼리의 비율은 바꾸지 못한다(→ area_values).
    숫자를 읽기 좋은 크기로 맞추고, 화면을 바꿔도 같은 종목이 같은 값을
    받게 하는 역할이다.
    """
    if stock.empty or cap_column not in stock.columns:
        return 1.0
    values = pd.to_numeric(stock[cap_column], errors="coerce").dropna()
    values = values[values > 0]
    if values.empty:
        return 1.0
    return float(values.min())


def area_values(market_cap: pd.Series, floor: float) -> pd.Series:
    """시가총액을 트리맵 면적으로 바꾼다.

    상위 종목과 하위 종목의 시가총액은 자릿수가 세 자리 넘게 벌어진다.
    그대로 면적에 넣으면 1위 종목 하나가 그림을 거의 다 덮고 나머지는
    실선처럼 눌린다. 기준으로 나눈 뒤 `AREA_EXPONENT`로 눌러 그 차이를
    줄인다.

    **로그를 쓰지 않는다.** 트리맵은 묶음 칸의 크기가 그 안 칸들의 합인
    그림이다. 종목마다 로그를 씌워 더하면 그 합이 시가총액 합과 다른
    순서를 갖는다. 로그가 자릿수 차이를 너무 세게 눌러, 시총이 작은
    종목을 여럿 담은 업종이 큰 종목 몇 개를 담은 업종을 이긴다. 실제로
    반도체 3종목(605조)이 상사·자본재 10종목(30조)보다 작게 그려졌다.

    거듭제곱도 합을 그대로 지키지는 못하므로 종목 수가 아주 많이 벌어지면
    같은 일이 생긴다. 지수가 1에 가까울수록 안전하다.

    **면적은 시가총액에 비례하지 않는다.** 칸 크기로 시총을 가늠하면
    안 되고 실제 값은 hover로 읽는다.
    """
    values = pd.to_numeric(market_cap, errors="coerce")
    ratio = values.where(values > 0) / max(floor, 1.0)
    sizes = np.power(ratio, AREA_EXPONENT)
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


def treemap_rows(
    rows: pd.DataFrame, floor: float, cap_column: str = CAP_COLUMN
) -> pd.DataFrame:
    """트리맵이 바로 쓸 수 있는 형태로 만든다.

    되돌려주는 컬럼은 원본 값에 화면용 세 개를 더한 것이다 — 묶음
    이름(`sector_label`), 면적(`area`), 색(`color`).

    면적으로 쓸 시가총액 컬럼은 `cap_column`이 정한다. 해외주식은 그 값이
    달러라 컬럼 이름이 다르다(→ CAP_COLUMN). 어느 쪽이든 칸 크기는 그 안에서
    서로를 견준 값이라, 두 그림의 칸 크기를 서로 견주지는 않는다.

    값이 없는 행은 뺀다. 시가총액이 없으면 칸을 그릴 수 없고, 순매수금액이
    없으면 색을 정할 수 없다. 0으로 채우면 '없음'이 '0으로 측정됨'이
    된다(→ AGENTS.md §9).
    """
    if rows.empty:
        return rows
    ready = rows.dropna(subset=[cap_column, "net_buy_amount"]).copy()
    if ready.empty:
        return ready
    ready["sector_label"] = ready["sector"].map(sector_label)
    ready["area"] = area_values(ready[cap_column], floor)
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
