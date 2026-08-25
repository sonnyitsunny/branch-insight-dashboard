"""데이터 계약과 정합성 검증.

표본 파일은 `tests/data/`에 있고 실제 원본과 같은 형식이다(→ fixture_data).
"""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard import data as data_module
from dashboard import sources
from dashboard.data import (
    AGE_GROUPS,
    ALL_AGE_GROUPS,
    ASSET_GROUPS,
    DIGITAL_CHANNELS,
    DIGITAL_CUSTOMER_COLUMN,
    DIGITAL_PROFILE_SHARE_COLUMNS,
    DIGITAL_TRADE_SHARE_COLUMN,
    DIGITAL_USAGE_DAY_GROUPS,
    FRAME_NAMES,
    INVESTMENT_TYPES,
    MONTHLY_DIGITAL_COLUMNS,
    RETURN_GROUPS,
    RETURN_PERIODS,
    SHARE_TOLERANCE_PP,
    TOTAL_LABEL,
    YOY_MONTHS,
    load_dashboard_data,
    reference_month,
    shift_month,
    validate_dashboard_data,
)
from fixture_data import (
    ASSET_RETURN_ROWS,
    BRANCH_COUNT,
    BRANCH_RETURN_MONTHS,
    DIGITAL_CHANNEL_COUNT,
    DIGITAL_USAGE_DAY_ROWS,
    CASH_FLOW_CHANNEL_COUNT,
    CURRENT_MONTH,
    END_MONTH,
    ETF_NEW_ENTRY_RANK,
    FUND_SHORT_RANK_COUNT,
    FUND_TIED_RANK,
    MONTH_COUNT,
    PENSION_BLOCK_COUNT,
    PENSION_SHORT_BLOCK,
    PENSION_SHORT_RANK_COUNT,
    OVERSEAS_NEW_ENTRY_RANK,
    OVERSEAS_STOCK_CAP_COUNT,
    PENSION_TRADE_PRODUCT_COUNT,
    PENSION_TYPE_COUNT,
    PREVIOUS_MONTH,
    RETURN_GROUP_ROWS,
    REVENUE_TYPE_COUNT,
    SEGMENT_RETURN_FRAMES,
    START_MONTH,
    STOCK_CAP_COUNT,
    STOCK_RANK_COUNT,
    TRADE_PRODUCT_COUNT,
    YOY_BASE_MONTH,
    fund_rank_counts,
    month_range,
    pension_rank_counts,
)


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _frames(data: data_module.DashboardData) -> dict[str, pd.DataFrame]:
    """pkl에 저장하는 형태(dict)로 바꾼다."""
    return {name: getattr(data, name) for name in FRAME_NAMES}


def _normalized(data: data_module.DashboardData, **replaced: pd.DataFrame):
    """일부 프레임만 바꿔 정규화한다. 값 검사 오류를 직접 확인할 때 쓴다."""
    return data_module._normalize(data_module.DashboardData(**{**_frames(data), **replaced}))


def test_fixture_transaction_frames_cover_every_branch_and_month(dataset):
    """거래 표본 세 개가 표준 프레임까지 들어온다.

    행 수는 지점 × 월 × 분류다. '전체' 지점 행은 여기서 빠져 있다.
    """
    branch_months = BRANCH_COUNT * MONTH_COUNT
    assert len(dataset.transaction) == branch_months * TRADE_PRODUCT_COUNT
    assert len(dataset.pension_transaction) == (
        branch_months * PENSION_TYPE_COUNT * PENSION_TRADE_PRODUCT_COUNT
    )
    assert len(dataset.cash_flow) == (
        branch_months * CASH_FLOW_CHANNEL_COUNT
    )
    for frame in (
        dataset.transaction,
        dataset.pension_transaction,
        dataset.cash_flow,
    ):
        assert TOTAL_LABEL not in set(frame["branch_name"])
        assert sorted(frame["base_month"].unique()) == month_range()


def test_fixture_revenue_frame_covers_every_branch_and_month(dataset):
    """수익 표본이 표준 프레임까지 들어온다.

    행 수는 지점 × 월 × 수익 분류다. '전체' 지점 행은 여기서 빠져 있다.
    """
    assert len(dataset.revenue) == (
        BRANCH_COUNT * MONTH_COUNT * REVENUE_TYPE_COUNT
    )
    assert TOTAL_LABEL not in set(dataset.revenue["branch_name"])
    assert sorted(dataset.revenue["base_month"].unique()) == month_range()


def test_fixture_domestic_stock_frame_covers_every_branch(dataset):
    """상품 국내주식 표본이 표준 프레임까지 들어온다.

    행 수는 지점 × 순위다. 원본이 마지막 한 달만 담고 있어 다른 프레임과
    달리 기간이 한 달뿐이며, 그래도 검증을 통과해야 한다.
    """
    assert len(dataset.domestic_stock_rank) == BRANCH_COUNT * STOCK_RANK_COUNT
    assert TOTAL_LABEL not in set(dataset.domestic_stock_rank["branch_name"])
    assert sorted(dataset.domestic_stock_rank["base_month"].unique()) == [
        END_MONTH
    ]

    total = dataset.domestic_stock_rank_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == STOCK_RANK_COUNT


