"""거래 탭 검증.

패널 여섯 개가 각각 어느 원본을 쓰는지, 선택 컨트롤이 실제로 그림을
바꾸는지, 원본에 없는 값을 0으로 채우지 않는지 확인한다.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import callbacks
from dashboard import tabs as tab_registry
from dashboard.data import (
    CASH_FLOW_CHANNELS,
    CASH_FLOW_CHANNEL_TOTAL,
    PENSION_TRADE_PRODUCT_TYPES,
    PENSION_TYPES,
    TOTAL_LABEL,
    TRADE_PRODUCT_TOTAL,
    TRADE_PRODUCT_TYPES,
    YOY_MONTHS,
    load_dashboard_data,
    reference_month,
    shift_month,
)
from dashboard.tabs.registry import KIND_DROPDOWN, KIND_RADIO
from dashboard.tabs.transaction import PENSION_MIX_MEASURE, TAB

CHARTS = {chart.key: chart for chart in TAB.charts}

COUNT_MEASURE = "거래고객수"
AMOUNT_MEASURE = "거래금액"


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def draw(key: str, data, **selection):
    chart = CHARTS[key]
    chosen = chart.defaults(data)
    chosen.update(selection)
    return chart.build(data, chosen)


# --- 탭 등록 ----------------------------------------------------------------
def test_transaction_tab_is_registered_with_six_panels():
    assert tab_registry.find("transaction") is TAB
    assert [chart.key for chart in TAB.charts] == [
        "total",
        "growth",
        "product",
        "productgrowth",
        "cashflow",
        "pension",
    ]


def test_transaction_tab_sits_right_of_the_asset_tab():
    """탭 순서는 고객 → 자산 → 거래 → 수익 순이다."""
    order = [value for value, _label in tab_registry.TAB_ORDER]
    labels = dict(tab_registry.TAB_ORDER)
    assert labels["transaction"] == "거래"
    assert order[order.index("asset") + 1] == "transaction"
    assert order[order.index("transaction") + 1] == "profit"
    assert labels["profit"] == "수익"


def test_profit_tab_is_named_but_not_implemented():
    """아직 만들지 않은 탭은 이름만 비활성으로 나타난다."""
    assert tab_registry.find("profit") is None


def test_every_panel_returns_a_figure(dataset):
    for chart in TAB.charts:
        figure = chart.build(dataset, chart.defaults(dataset))
        assert isinstance(figure, go.Figure), chart.key
        assert figure.data, chart.key


def test_measure_panels_offer_both_measures(dataset):
    """거래고객수·거래금액을 함께 고를 수 있어야 두 눈으로 견줄 수 있다."""
    for key in ("total", "growth", "product", "productgrowth"):
        options = CHARTS[key].option_map(dataset)
        assert options["measure"] == [COUNT_MEASURE, AMOUNT_MEASURE], key


# --- 1. 거래 종합 ------------------------------------------------------------
def test_total_draws_total_as_bars_and_branch_as_a_line(dataset):
    figure = draw("total", dataset)
    kinds = [trace.type for trace in figure.data]
    assert kinds == ["bar", "scatter"]
    assert figure.data[0].name == TOTAL_LABEL
    assert figure.data[1].name == dataset.branch_names[0]


def test_total_uses_the_total_product_row_as_given(dataset):
    """'전체' 상품은 상품별 합이 아니라 원본 값을 그대로 쓴다."""
    month = reference_month(dataset)
    figure = draw("total", dataset, measure=AMOUNT_MEASURE)
    given = dataset.transaction_total
    expected = given[
        (given["base_month"] == month)
        & (given["product_type"] == TRADE_PRODUCT_TOTAL)
    ]["trade_amount"].iloc[0]
    assert figure.data[0].y[-1] == pytest.approx(float(expected))


def test_total_follows_the_branch_choice(dataset):
    other = dataset.branch_names[1]
    figure = draw("total", dataset, branch=other)
    assert figure.data[1].name == other


def test_total_measure_changes_the_axis(dataset):
    counts = draw("total", dataset, measure=COUNT_MEASURE)
    amounts = draw("total", dataset, measure=AMOUNT_MEASURE)
    assert "명" in counts.layout.yaxis.title.text
    assert "억원" in amounts.layout.yaxis.title.text
    assert list(counts.data[0].y) != list(amounts.data[0].y)


# --- 2. 거래 증가율 ----------------------------------------------------------
def test_growth_puts_one_point_on_each_branch(dataset):
    figure = draw("growth", dataset)
    assert len(figure.data) == 1
    assert len(figure.data[0].x) == len(dataset.branch_names)


def test_growth_compares_against_the_same_month_last_year(dataset):
    """세로축은 전년 동월 대비다. 12개월 전 값에서 계산한다."""
    current = reference_month(dataset)
    base = shift_month(current, -YOY_MONTHS)
    figure = draw("growth", dataset, measure=AMOUNT_MEASURE)

    rows = dataset.transaction
    picked = rows[rows["product_type"] == TRADE_PRODUCT_TOTAL]
    now = picked[picked["base_month"] == current].set_index("branch_name")
    then = picked[picked["base_month"] == base].set_index("branch_name")
    name = str(figure.data[0].text[0])
    expected = (
        now.loc[name, "trade_amount"] / then.loc[name, "trade_amount"] - 1
    ) * 100
    assert figure.data[0].y[0] == pytest.approx(expected)


def test_growth_axis_follows_the_measure(dataset):
    counts = draw("growth", dataset, measure=COUNT_MEASURE)
    amounts = draw("growth", dataset, measure=AMOUNT_MEASURE)
    assert counts.layout.xaxis.title.text == "거래고객수(명)"
    assert amounts.layout.xaxis.title.text == "거래금액(억원)"
    for figure in (counts, amounts):
        assert "YoY" in figure.layout.yaxis.title.text


# --- 3. 상품별 거래 ----------------------------------------------------------
def test_product_panel_offers_every_product_but_the_total(dataset):
    """'전체' 상품은 거래 종합 패널이 맡는다."""
    options = CHARTS["product"].option_map(dataset)
    assert options["product"] == list(TRADE_PRODUCT_TYPES)
    assert TRADE_PRODUCT_TOTAL not in options["product"]


def test_product_panel_draws_the_chosen_product(dataset):
    month = reference_month(dataset)
    figure = draw(
        "product", dataset, product="채권", measure=AMOUNT_MEASURE
    )
    given = dataset.transaction_total
    expected = given[
        (given["base_month"] == month) & (given["product_type"] == "채권")
    ]["trade_amount"].iloc[0]
    assert figure.data[0].y[-1] == pytest.approx(float(expected))
    assert "채권" in figure.layout.yaxis.title.text


def test_product_panel_has_two_dropdowns_and_one_radio(dataset):
    kinds = {select.key: select.kind for select in CHARTS["product"].selects}
    assert kinds == {
        "branch": KIND_DROPDOWN,
        "product": KIND_DROPDOWN,
        "measure": KIND_RADIO,
    }


# --- 4. 상품별 증가율 --------------------------------------------------------
def test_product_growth_follows_the_product_choice(dataset):
    stocks = draw("productgrowth", dataset, product="국내주식")
    bonds = draw("productgrowth", dataset, product="채권")
    assert "국내주식" in stocks.layout.xaxis.title.text
    assert "채권" in bonds.layout.xaxis.title.text
    assert list(stocks.data[0].x) != list(bonds.data[0].x)


# --- 5. 입출금 ---------------------------------------------------------------
def test_cash_flow_draws_one_bar_and_two_lines(dataset):
    figure = draw("cashflow", dataset)
    kinds = [trace.type for trace in figure.data]
    assert kinds == ["bar", "scatter", "scatter"]
    names = [trace.name for trace in figure.data]
    assert names == [
        f"순입금 {TOTAL_LABEL}",
        f"순입금 {CASH_FLOW_CHANNELS[0]}",
        f"순입금 {CASH_FLOW_CHANNELS[1]}",
    ]


def test_cash_flow_lines_add_up_to_the_bar(dataset):
    figure = draw("cashflow", dataset, scope=dataset.branch_names[0])
    bar, securities, bank = (trace.y for trace in figure.data)
    for total, first, second in zip(bar, securities, bank):
        assert total == pytest.approx(first + second, abs=0.05)


def test_cash_flow_offers_the_total_and_every_branch(dataset):
    options = CHARTS["cashflow"].option_map(dataset)
    assert options["scope"] == [TOTAL_LABEL, *dataset.branch_names]


def test_cash_flow_keeps_negative_months(dataset):
    """순입금은 빠져나간 달에 음수가 된다. 0으로 접지 않는다."""
    seen = False
    for scope in (TOTAL_LABEL, *dataset.branch_names):
        figure = draw("cashflow", dataset, scope=scope)
        if any(value < 0 for value in figure.data[0].y):
            seen = True
            # 축이 0을 품고 있어야 부호를 읽을 수 있다.
            assert figure.layout.yaxis.range[0] < 0
            break
    assert seen, "표본에 순입금이 음수인 달이 없습니다"


# --- 6. 연금 거래 구성 -------------------------------------------------------
def test_pension_stacks_every_product(dataset):
    figure = draw("pension", dataset)
    assert figure.layout.barmode == "stack"
    assert [trace.name for trace in figure.data] == list(
        PENSION_TRADE_PRODUCT_TYPES
    )


def test_pension_is_fixed_to_the_amount(dataset):
    """지표를 고르게 하지 않는다.

    거래고객수로는 구성을 읽을 수 없다. '기타'에 원본 값이 없어 한 칸이
    빠지고, 남은 칸을 더해도 전체 거래고객수가 되지 않는다.
    """
    keys = [select.key for select in CHARTS["pension"].selects]
    assert "measure" not in keys
    assert keys == ["scope", "pension"]
    assert PENSION_MIX_MEASURE == AMOUNT_MEASURE
    assert "억원" in draw("pension", dataset).layout.yaxis.title.text
    # 무엇을 기준으로 쌓았는지 카드에 적혀 있어야 한다.
    assert PENSION_MIX_MEASURE in CHARTS["pension"].description(dataset)


def test_pension_follows_the_pension_type(dataset):
    options = CHARTS["pension"].option_map(dataset)
    assert options["pension"] == list(PENSION_TYPES)
    personal = draw("pension", dataset, pension=PENSION_TYPES[0])
    irp = draw("pension", dataset, pension=PENSION_TYPES[1])
    assert list(personal.data[0].y) != list(irp.data[0].y)


def test_pension_uses_the_total_row_for_the_total_scope(dataset):
    month = reference_month(dataset)
    figure = draw("pension", dataset, scope=TOTAL_LABEL, pension="DC")
    given = dataset.pension_transaction_total
    expected = given[
        (given["base_month"] == month)
        & (given["pension_type"] == "DC")
        & (given["product_type"] == PENSION_TRADE_PRODUCT_TYPES[0])
    ]["trade_amount"].iloc[0]
    assert figure.data[0].y[-1] == pytest.approx(float(expected))


# --- 빈 데이터 --------------------------------------------------------------
def test_panels_survive_missing_transaction_sources(dataset):
    """거래 원본이 없어도 화면이 깨지지 않고 안내 상태가 된다."""
    empty = type(dataset)(
        monthly=dataset.monthly,
        age=dataset.age,
        investment=dataset.investment,
        summary=dataset.summary,
        transaction=pd.DataFrame(),
        pension_transaction=pd.DataFrame(),
        cash_flow=pd.DataFrame(),
    )
    for chart in TAB.charts:
        figure = chart.build(empty, chart.defaults(empty))
        assert isinstance(figure, go.Figure), chart.key
        assert not figure.data, chart.key
        assert figure.layout.annotations, chart.key


# --- 콜백 -------------------------------------------------------------------
def test_callback_ids_are_unique_across_tabs(dataset):
    ids = [
        chart.chart_id(TAB.value) for chart in TAB.charts
    ] + [
        chart.select_id(TAB.value, select.key)
        for chart in TAB.charts
        for select in chart.selects
    ]
    assert len(ids) == len(set(ids))
    assert all(identifier.startswith("transaction-") for identifier in ids)


def test_initial_view_includes_the_transaction_tab(dataset):
    view = callbacks.build_initial_view(dataset)
    assert "transaction" in view["tabs"]


def test_channel_total_is_named_like_the_branch_total():
    """채널 축의 '전체'와 지점 축의 '전체'는 이름이 같지만 다른 축이다."""
    assert CASH_FLOW_CHANNEL_TOTAL == TOTAL_LABEL