def test_fixture_domestic_stock_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    비어 있는 업종, 음수 순매수금액, 부호가 있는 순위변동은 모두 실제
    원본에 있는 형태다. 어느 하나라도 조용히 채워지면 화면 숫자가 원본과
    달라진다.
    """
    frame = dataset.domestic_stock_rank
    assert (frame["sector"] == "").any()
    assert (frame["net_buy_amount"] < 0).any()
    assert (frame["rank_change"] < 0).any()
    assert (frame["rank_change"] > 0).any()
    assert (frame["rank_change"] == 0).any()
    # 순위는 지점마다 1..N이 한 번씩이다.
    counts = frame.groupby("branch_id")["stock_rank"].nunique()
    assert set(counts) == {STOCK_RANK_COUNT}


def test_fixture_domestic_stock_cap_covers_every_branch(dataset):
    """시가총액 상위 종목 표본이 표준 프레임까지 들어온다.

    지점마다 거래한 종목만 있어 행 수가 지점 × 종목보다 적다. 그래도 모든
    지점이 한 행 이상은 갖고 있어야 이 표본으로 화면을 만들 수 있다.
    """
    frame = dataset.domestic_stock_cap
    assert frame["branch_id"].nunique() == BRANCH_COUNT
    assert len(frame) < BRANCH_COUNT * STOCK_CAP_COUNT
    assert frame["stock_name"].nunique() == STOCK_CAP_COUNT
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.domestic_stock_cap_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == STOCK_CAP_COUNT


def test_fixture_domestic_stock_cap_keeps_stock_facts_stable(dataset):
    """같은 종목의 시가총액·업종은 지점이 달라도 하나뿐이다.

    트리맵이 시가총액을 면적으로, 업종을 묶음으로 쓴다. 지점을 바꿀 때마다
    값이 흔들리면 그림 자체가 달라진다.
    """
    frame = dataset.domestic_stock_cap
    caps = frame.groupby("stock_name")["market_cap"].nunique()
    assert set(caps) == {1}
    filled = frame[frame["sector"] != ""]
    sectors = filled.groupby("stock_name")["sector"].nunique()
    assert set(sectors) == {1}
    # 업종이 비어 있는 종목과 음수 순매수도 그대로 남는다.
    assert (frame["sector"] == "").any()
    assert (frame["net_buy_amount"] < 0).any()


def test_fixture_overseas_stock_frame_covers_every_branch(dataset):
    """상품 해외주식 표본이 표준 프레임까지 들어온다.

    국내주식 순위표와 같이 행 수는 지점 × 순위이고 마지막 한 달만 담는다.
    """
    frame = dataset.overseas_stock_rank
    assert len(frame) == BRANCH_COUNT * STOCK_RANK_COUNT
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.overseas_stock_rank_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == STOCK_RANK_COUNT


def test_fixture_overseas_stock_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    비어 있는 업종, 음수 순매수금액, 부호가 있는 순위변동은 국내주식과 같고
    거래소가 하나 더 있다. 앞 달에 없던 종목의 순위변동은 0으로 채우지 않고
    비운 채로 남아야 한다. 0은 '순위가 그대로'라는 뜻이라 뜻이 달라진다.
    """
    frame = dataset.overseas_stock_rank
    assert (frame["sector"] == "").any()
    assert (frame["exchange"] != "").all()
    assert (frame["net_buy_amount"] < 0).any()
    assert (frame["net_buy_amount"] > 0).any()
    assert (frame["rank_change"] < 0).any()
    assert (frame["rank_change"] > 0).any()
    assert (frame["rank_change"] == 0).any()
    new_entry = frame[frame["stock_rank"] == OVERSEAS_NEW_ENTRY_RANK]
    assert new_entry["rank_change"].isna().all()
    # 순위는 지점마다 1..N이 한 번씩이다.
    counts = frame.groupby("branch_id")["stock_rank"].nunique()
    assert set(counts) == {STOCK_RANK_COUNT}


def test_fixture_overseas_stock_has_no_market_cap(dataset):
    """해외주식 원본에는 시가총액이 없다.

    국내주식 트리맵은 시가총액을 칸 크기로 쓴다. 그 컬럼이 이 프레임에
    있다고 착각하고 화면을 만들면 빈 그림이 나온다.
    """
    assert "market_cap" not in dataset.overseas_stock_rank.columns


def test_fixture_overseas_stock_cap_covers_every_branch(dataset):
    """해외주식 시가총액 상위 종목 표본이 표준 프레임까지 들어온다.

    지점마다 거래한 종목만 있어 행 수가 지점 × 종목보다 적다. 그래도 모든
    지점이 한 행 이상은 갖고 있어야 이 표본으로 화면을 만들 수 있다.
    """
    frame = dataset.overseas_stock_cap
    assert frame["branch_id"].nunique() == BRANCH_COUNT
    assert len(frame) < BRANCH_COUNT * OVERSEAS_STOCK_CAP_COUNT
    assert frame["stock_name"].nunique() == OVERSEAS_STOCK_CAP_COUNT
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.overseas_stock_cap_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == OVERSEAS_STOCK_CAP_COUNT


def test_fixture_overseas_stock_cap_keeps_stock_facts_stable(dataset):
    """같은 종목의 시가총액·업종·거래소는 지점이 달라도 하나뿐이다.

    트리맵이 시가총액을 면적으로, 업종을 묶음으로 쓴다. 지점을 바꿀 때마다
    값이 흔들리면 그림 자체가 달라진다.

    순위는 여기서 보지 않는다. 무엇을 기준으로 매긴 순위인지 확인되지 않아
    지점마다 같아야 한다고 말할 수 없다.
    """
    frame = dataset.overseas_stock_cap
    for column in ("market_cap_usd", "exchange"):
        counts = frame.groupby("stock_name")[column].nunique()
        assert set(counts) == {1}
    filled = frame[frame["sector"] != ""]
    assert set(filled.groupby("stock_name")["sector"].nunique()) == {1}
    # 업종이 비어 있는 종목과 음수 순매수도 그대로 남는다.
    assert (frame["sector"] == "").any()
    assert (frame["net_buy_amount"] < 0).any()


def test_fixture_overseas_market_cap_keeps_its_own_column(dataset):
    """달러 시가총액은 원화 컬럼과 이름을 나눠 담는다.

    `market_cap`(억원)과 같은 이름을 쓰면 원화 표기 함수에 그대로 넘어가
    화면에 억원으로 적힌다.
    """
    frame = dataset.overseas_stock_cap
    assert "market_cap" not in frame.columns
    assert (frame["market_cap_usd"] > 0).all()


def test_fixture_etf_frame_covers_every_branch(dataset):
    """상품 ETF 표본이 표준 프레임까지 들어온다.

    주식 순위표와 같이 행 수는 지점 × 순위이고 마지막 한 달만 담는다.
    """
    frame = dataset.etf_rank
    assert len(frame) == BRANCH_COUNT * STOCK_RANK_COUNT
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.etf_rank_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == STOCK_RANK_COUNT


def test_fixture_etf_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    음수 순매수금액과 부호가 있는 순위변동은 주식 순위표와 같다. 앞 달에
    없던 종목의 순위변동은 0으로 채우지 않고 비운 채로 남아야 한다.
    """
    frame = dataset.etf_rank
    assert (frame["net_buy_amount"] < 0).any()
    assert (frame["net_buy_amount"] > 0).any()
    assert (frame["rank_change"] < 0).any()
    assert (frame["rank_change"] > 0).any()
    assert (frame["rank_change"] == 0).any()
    new_entry = frame[frame["stock_rank"] == ETF_NEW_ENTRY_RANK]
    assert new_entry["rank_change"].isna().all()
    # 순위는 지점마다 1..N이 한 번씩이다.
    counts = frame.groupby("branch_id")["stock_rank"].nunique()
    assert set(counts) == {STOCK_RANK_COUNT}


def test_fixture_etf_has_no_sector(dataset):
    """ETF 원본에는 업종이 없다.

    주식 트리맵은 업종으로 종목을 묶는다. 그 컬럼이 이 프레임에 있다고
    보고 화면을 만들면 빈 그림이 나온다.
    """
    assert "sector" not in dataset.etf_rank.columns
    # 시가총액은 억원이라 국내주식과 같은 이름을 쓴다.
    assert (dataset.etf_rank["market_cap"] > 0).all()


def test_fixture_fund_frame_covers_every_branch(dataset):
    """상품 펀드 표본이 표준 프레임까지 들어온다.

    ETF 순위표와 달리 지점마다 순위 수가 다르므로 행 수가 지점 × 순위가
    아니다. 지점은 하나도 빠지지 않는다.
    """
    frame = dataset.fund_rank
    assert len(frame) == sum(fund_rank_counts())
    assert len(set(frame["branch_name"])) == BRANCH_COUNT
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.fund_rank_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == STOCK_RANK_COUNT


def test_fixture_fund_branches_may_stop_short_of_twenty(dataset):
    """20위까지 차지 않는 지점이 있어도 그대로 들어온다.

    파는 종목이 적은 지점이다. 빈 순위를 채우거나 그 지점을 빼면 화면에
    없는 종목이 생기거나 지점 하나가 사라진다.
    """
    frame = dataset.fund_rank
    counts = frame.groupby("branch_id")["stock_rank"].max()
    assert set(counts) == {FUND_SHORT_RANK_COUNT, STOCK_RANK_COUNT}
    rows = frame.groupby("branch_id").size()
    assert set(rows) == {FUND_SHORT_RANK_COUNT, STOCK_RANK_COUNT}
    # 순위는 1부터 마지막까지 이어진다. 동순위가 있는 자리만 한 등수를
    # 두 번 쓰고 그다음을 건너뛴다(→ FUND_TIED_RANK).
    for branch_id, last in counts.items():
        ranks = sorted(frame[frame["branch_id"] == branch_id]["stock_rank"])
        assert ranks[0] == 1
        assert ranks[-1] == int(last)
        assert set(ranks) <= set(range(1, int(last) + 1))


def test_fixture_fund_keeps_tied_ranks(dataset):
    """같은 등수가 나란히 오는 지점이 있어도 그대로 들어온다.

    값이 같은 종목이 여럿이면 원본이 같은 등수를 담는다. 잘못이 아니므로
    막지 않는다(→ dashboard/sources/fund1.py 의 check_ranks).
    """
    frame = dataset.fund_rank
    tied = frame[
        frame.duplicated(subset=["branch_id", "stock_rank"], keep=False)
    ]
    assert len(tied)
    assert set(tied["stock_rank"]) == {FUND_TIED_RANK}
    # 등수가 같아도 종목은 다르다. 같은 종목이 두 줄이면 금액이 두 번
    # 세어지므로 그것은 여전히 막는다.
    keys = ["branch_id", "stock_name"]
    assert not frame.duplicated(subset=keys).any()


def test_fixture_fund_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    시가총액이 없고, 앞 달에 없던 종목의 순위변동은 비어 있다. 그 자리는
    지점마다 마지막 순위다.
    """
    frame = dataset.fund_rank
    assert "market_cap" not in frame.columns
    assert "sector" not in frame.columns
    assert (frame["net_buy_amount"] < 0).any()
    assert (frame["net_buy_amount"] > 0).any()
    assert (frame["rank_change"] < 0).any()
    assert (frame["rank_change"] > 0).any()
    assert (frame["rank_change"] == 0).any()
    last = frame.groupby("branch_id")["stock_rank"].transform("max")
    assert frame.loc[frame["stock_rank"] == last, "rank_change"].isna().all()
    assert frame.loc[frame["stock_rank"] < last, "rank_change"].notna().all()


def test_fixture_pension_frame_unfolds_every_product(dataset):
    """상품 연금 표본이 한 줄에 한 상품인 형태로 표준 프레임까지 들어온다.

    원본은 상품 여섯 개를 가로로 펼쳐 담고 있다. 그대로 두면 화면이 컬럼
    이름으로 상품을 갈라야 한다(→ dashboard/sources/pension1.py).
    """
    frame = dataset.pension_rank
    assert len(frame) == sum(pension_rank_counts())
    assert len(set(frame["branch_name"])) == BRANCH_COUNT
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    axes = frame.groupby(
        ["pension_type", "product_type"], observed=True
    ).size()
    assert len(axes) == PENSION_BLOCK_COUNT

    total = dataset.pension_rank_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == STOCK_RANK_COUNT * PENSION_BLOCK_COUNT


def test_fixture_pension_drops_rows_without_a_name(dataset):
    """종목명이 빈 칸이던 자리는 줄이 아예 없다.

    파는 종목이 적은 지점이라 그 상품의 순위가 끝까지 차지 않는다. 다른
    상품은 그대로 20위까지 있다.
    """
    frame = dataset.pension_rank
    keys = ["branch_id", "pension_type", "product_type"]
    last = frame.groupby(keys, observed=True)["stock_rank"].max()
    is_short = (
        last.index.get_level_values("pension_type")
        == PENSION_SHORT_BLOCK[0]
    ) & (
        last.index.get_level_values("product_type")
        == PENSION_SHORT_BLOCK[1]
    )
    assert set(last[is_short]) == {
        PENSION_SHORT_RANK_COUNT,
        STOCK_RANK_COUNT,
    }
    assert set(last[~is_short]) == {STOCK_RANK_COUNT}
    assert frame["stock_name"].str.strip().ne("").all()


def test_fixture_pension_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    시가총액과 업종이 없고, 순위변동은 상품마다 마지막 순위에서 비어 있다.
    """
    frame = dataset.pension_rank
    assert "market_cap" not in frame.columns
    assert "sector" not in frame.columns
    assert (frame["net_buy_amount"] < 0).any()
    assert (frame["net_buy_amount"] > 0).any()
    assert (frame["rank_change"] < 0).any()
    assert (frame["rank_change"] > 0).any()
    assert (frame["rank_change"] == 0).any()
    keys = ["branch_id", "pension_type", "product_type"]
    last = frame.groupby(keys, observed=True)[
        "stock_rank"
    ].transform("max")
    assert frame.loc[frame["stock_rank"] == last, "rank_change"].isna().all()
    assert frame.loc[frame["stock_rank"] < last, "rank_change"].notna().all()


def test_fixture_branch_return_covers_every_branch(dataset):
    """지점별 수익률 표본이 표준 프레임까지 들어온다.

    분류축이 없어 행 수가 곧 지점 수다. 원본이 마지막 한 달만 담고 있어
    기간이 한 달뿐이며, 그래도 검증을 통과해야 한다.
    """
    frame = dataset.branch_return
    assert len(frame) == BRANCH_COUNT
    assert len(set(frame["branch_name"])) == BRANCH_COUNT
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.branch_return_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == BRANCH_RETURN_MONTHS


def test_fixture_branch_return_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    수익률은 이미 %라 그대로 오고, 손실이 난 지점은 음수로 남는다. 어느
    하나라도 조용히 고쳐지면 화면 숫자가 원본과 달라진다.
    """
    frame = dataset.branch_return
    for column in ("return_1y", "return_3y"):
        assert frame[column].notna().all()
        assert (frame[column] < 0).any()
        assert (frame[column] > 0).any()
        # 0~1 비율이 아니라 %다. 비율이면 모든 값이 1 안에 들어온다.
        assert frame[column].abs().max() > 1.0


def test_fixture_return_group_covers_every_branch(dataset):
    """수익률 그룹별 비중 표본이 표준 프레임까지 들어온다.

    행 수는 지점 × 기간 × 구간이다. 기간 둘에 구간 열이라 지점마다 스무
    행이며, '전체' 지점 행은 여기서 빠져 있다.
    """
    frame = dataset.return_group
    assert len(frame) == BRANCH_COUNT * RETURN_GROUP_ROWS
    assert set(frame.groupby("branch_id").size()) == {RETURN_GROUP_ROWS}
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.return_group_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == RETURN_GROUP_ROWS


def test_fixture_return_group_keeps_both_axes_in_order(dataset):
    """기간과 수익률 구간이 각각 컬럼으로 남고 순서를 지킨다.

    구간은 낮은 쪽부터 높은 쪽 순이다. 가나다순으로 세우면 `+100%이상`이
    맨 앞으로 온다.
    """
    frame = dataset.return_group
    assert list(frame["return_period"].cat.categories) == list(
        RETURN_PERIODS
    )
    assert list(frame["return_group"].cat.categories) == list(
        RETURN_GROUPS
    )
    axes = frame.groupby(
        ["return_period", "return_group"], observed=True
    ).size()
    assert len(axes) == len(RETURN_PERIODS) * len(RETURN_GROUPS)


def test_fixture_return_group_numbers_add_up(dataset):
    """구간 인원수의 합이 지점 합계와 맞고 비중이 그 둘과 어긋나지 않는다.

    막대 높이는 비중으로, hover의 고객 수는 인원수로 그리므로 둘이
    어긋나면 화면 안에서 숫자가 서로 맞지 않게 된다.
    """
    frame = dataset.return_group
    keys = ["branch_id", "return_period"]
    grouped = frame.groupby(keys, observed=True)
    assert (
        grouped["customer_count"].sum()
        == grouped["branch_customer_count"].first()
    ).all()
    computed = (
        frame["customer_count"] / frame["branch_customer_count"] * 100.0
    )
    assert (frame["customer_share"] - computed).abs().max() <= (
        SHARE_TOLERANCE_PP
    )
    # 한 지점·기간의 비중을 모두 더하면 100%가 된다.
    shares = grouped["customer_share"].sum()
    assert (shares - 100.0).abs().max() < 0.5


def test_fixture_asset_return_covers_every_branch(dataset):
    """자산규모별 수익률 표본이 표준 프레임까지 들어온다.

    행 수는 지점 × 자산 규모 구간이다. 원본이 마지막 한 달만 담고 있어
    기간이 한 달뿐이며, '전체' 지점 행은 여기서 빠져 있다.
    """
    frame = dataset.asset_return
    assert len(frame) == BRANCH_COUNT * ASSET_RETURN_ROWS
    assert set(frame.groupby("branch_id").size()) == {ASSET_RETURN_ROWS}
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.asset_return_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == ASSET_RETURN_ROWS


def test_fixture_asset_return_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    구간은 작은 쪽부터 큰 쪽 순이고, 수익률은 이미 %라 그대로 온다.
    손실이 난 구간은 음수로 남는다.
    """
    frame = dataset.asset_return
    assert list(frame["asset_group"].cat.categories) == list(ASSET_GROUPS)
    assert set(frame["asset_group"]) == set(ASSET_GROUPS)
    for column in ("return_1y", "return_3y"):
        assert frame[column].notna().all()
        assert (frame[column] < 0).any()
        assert (frame[column] > 0).any()
        # 0~1 비율이 아니라 %다. 비율이면 모든 값이 1 안에 들어온다.
        assert frame[column].abs().max() > 1.0


@pytest.mark.parametrize(
    "name, group_column, rows",
    [
        (name, group_column, rows)
        for name, (group_column, rows) in SEGMENT_RETURN_FRAMES.items()
    ],
)
def test_fixture_segment_return_covers_every_branch(
    dataset, name, group_column, rows
):
    """구간별 수익률 표본 여섯 개가 표준 프레임까지 들어온다.

    행 수는 지점 × 구간이다. 원본이 마지막 한 달만 담고 있어 기간이 한
    달뿐이며, '전체' 지점 행은 여기서 빠져 있다.
    """
    frame = getattr(dataset, name)
    assert len(frame) == BRANCH_COUNT * rows
    assert set(frame.groupby("branch_id").size()) == {rows}
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.total_of(name)
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == rows


@pytest.mark.parametrize(
    "name, group_column, rows",
    [
        (name, group_column, rows)
        for name, (group_column, rows) in SEGMENT_RETURN_FRAMES.items()
    ],
)
def test_fixture_segment_return_keeps_source_shapes(
    dataset, name, group_column, rows
):
    """원본의 성질이 화면까지 그대로 간다.

    구간은 원본이 늘어놓은 차례 그대로이고, 수익률은 이미 %라 그대로
    온다. 손실이 난 구간은 음수로 남는다. 구간 목록은 데이터 계층이 가진
    것과 같아야 하며, 표본은 그 구간을 모두 채운다.
    """
    frame = getattr(dataset, name)
    categories = list(frame[group_column].cat.categories)
    assert len(categories) == rows
    assert set(frame[group_column]) == set(categories)
    for column in ("return_1y", "return_3y"):
        assert frame[column].notna().all()
        assert (frame[column] < 0).any()
        assert (frame[column] > 0).any()
        # 0~1 비율이 아니라 %다. 비율이면 모든 값이 1 안에 들어온다.
        assert frame[column].abs().max() > 1.0


def test_fixture_transaction_total_rows_are_kept_apart(dataset):
    """원본의 '전체' 지점 행은 지점 데이터와 섞이지 않고 따로 남는다."""
    for name in ("transaction", "pension_transaction", "cash_flow", "revenue"):
        total = dataset.total_of(name)
        assert not total.empty
        assert set(total["branch_name"]) == {TOTAL_LABEL}


def test_fixture_covers_13_months():
    months = month_range()
    assert len(months) == MONTH_COUNT
    assert months[0] == "2025-07"
    assert months[-1] == "2026-07"


# --- 기준 월 계산 -------------------------------------------------------------
def test_shift_month_crosses_year_boundary():
    assert shift_month("2026-07", -1) == "2026-06"
    assert shift_month("2026-01", -1) == "2025-12"
    assert shift_month("2026-01", -YOY_MONTHS) == "2025-01"
    assert shift_month("2025-12", 2) == "2026-02"


def test_reference_months_are_derived_not_hardcoded():
    """기준 월 3개는 서로 손으로 맞추지 않는다.

    예전에는 YOY_BASE_MONTH가 START_MONTH와 같았는데, 이는 MONTH_COUNT가
    13이라 우연히 12개월 전과 일치했을 뿐이다. 기간을 늘리면 YoY라고
    표시하면서 2년 증가율을 계산하게 된다.
    """
    assert END_MONTH == shift_month(START_MONTH, MONTH_COUNT - 1)
    assert PREVIOUS_MONTH == shift_month(CURRENT_MONTH, -1)
    assert YOY_BASE_MONTH == shift_month(CURRENT_MONTH, -YOY_MONTHS)


def test_reference_month_follows_the_data(dataset):
    """기준 월은 상수가 아니라 데이터의 최신 월을 따라간다."""
    assert reference_month(dataset) == dataset.months[-1]

    trimmed = load_dashboard_data(
        filters={"base_months": [m for m in dataset.months if m <= "2026-03"]}
    )
    assert reference_month(trimmed) == "2026-03"


def test_reference_month_can_be_fixed_by_env(dataset, monkeypatch):
    monkeypatch.setenv(data_module.BASE_MONTH_ENV, "2026-01")
    assert reference_month(dataset) == "2026-01"


def test_reference_month_rejects_month_without_data(dataset, monkeypatch):
    """지정한 월에 데이터가 없으면 조용히 빈 화면이 되지 않고 오류를 낸다."""
    monkeypatch.setenv(data_module.BASE_MONTH_ENV, "2019-01")
    with pytest.raises(ValueError):
        reference_month(dataset)


def test_branch_count_is_27(dataset):
    assert dataset.monthly["branch_id"].nunique() == BRANCH_COUNT
    assert len(dataset.branch_names) == BRANCH_COUNT


def test_loading_twice_gives_the_same_data(dataset):
    again = load_dashboard_data()
    pd.testing.assert_frame_equal(dataset.monthly, again.monthly)


def test_age_and_investment_sums_stay_within_customer_count(dataset):
    """연령은 고객 수와 정확히 맞고, 투자성향은 넘지 않는다.

    투자성향은 화면에서 빼는 분류가 있어 합계가 고객 수보다 적을 수 있다.
    원본 안에서 분류 합계가 맞는지는 어댑터가 확인한다(→ test_source_adapter).
    """
    key = ["base_month", "branch_id"]
    base = dataset.monthly.set_index(key)["customer_count"]
    snapshot = base[base.index.get_level_values("base_month").isin(dataset.age["base_month"])]

    age_sum = dataset.age.groupby(key, observed=True)["customer_count"].sum()
    assert age_sum.reindex(snapshot.index).equals(snapshot)

    invest_sum = dataset.investment.groupby(key, observed=True)["customer_count"].sum()
    assert (invest_sum.reindex(snapshot.index) <= snapshot).all()


def test_share_columns_stay_within_range(dataset):
    """비율 컬럼은 0~100 안에 있어야 한다. 100을 곱하지 않았거나 두 번 곱하면 벗어난다."""
    for column in data_module.SUMMARY_SHARE_COLUMNS:
        values = dataset.summary[column]
        assert values.notna().all(), column
        assert values.between(0, 100).all(), column


def test_categories_are_complete_and_ordered(dataset):
    # '기타'(연령 미선택)까지 유효한 값으로 받는다. 화면 분포에서는 빠진다.
    assert list(dataset.age["age_group"].cat.categories) == list(
        ALL_AGE_GROUPS
    )
    assert list(dataset.investment["investment_type"].cat.categories) == list(INVESTMENT_TYPES)


def test_trend_has_growing_and_shrinking_branches(dataset):
    monthly = dataset.monthly
    first = monthly[monthly["base_month"] == "2025-07"].set_index("branch_name")["customer_count"]
    last = monthly[monthly["base_month"] == CURRENT_MONTH].set_index("branch_name")["customer_count"]
    change = (last - first).dropna()
    assert (change > 0).any(), "성장하는 지점이 있어야 한다"
    assert (change < 0).any(), "감소하는 지점이 있어야 한다"


def test_branch_size_spread_is_wide(dataset):
    counts = dataset.monthly[dataset.monthly["base_month"] == CURRENT_MONTH]["customer_count"]
    assert counts.max() / counts.min() > 3, "지점 규모 차이가 충분히 나타나야 한다"


def test_monthly_change_is_gradual(dataset):
    """월별 고객 수가 급격하게 튀지 않는지 확인한다."""
    monthly = dataset.monthly.sort_values(["branch_id", "base_month"])
    change = monthly.groupby("branch_id", observed=True)["customer_count"].pct_change().dropna()
    assert change.abs().max() < 0.06


def _with_shifted_age(dataset, gap: int) -> data_module.DashboardData:
    """연령 구간 한 칸의 인원수만 어긋뜨린 데이터."""
    broken_age = dataset.age.copy()
    broken_age.loc[0, "customer_count"] = (
        int(broken_age.loc[0, "customer_count"]) + gap
    )
    return data_module.DashboardData(
        monthly=dataset.monthly,
        age=broken_age,
        investment=dataset.investment,
        summary=dataset.summary,
    )


def test_validation_rejects_broken_data(dataset):
    """합계가 고객 수와 크게 어긋나면 멈춘다."""
    first = dataset.age.iloc[0]
    base = dataset.monthly.set_index(["base_month", "branch_id"])
    count = base.loc[
        (first["base_month"], first["branch_id"]), "customer_count"
    ]
    # 허용 범위를 확실히 넘는 차이.
    gap = int(data_module.COUNT_TOLERANCE + count * 0.05) + 1
    with pytest.raises(ValueError, match="너무 다릅니다"):
        validate_dashboard_data(_with_shifted_age(dataset, gap))


# --- 파일 간 고객 수 대조 -----------------------------------------------------
def _counts_pair(actual: list[int], expected: list[int]):
    index = pd.Index(["0001", "0002"], name="branch_id")
    return (
        pd.Series(actual, index=index, dtype=float),
        pd.Series(expected, index=index, dtype=float),
    )


def _gap_check(actual: list[int], expected: list[int]) -> None:
    left, right = _counts_pair(actual, expected)
    data_module.check_count_gap(
        left, right, "고객 수", "지점 프로필", "월별 고객 수"
    )


def test_count_gap_passes_when_two_files_agree():
    import warnings as std_warnings

    with std_warnings.catch_warnings():
        std_warnings.simplefilter("error")
        _gap_check([1200, 1600], [1200, 1600])


def test_count_gap_warns_within_the_tolerance():
    """하루 차이로 몇 명이 빠져나간 정도는 알리고 넘어간다."""
    with pytest.warns(UserWarning, match="조금 다릅니다") as caught:
        _gap_check([1199, 1600], [1200, 1600])
    message = str(caught[0].message)
    # 어느 파일의 어느 지점이 얼마나 다른지 그대로 알려 준다.
    assert "지점 프로필" in message and "월별 고객 수" in message
    assert "0001" in message and "1,199" in message and "1,200" in message


def test_count_gap_stops_when_the_files_are_far_apart():
    """크게 벌어지면 집계 기준 자체가 다르다는 뜻이다."""
    gap = data_module.COUNT_TOLERANCE + 1
    with pytest.raises(ValueError, match="너무 다릅니다") as error:
        _gap_check([1200 - gap, 1600], [1200, 1600])
    assert "COUNT_TOLERANCE" in str(error.value), "고칠 곳을 알려 준다"


def test_count_gap_scales_with_branch_size():
    """지점 규모가 제각각이라 비율로도 허용한다.

    큰 지점에서는 고정 인원만으로는 너무 빡빡하다.
    """
    big = 100_000
    allowed = int(big * data_module.COUNT_TOLERANCE_RATIO)
    assert allowed > data_module.COUNT_TOLERANCE
    with pytest.warns(UserWarning):
        _gap_check([big - allowed, 1600], [big, 1600])
    with pytest.raises(ValueError):
        _gap_check([big - allowed * 2, 1600], [big, 1600])


def test_count_gap_stops_when_a_key_is_missing():
    """한쪽에만 있는 지점은 값을 견줄 수 없다. 조용히 넘기지 않는다."""
    left = pd.Series([1200.0], index=pd.Index(["0001"], name="branch_id"))
    right = pd.Series([1200.0], index=pd.Index(["0009"], name="branch_id"))
    with pytest.raises(ValueError, match="한쪽에만 있는"):
        data_module.check_count_gap(
            left, right, "고객 수", "지점 프로필", "월별 고객 수"
        )


def test_validation_allows_a_small_gap_between_files(dataset):
    """원본이 다른 날 뽑히면 몇 명이 어긋난다. 그때는 알리고 넘어간다.

    연령 분포는 지점 프로필에서, 고객 수는 월별 파일에서 온다. 두 파일이
    하루만 달라도 그 사이에 빠져나간 고객만큼 수가 줄어든다.
    """
    with pytest.warns(UserWarning, match="조금 다릅니다"):
        validate_dashboard_data(
            _with_shifted_age(dataset, data_module.COUNT_TOLERANCE)
        )


# --- 실제 데이터 대비: 검증이 더미 기준을 강요하지 않는가 -----------------------
def test_validation_allows_other_periods_and_branch_counts(dataset):
    """기간과 지점 수는 실제 데이터에서 얼마든지 달라진다.

    예전에는 `month_range()`와 `BRANCH_COUNT`를 그대로 요구해서, 지점이 한 곳
    늘거나 데이터 기간이 밀리기만 해도 앱이 아예 뜨지 않았다(회귀 방지).
    """
    # 연령·투자성향·요약은 마지막 월 스냅샷만 담고 있으므로 그 월을 포함해 자른다.
    trimmed = load_dashboard_data(
        filters={
            "branch_names": dataset.branch_names[:5],
            "base_months": dataset.months[-3:],
        }
    )
    validate_dashboard_data(trimmed)


def test_validation_can_check_an_expected_range(dataset):
    """기간·지점 수를 지정하면 그것까지 확인한다. 표본 파일 점검에 쓴다."""
    with pytest.raises(ValueError):
        validate_dashboard_data(dataset, expected_branch_count=BRANCH_COUNT + 1)
    with pytest.raises(ValueError):
        validate_dashboard_data(dataset, expected_months=("2030-01",))


def test_snapshot_frames_may_cover_fewer_months(dataset):
    """연령·투자성향·요약은 특정 시점 스냅샷만 담을 수 있다.

    실제 원본은 월별 고객 수만 여러 달치이고 나머지는 최근 한 달치만 오기도 한다.
    """
    one_month = {
        name: frame[frame["base_month"] == CURRENT_MONTH]
        for name, frame in _frames(dataset).items()
        if name != "monthly"
    }
    validate_dashboard_data(
        data_module.DashboardData(monthly=dataset.monthly, **one_month)
    )


def test_frames_may_not_hold_months_missing_from_monthly(dataset):
    """monthly에 없는 월이 다른 데이터에 있으면 막는다. 기간의 기준은 monthly다."""
    stray_age = dataset.age.copy()
    stray_age["base_month"] = stray_age["base_month"].replace(CURRENT_MONTH, "2030-01")
    with pytest.raises(ValueError, match="monthly에 없는 기준 월"):
        validate_dashboard_data(
            data_module.DashboardData(**{**_frames(dataset), "age": stray_age})
        )


# --- 실제 데이터 대비: 값을 조용히 고치지 않는가 --------------------------------
@pytest.mark.parametrize(
    ("bad_value", "expected"),
    [
        (None, "숫자로 읽을 수 없는"),
        ("N/A", "숫자로 읽을 수 없는"),
        (-5, "음수"),
    ],
)
def test_unreadable_numbers_stop_instead_of_becoming_zero(dataset, bad_value, expected):
    """빈 칸을 0으로 덮으면 틀린 합계가 맞는 것처럼 화면에 뜬다(회귀 방지)."""
    broken = dataset.monthly.astype({"customer_count": object})
    broken.loc[0, "customer_count"] = bad_value
    with pytest.raises(ValueError, match=expected):
        _normalized(dataset, monthly=broken)


def test_bad_month_format_is_rejected(dataset):
    broken = dataset.monthly.copy()
    broken.loc[0, "base_month"] = "2027/01"
    with pytest.raises(ValueError, match="YYYY-MM"):
        _normalized(dataset, monthly=broken)


# --- 실제 데이터 대비: 모르는 분류값이 원인을 알려주는가 -------------------------
def test_unknown_category_names_the_offending_value(dataset):
    """모르는 값을 Categorical로 만들면 조용히 결측이 되고 원인이 숨는다."""
    broken = dataset.age.copy()
    broken["age_group"] = broken["age_group"].astype(str).replace({"20대": "20~29세"})
    with pytest.raises(ValueError, match="20~29세"):
        _normalized(dataset, age=broken)


def test_text_booleans_are_read_correctly(dataset):
    """원본이 'Y'/'N' 문자열이어도 뒤집히지 않는다.

    문자열을 bool로 그냥 바꾸면 빈 문자열이 아닌 모든 값이 참이 되어
    'N'까지 동의로 바뀐다.
    """
    source = dataset.investment.copy()
    expected = int(source["marketing_consent"].sum())
    source["marketing_consent"] = ["Y" if flag else "N" for flag in source["marketing_consent"]]
    normalized = _normalized(dataset, investment=source)
    assert int(normalized.investment["marketing_consent"].sum()) == expected


def test_unknown_boolean_text_is_rejected(dataset):
    source = dataset.investment.copy()
    source["marketing_consent"] = ["예" if flag else "아니오" for flag in source["marketing_consent"]]
    with pytest.raises(ValueError, match="참·거짓"):
        _normalized(dataset, investment=source)


# --- 실제 데이터 대비: 원본이 숫자 컬럼일 때 ------------------------------------
def test_numeric_month_and_branch_id_are_read(dataset):
    """실제 데이터는 지점명 말고 전부 숫자다. 202507도 2026-01처럼 읽어야 한다."""
    frames = {}
    for name, frame in _frames(dataset).items():
        frame = frame.copy()
        frame["base_month"] = frame["base_month"].str.replace("-", "").astype(int)
        frame["branch_id"] = frame["branch_id"].str.lstrip("B").astype(int)
        frames[name] = frame

    normalized = data_module._normalize(data_module.DashboardData(**frames))
    assert normalized.months == dataset.months
    # 숫자 코드는 문자열로 맞춘다. '1.0' 같은 소수점 표기가 남으면 안 된다.
    assert not normalized.monthly["branch_id"].str.contains(".", regex=False).any()
    assert normalized.monthly["customer_count"].sum() == dataset.monthly["customer_count"].sum()


def test_unreadable_month_names_the_value(dataset):
    broken = dataset.monthly.astype({"base_month": object})
    broken.loc[0, "base_month"] = "2027/01"
    with pytest.raises(ValueError, match="YYYY-MM"):
        _normalized(dataset, monthly=broken)


# --- 실제 데이터 대비: 원본에 '전체' 합계 행이 있을 때 --------------------------
def _with_source_total(dataset) -> dict[str, pd.DataFrame]:
    """원본처럼 '전체' 합계 행을 덧붙인 4개 프레임."""
    frames = {}
    for name, frame in _frames(dataset).items():
        keys = [
            column
            for column in (
                "base_month",
                "age_group",
                "investment_type",
                "marketing_consent",
                "asset_type",
                "product_type",
                "pension_type",
                "channel",
                "revenue_type",
                "return_period",
                "return_group",
                "asset_group",
                "usage_day_group",
                *(
                    group_column
                    for group_column, _ in SEGMENT_RETURN_FRAMES.values()
                ),
            )
            if column in frame.columns
        ]
        total = frame.groupby(keys, observed=True, as_index=False).sum(numeric_only=True)
        if "average_age" in frame.columns:
            total["average_age"] = frame.groupby(keys, observed=True)["average_age"].mean().values
        total["branch_id"] = "ALL"
        total["branch_name"] = TOTAL_LABEL
        frames[name] = pd.concat([frame, total], ignore_index=True)
    return frames


def test_source_total_row_is_separated_from_branches(dataset):
    """원본의 '전체' 행을 지점으로 세면 모든 숫자가 두 배가 된다(회귀 방지)."""
    normalized = data_module._normalize(data_module.DashboardData(**_with_source_total(dataset)))
    validate_dashboard_data(normalized)

    assert TOTAL_LABEL not in normalized.branch_names
    assert len(normalized.branch_names) == BRANCH_COUNT
    assert normalized.monthly["customer_count"].sum() == dataset.monthly["customer_count"].sum()


def test_source_total_that_disagrees_with_branches_is_reported(dataset):
    frames = _with_source_total(dataset)
    monthly = frames["monthly"]
    monthly.loc[monthly["branch_name"] == TOTAL_LABEL, "customer_count"] += 999
    with pytest.raises(ValueError, match="지점 합계"):
        data_module._normalize(data_module.DashboardData(**frames))


# --- 실제 데이터 대비: 동의·불원이 각각 인원수 컬럼일 때 ------------------------
def test_investment_wide_form_is_reshaped(dataset):
    """원본은 동의 여부 플래그가 아니라 동의·불원 인원수를 각각 담고 있다."""
    long_form = dataset.investment
    wide = (
        long_form.pivot_table(
            index=["base_month", "branch_id", "branch_name", "investment_type"],
            columns="marketing_consent",
            values="customer_count",
            aggfunc="sum",
            observed=True,
        )
        .reset_index()
        .rename(columns={True: "consent_customer_count", False: "non_consent_customer_count"})
    )
    wide.columns.name = None

    normalized = _normalized(dataset, investment=wide)
    pd.testing.assert_frame_equal(
        normalized.investment.sort_values(list(normalized.investment.columns)).reset_index(
            drop=True
        ),
        long_form.sort_values(list(long_form.columns)).reset_index(drop=True),
    )


def test_category_codes_translate_numeric_values(dataset, monkeypatch):
    """원본이 연령 구간을 숫자 코드로 담고 있으면 코드표로 이름을 붙인다."""
    codes = {str(index + 1): group for index, group in enumerate(AGE_GROUPS)}
    monkeypatch.setattr(data_module, "AGE_GROUP_CODES", codes)

    numeric_age = dataset.age.copy()
    reverse = {group: int(code) for code, group in codes.items()}
    numeric_age["age_group"] = numeric_age["age_group"].map(reverse).astype(int)

    normalized = _normalized(dataset, age=numeric_age)
    assert list(normalized.age["age_group"].cat.categories) == list(
        ALL_AGE_GROUPS
    )
    assert normalized.age["age_group"].isna().sum() == 0


def test_unknown_category_hints_at_the_code_table(dataset):
    broken = dataset.age.copy()
    broken["age_group"] = broken["age_group"].map({group: index for index, group in enumerate(AGE_GROUPS)})
    with pytest.raises(ValueError, match="코드표"):
        _normalized(dataset, age=broken)


# --- 실제 데이터 대비: pkl 읽기 ------------------------------------------------
def test_pickle_source_round_trip(dataset, tmp_path, monkeypatch):
    path = tmp_path / "dashboard.pkl"
    pd.to_pickle(_frames(dataset), path)
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, str(path))
    # 표준 4개 프레임을 담은 dict 하나로 읽는 경로를 확인한다.
    monkeypatch.setenv(sources.profile.FILE_ENV, "")

    loaded = load_dashboard_data()
    pd.testing.assert_frame_equal(loaded.monthly, dataset.monthly)
    assert loaded.months == dataset.months
    assert loaded.branch_names == dataset.branch_names


def test_pickle_reload_when_the_file_changes(dataset, tmp_path, monkeypatch):
    """파일을 새로 내보내면 앱을 다시 켜지 않아도 새 내용을 읽는다."""
    path = tmp_path / "dashboard.pkl"
    pd.to_pickle(_frames(dataset), path)
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, str(path))
    # 표준 4개 프레임을 담은 dict 하나로 읽는 경로를 확인한다.
    monkeypatch.setenv(sources.profile.FILE_ENV, "")
    assert load_dashboard_data().months == dataset.months

    trimmed = load_dashboard_data(filters={"base_months": dataset.months[-4:]})
    pd.to_pickle(_frames(trimmed), path)
    assert load_dashboard_data().months == dataset.months[-4:]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("dict가 아님", "dict가 아니라"),
        ({"monthly": pd.DataFrame()}, "다음 데이터가 없습니다"),
    ],
)
def test_pickle_with_wrong_shape_explains_what_is_needed(
    tmp_path, monkeypatch, content, expected
):
    path = tmp_path / "wrong.pkl"
    pd.to_pickle(content, path)
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, str(path))
    # 표준 4개 프레임을 담은 dict 하나로 읽는 경로를 확인한다.
    monkeypatch.setenv(sources.profile.FILE_ENV, "")
    with pytest.raises(ValueError, match=expected):
        load_dashboard_data()


def test_pickle_path_must_be_given_and_exist(monkeypatch, tmp_path):
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, "")
    with pytest.raises(ValueError, match=sources.monthly.FILE_ENV):
        load_dashboard_data()

    monkeypatch.setenv(sources.monthly.FILE_ENV, str(tmp_path / "없는파일.pkl"))
    with pytest.raises(ValueError, match="찾을 수 없습니다"):
        load_dashboard_data()


def test_unknown_data_source_is_rejected(monkeypatch):
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "oracle")
    with pytest.raises(ValueError):
        load_dashboard_data()


def test_filters_narrow_the_result(dataset):
    filtered = load_dashboard_data(filters={"branch_names": ["지점 01"], "base_months": [CURRENT_MONTH]})
    assert filtered.monthly["branch_name"].unique().tolist() == ["지점 01"]
    assert filtered.monthly["base_month"].unique().tolist() == [CURRENT_MONTH]


# --- 디지털 채널 표본 --------------------------------------------------------
def test_fixture_digital_channel_covers_every_branch(dataset):
    """디지털채널1 표본이 채널로 펴진 채 표준 프레임까지 들어온다.

    원본은 채널 셋을 한 행에 가로로 담고 있어, 행 수는 지점 × 월 × 채널이
    된다. 두 원본 모두 열세 달을 담고 있고, '전체' 지점 행은 여기서 빠져
    있다.
    """
    frame = dataset.digital_channel
    expected = BRANCH_COUNT * MONTH_COUNT * DIGITAL_CHANNEL_COUNT
    assert len(frame) == expected
    assert list(frame["channel"].cat.categories) == list(DIGITAL_CHANNELS)
    assert set(frame["channel"]) == set(DIGITAL_CHANNELS)
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == month_range()

    total = dataset.digital_channel_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == MONTH_COUNT * DIGITAL_CHANNEL_COUNT


def test_fixture_digital_channel_keeps_source_shapes(dataset):
    """원본의 성질이 화면까지 그대로 간다.

    이용 비중은 이미 %라 그대로 오고, 이용 고객 수는 그 지점의 고객 수를
    넘지 않는다. 세 채널을 더한 비중은 100%를 넘을 수 있다. 한 고객이 여러
    창구를 쓰기 때문이다(→ data.DIGITAL_CHANNELS).
    """
    frame = dataset.digital_channel
    assert frame["user_count"].notna().all()
    assert (frame["user_count"] > 0).all()
    assert frame["user_share"].between(0, 100).all()
    # 0~1 비율이 아니라 %다. 비율이면 모든 값이 1 안에 들어온다.
    assert frame["user_share"].max() > 1.0

    counts = dataset.monthly.set_index(["base_month", "branch_id"])
    counts = counts["customer_count"]
    keys = list(zip(frame["base_month"], frame["branch_id"]))
    limit = counts.loc[keys].to_numpy()
    assert (frame["user_count"].to_numpy() <= limit).all()


def test_fixture_digital_values_reach_the_monthly_frame(dataset):
    """채널로 나뉘지 않는 값은 월별 프레임에 따로 붙는다.

    디지털채널1의 고객 수는 `digital_customer_count`로 들어가고, 화면 전체가
    쓰는 `customer_count`는 월별 파일 값 그대로다. 한쪽이 다른 쪽을 덮지
    않는다(→ data.MONTHLY_DIGITAL_COLUMNS).
    """
    monthly = dataset.monthly
    for column in MONTHLY_DIGITAL_COLUMNS:
        assert monthly[column].notna().all()
    assert "customer_count" in monthly.columns
    assert DIGITAL_CUSTOMER_COLUMN != "customer_count"
    assert monthly[DIGITAL_TRADE_SHARE_COLUMN].between(0, 100).all()


def test_fixture_digital_profile_covers_every_branch(dataset):
    """디지털채널2 표본도 같은 채널 축으로 펴져 들어온다."""
    frame = dataset.digital_profile
    expected = BRANCH_COUNT * MONTH_COUNT * DIGITAL_CHANNEL_COUNT
    assert len(frame) == expected
    assert list(frame["channel"].cat.categories) == list(DIGITAL_CHANNELS)
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == month_range()

    total = dataset.digital_profile_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == MONTH_COUNT * DIGITAL_CHANNEL_COUNT


def test_fixture_digital_profile_keeps_source_shapes(dataset):
    """평균 연령·평균 자산·잔고 비중이 각자의 단위로 남는다.

    자산평균은 **원**이라 월별 프레임의 평균 자산(백만원)과 자릿수가 다르다.
    상품 비중 여섯의 합은 100%가 되지 않아도 된다. 이 여섯에 들어가지 않는
    잔고가 있을 수 있다(→ dashboard/sources/digital2.py).
    """
    frame = dataset.digital_profile
    assert frame["average_age"].between(20, 90).all()
    assert (frame["average_assets_won"] > 1_000_000).all()
    for column in DIGITAL_PROFILE_SHARE_COLUMNS:
        assert frame[column].between(0, 100).all()
        assert frame[column].max() > 1.0
    mixed = frame[list(DIGITAL_PROFILE_SHARE_COLUMNS)].sum(axis=1)
    assert (mixed <= 100.0).all()


def test_fixture_digital_channels_tell_different_stories(dataset):
    """채널마다 고객층이 다르다. 펴는 과정에서 값이 뒤섞이지 않았다.

    HTS 쪽이 MTS 쪽보다 나이가 많고 자산이 크다. 값이 채널을 넘어 섞였다면
    이 차이가 사라진다.
    """
    frame = dataset.digital_profile
    by_channel = frame.groupby("channel", observed=True)
    ages = by_channel["average_age"].mean()
    assets = by_channel["average_assets_won"].mean()
    assert ages["HTS"] > ages["MTS"]
    assert assets["HTS"] > assets["MTS"]


def test_fixture_digital_usage_days_covers_every_branch(dataset):
    """디지털채널3 표본이 채널로 펴진 채 표준 프레임까지 들어온다.

    행 수는 지점 × 이용일수 구간 × 채널이다. 이 원본만 마지막 한 달을
    담고 있어 기간이 한 달뿐이며, '전체' 지점 행은 따로 떨어져 나간다.
    """
    frame = dataset.digital_usage_days
    per_branch = DIGITAL_USAGE_DAY_ROWS * DIGITAL_CHANNEL_COUNT
    assert len(frame) == BRANCH_COUNT * per_branch
    assert set(frame.groupby("branch_id").size()) == {per_branch}
    assert TOTAL_LABEL not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == [END_MONTH]

    total = dataset.digital_usage_days_total
    assert set(total["branch_name"]) == {TOTAL_LABEL}
    assert len(total) == per_branch


def test_fixture_digital_usage_days_keeps_source_shapes(dataset):
    """구간 차례와 비중이 원본대로 남는다.

    구간은 적게 쓴 쪽부터 많이 쓴 쪽 순이고, 앞에 붙어 있던 번호는 떨어져
    나간다. 비중은 이미 %라 그대로 온다.
    """
    frame = dataset.digital_usage_days
    assert list(frame["usage_day_group"].cat.categories) == list(
        DIGITAL_USAGE_DAY_GROUPS
    )
    assert set(frame["usage_day_group"]) == set(DIGITAL_USAGE_DAY_GROUPS)
    assert list(frame["channel"].cat.categories) == list(DIGITAL_CHANNELS)
    assert frame["day_group_share"].notna().all()
    assert frame["day_group_share"].between(0, 100).all()
    # 0~1 비율이 아니라 %다. 비율이면 모든 값이 1 안에 들어온다.
    assert frame["day_group_share"].max() > 1.0


def test_fixture_digital_usage_days_differ_by_channel(dataset):
    """채널마다 이용일수가 다르게 쏠린다. 펴는 과정에서 섞이지 않았다.

    HTS 쪽이 MTS 쪽보다 '0일(미사용)' 칸이 크다. 값이 채널을 넘어 섞였다면
    이 차이가 사라진다.
    """
    frame = dataset.digital_usage_days
    unused = frame[frame["usage_day_group"] == DIGITAL_USAGE_DAY_GROUPS[0]]
    by_channel = unused.groupby("channel", observed=True)
    shares = by_channel["day_group_share"].mean()
    assert shares["HTS"] > shares["MTS"]
