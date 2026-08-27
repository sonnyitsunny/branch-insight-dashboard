"""수익 탭 검증.

패널 넷이 각각 수익1의 어느 값을 쓰는지, 선택 컨트롤이 실제로 그림을
바꾸는지, 원본에 없는 값을 0으로 채우지 않는지 확인한다.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import callbacks
from dashboard import tabs as tab_registry
from dashboard.data import (
    REVENUE_FINAL,
    REVENUE_PENSION,
    REVENUE_PRODUCT_TYPES,
    REVENUE_RETAIL,
    TOTAL_LABEL,
    YOY_MONTHS,
    load_dashboard_data,
    reference_month,
    shift_month,
)
from dashboard.tabs.profit import (
    CHART_AMOUNT_DIVISOR,
    CHART_AMOUNT_UNIT,
    MIX_SLOTS,
    MIX_TYPES,
    TAB,
    figures,
    metrics,
)
from dashboard.tabs.registry import KIND_DROPDOWN, VARIANTS_SLOT

CHARTS = {chart.key: chart for chart in TAB.charts}


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def draw(key: str, data, **selection):
    chart = CHARTS[key]
    chosen = chart.defaults(data)
    chosen.update(selection)
    return chart.build(data, chosen)


def _final_rows(data, month: str, total: bool = False) -> pd.DataFrame:
    frame = data.revenue_total if total else data.revenue
    return frame[
        (frame["base_month"] == month)
        & (frame["revenue_type"] == REVENUE_FINAL)
    ]


# --- 탭 등록 ----------------------------------------------------------------
def test_profit_tab_is_registered_with_four_panels():
    assert tab_registry.find("profit") is TAB
    assert [chart.key for chart in TAB.charts] == [
        "trend",
        "mix",
        "amount",
        "share",
    ]


def test_profit_tab_sits_right_of_the_transaction_tab():
    order = [value for value, _label in tab_registry.TAB_ORDER]
    assert dict(tab_registry.TAB_ORDER)["profit"] == "수익"
    assert order[order.index("transaction") + 1] == "profit"


def test_every_panel_returns_a_figure(dataset):
    for chart in TAB.charts:
        figure = chart.build(dataset, chart.defaults(dataset))
        assert isinstance(figure, go.Figure), chart.key
        assert figure.data, chart.key


def test_panel_ids_do_not_collide(dataset):
    ids = [chart.chart_id("profit") for chart in TAB.charts]
    for chart in TAB.charts:
        ids.extend(
            chart.select_id("profit", select.key)
            for select in chart.selects
        )
    assert len(ids) == len(set(ids))


def test_initial_view_carries_every_panel(dataset):
    """첫 화면 값에 네 패널이 모두 들어 있다.

    두 산점도는 보조 문구를 두지 않는다. 헤더 오른쪽에는 확대·축소 안내만
    남는다(→ Chart.note).
    """
    view = callbacks.build_initial_view(dataset)["tabs"]["profit"]
    for chart in TAB.charts:
        panel = view["charts"][chart.key]
        assert isinstance(panel["figure"], go.Figure), chart.key
        if chart.description:
            assert panel["description"], chart.key
        else:
            assert panel["description"] == "", chart.key


# --- 1. 수익 추이 ------------------------------------------------------------
def test_trend_draws_all_customer_amount_as_bars(dataset):
    """막대는 전체고객 '최종' 수익이다. 원본은 원, 막대는 억원이다."""
    figure = draw("trend", dataset)
    bar = figure.data[0]
    assert isinstance(bar, go.Bar)

    total = dataset.revenue_total
    expected = [
        value / CHART_AMOUNT_DIVISOR
        for value in total[total["revenue_type"] == REVENUE_FINAL]
        .sort_values("base_month")["all_revenue_amount"]
    ]
    assert list(bar.y) == pytest.approx(expected)
    assert CHART_AMOUNT_UNIT in figure.layout.yaxis.title.text


def test_trend_draws_common_share_as_a_line_on_the_right_axis(dataset):
    """선은 공통고객 수익 비중(%)이고 단위가 달라 오른쪽 축에 붙는다."""
    figure = draw("trend", dataset)
    line = figure.data[1]
    assert isinstance(line, go.Scatter)
    assert line.yaxis == "y2"
    assert figure.layout.yaxis2.ticksuffix == "%"

    total = dataset.revenue_total
    expected = (
        total[total["revenue_type"] == REVENUE_FINAL]
        .sort_values("base_month")["common_revenue_share"]
        .tolist()
    )
    assert list(line.y) == pytest.approx(expected)


def test_trend_scope_offers_the_total_and_every_branch(dataset):
    select = CHARTS["trend"].selects[0]
    assert select.kind == KIND_DROPDOWN
    options = select.options(dataset)
    assert options[0] == TOTAL_LABEL
    assert options[1:] == dataset.branch_names


def test_trend_follows_the_chosen_branch(dataset):
    """지점을 고르면 그 지점 값으로 바뀐다."""
    branch = dataset.branch_names[0]
    figure = draw("trend", dataset, scope=branch)

    rows = dataset.revenue
    picked = rows[
        (rows["branch_name"] == branch)
        & (rows["revenue_type"] == REVENUE_FINAL)
    ].sort_values("base_month")
    assert list(figure.data[0].y) == pytest.approx(
        [
            value / CHART_AMOUNT_DIVISOR
            for value in picked["all_revenue_amount"]
        ]
    )
    assert branch in figure.data[0].hovertemplate


def test_trend_uses_the_source_share_as_given(dataset):
    """비중을 금액에서 되계산하지 않는다.

    원본 비중을 바꿔 두면 금액과 앞뒤가 맞지 않는데, 그래도 그 값이
    그대로 선에 실려야 한다.
    """
    changed = dataset.revenue_total.copy()
    is_final = changed["revenue_type"] == REVENUE_FINAL
    changed.loc[is_final, "common_revenue_share"] = 12.5

    trend = metrics.revenue_trend(
        dataset.revenue,
        changed,
        TOTAL_LABEL,
        TOTAL_LABEL,
        REVENUE_FINAL,
        "all_revenue_amount",
        "common_revenue_share",
    )
    assert (trend["share"] == 12.5).all()


def test_trend_is_empty_without_the_source(dataset):
    """수익1이 없으면 안내 상태가 된다. 0으로 채우지 않는다."""
    trend = metrics.revenue_trend(
        pd.DataFrame(),
        None,
        TOTAL_LABEL,
        TOTAL_LABEL,
        REVENUE_FINAL,
        "all_revenue_amount",
        "common_revenue_share",
    )
    assert trend.empty
    figure = figures.create_revenue_trend_figure(
        trend, TOTAL_LABEL, "수익(원)", "비중"
    )
    assert not figure.data


# --- 2. 지점별 수익 구성 비교분석 --------------------------------------------
def test_mix_stacks_nine_products_and_the_pension(dataset):
    """상품 아홉 개에 '퇴직'을 더한 열 칸을 쌓는다."""
    assert MIX_TYPES == (*REVENUE_PRODUCT_TYPES, REVENUE_PENSION)
    assert len(MIX_TYPES) == 10
    # 소계와 합계는 쌓지 않는다. 함께 쌓으면 같은 금액을 두 번 센다.
    assert REVENUE_RETAIL not in MIX_TYPES
    assert REVENUE_FINAL not in MIX_TYPES

    figure = draw("mix", dataset)
    assert [trace.name for trace in figure.data] == list(MIX_TYPES)
    assert figure.layout.barmode == "stack"
    assert list(figure.layout.yaxis.range) == [0, 100]


def test_mix_has_the_total_first_then_three_branch_slots(dataset):
    chart = CHARTS["mix"]
    assert len(chart.selects) == MIX_SLOTS
    figure = draw("mix", dataset)
    names = dataset.branch_names
    assert list(figure.layout.xaxis.ticktext) == [
        TOTAL_LABEL,
        names[0],
        names[1],
        names[2],
    ]
    # 자리는 순서로 잡혀 있어야 같은 지점을 두 칸에 골라도 합쳐지지 않는다.
    assert list(figure.data[0].x) == [0, 1, 2, 3]


def test_mix_keeps_a_bar_per_slot_even_if_a_branch_repeats(dataset):
    same = dataset.branch_names[0]
    figure = draw("mix", dataset, branch1=same, branch2=same, branch3=same)
    assert list(figure.data[0].x) == [0, 1, 2, 3]
    values = list(figure.data[0].y)
    assert values[1] == values[2] == values[3]


def test_mix_uses_the_source_share_as_given(dataset):
    """막대 높이는 원본 비중 그대로다."""
    month = reference_month(dataset)
    figure = draw("mix", dataset)
    branch = dataset.branch_names[0]
    rows = dataset.revenue
    picked = rows[
        (rows["branch_name"] == branch) & (rows["base_month"] == month)
    ].set_index("revenue_type")
    for index, revenue_type in enumerate(MIX_TYPES):
        # 자리 1이 첫 비교 지점이다.
        assert figure.data[index].y[1] == pytest.approx(
            picked.loc[revenue_type, "revenue_share"]
        )


def test_mix_has_a_colour_for_every_stack():
    assert len(MIX_TYPES) <= len(figures.MIX_COLORS)
    used = figures.MIX_COLORS[: len(MIX_TYPES)]
    assert len(set(used)) == len(used)


def test_mix_slot_values_cover_every_branch(dataset):
    """정적 HTML이 갈아 끼울 값이 지점마다 준비돼 있다."""
    assert CHARTS["mix"].variants == VARIANTS_SLOT
    slots = CHARTS["mix"].slot_values(dataset)
    assert sorted(slots) == [
        f"branch{index + 1}" for index in range(MIX_SLOTS)
    ]
    values = slots["branch1"]
    assert sorted(values) == sorted(dataset.branch_names)
    first = values[dataset.branch_names[0]]
    assert len(first["y"]) == len(MIX_TYPES)
    assert len(first["text"]) == len(MIX_TYPES)


def test_mix_does_not_precompute_every_combination(dataset):
    """칸이 셋이라 조합을 다 담으면 지점 수의 세제곱이 된다."""
    assert CHARTS["mix"].combinations(dataset) == []


# --- 3·4. 산점도 -------------------------------------------------------------
def test_amount_scatter_uses_the_common_final_revenue(dataset):
    """가로축은 공통고객 '최종' 수익이다. 원본은 원, 축은 억원이다."""
    month = reference_month(dataset)
    figure = draw("amount", dataset)
    point = figure.data[0]

    rows = _final_rows(dataset, month).set_index("branch_name")
    for name, value in zip(point.text, point.x):
        assert value == pytest.approx(
            rows.loc[name, "revenue_amount"] / CHART_AMOUNT_DIVISOR
        )
    assert CHART_AMOUNT_UNIT in figure.layout.xaxis.title.text


def test_share_scatter_uses_the_common_share(dataset):
    """가로축은 공통고객 수익 점유율(%)이다."""
    month = reference_month(dataset)
    figure = draw("share", dataset)
    point = figure.data[0]

    rows = _final_rows(dataset, month).set_index("branch_name")
    for name, value in zip(point.text, point.x):
        assert value == pytest.approx(
            rows.loc[name, "common_revenue_share"]
        )
    assert figure.layout.xaxis.ticksuffix == "%"


def test_scatter_growth_is_year_over_year(dataset):
    """세로축은 전년 동월 대비 증가율이다."""
    current = reference_month(dataset)
    base = shift_month(current, -YOY_MONTHS)
    figure = draw("amount", dataset)
    point = figure.data[0]

    now = _final_rows(dataset, current).set_index("branch_name")
    past = _final_rows(dataset, base).set_index("branch_name")
    for name, growth in zip(point.text, point.y):
        expected = (
            now.loc[name, "revenue_amount"]
            / past.loc[name, "revenue_amount"]
            - 1
        ) * 100
        assert growth == pytest.approx(expected)
    assert figure.layout.yaxis.ticksuffix == "%"


def test_scatter_skips_branches_without_a_comparison_month(dataset):
    """견줄 달이 없으면 0%로 채우지 않고 그 지점을 뺀다."""
    current = reference_month(dataset)
    trimmed = dataset.revenue[dataset.revenue["base_month"] == current]
    scatter = metrics_growth(trimmed, current)
    assert scatter.empty


def metrics_growth(frame, current):
    from dashboard.metrics import growth_scatter

    return growth_scatter(
        frame,
        "revenue_amount",
        current,
        shift_month(current, -YOY_MONTHS),
        {"revenue_type": REVENUE_FINAL},
    )


def test_scatter_panels_can_be_zoomed():
    for key in ("amount", "share"):
        assert CHARTS[key].zoomable, key
        assert CHARTS[key].note


def test_mix_legend_is_split_into_fixed_columns(dataset):
    """범례 칸 수를 Plotly에 맡기면 긴 이름이 오른쪽으로 밀려 잘린다.

    차트 폭의 분수로 칸을 끊으면 화면 폭과 무관하게 칸 수가 고정되고
    범례 전체 폭이 차트 폭을 넘지 않는다.
    """
    from dashboard.tabs.profit.figures import MIX_LEGEND_COLUMNS

    legend = draw("mix", dataset).layout.legend
    assert legend.orientation == "h"
    assert legend.entrywidthmode == "fraction"
    assert legend.entrywidth == pytest.approx(1 / MIX_LEGEND_COLUMNS)
    # 이름이 가장 긴 칸이 한 칸 안에 들어갈 만큼은 끊어야 한다.
    assert MIX_LEGEND_COLUMNS <= 4
    # 안내 문구는 그대로 남는다.
    assert legend.title.text


def test_mix_legend_setting_does_not_leak_to_other_tabs(dataset):
    """자산 구성 범례는 칸이 여섯이라 그대로 둔다."""
    from dashboard.tabs import asset

    chart = {c.key: c for c in asset.TAB.charts}["mix"]
    legend = chart.build(dataset, chart.defaults(dataset)).layout.legend
    assert legend.entrywidthmode is None
    assert legend.entrywidth is None


# --- 지점별 표 --------------------------------------------------------------
def test_table_has_the_declared_columns_in_order(dataset):
    """금액·증가율이 분류마다 짝을 이루고 그 뒤에 비중이 온다."""
    from dashboard.tabs.profit import (
        TABLE_COLUMNS,
        TABLE_FIELDS,
        TABLE_TYPES,
    )

    headers = [column.header for column in TABLE_COLUMNS]
    # 헤더는 원본 컬럼 이름을 그대로 적는다. 표에서 본 값이 원본의 어느
    # 컬럼인지 바로 찾을 수 있어야 한다(회귀 방지).
    assert headers[0] == "지점명"
    assert headers[1:5] == [
        "수익_공통_최종",
        "수익_공통_최종 증가율(YoY)",
        "수익_공통_리테일",
        "수익_공통_리테일 증가율(YoY)",
    ]
    assert headers[-3:] == [
        "수익_공통_펀드_비중",
        "수익_공통_채권_비중",
        "수익_공통_CMA발행어음RP_비중",
    ]
    # 분류 11개 × (금액, 증가율) + 비중 10개 + 지점명.
    assert len(TABLE_TYPES) == 11
    assert len(TABLE_COLUMNS) == 1 + len(TABLE_TYPES) * 2 + 10
    # '기타'는 일부러 뺐다. 그래서 비중을 다 더해도 100%가 아니다.
    assert "기타" not in TABLE_TYPES
    assert len(set(TABLE_FIELDS)) == len(TABLE_FIELDS)
    # 필드 이름은 ASCII여야 한다(→ grid._text_expression).
    assert all(field.isascii() for field in TABLE_FIELDS)


def test_table_amounts_come_from_the_source_as_given(dataset):
    """금액은 원 단위 그대로, 분류마다 원본 값을 그대로 옮긴다."""
    from dashboard.tabs.profit import REVENUE_FIELDS, TABLE_TYPES

    month = reference_month(dataset)
    _total, rows = TAB.tables[0].build(dataset, {})
    branch = dataset.branch_names[0]
    row = rows[rows["branch_name"] == branch].iloc[0]

    picked = dataset.revenue[
        (dataset.revenue["branch_name"] == branch)
        & (dataset.revenue["base_month"] == month)
    ].set_index("revenue_type")
    for revenue_type in TABLE_TYPES:
        field = f"revenue_{REVENUE_FIELDS[revenue_type]}"
        assert row[field] == pytest.approx(
            picked.loc[revenue_type, "revenue_amount"]
        ), revenue_type


def test_table_growth_is_year_over_year(dataset):
    current = reference_month(dataset)
    base = shift_month(current, -YOY_MONTHS)
    _total, rows = TAB.tables[0].build(dataset, {})
    branch = dataset.branch_names[0]
    row = rows[rows["branch_name"] == branch].iloc[0]

    now = _final_rows(dataset, current).set_index("branch_name")
    past = _final_rows(dataset, base).set_index("branch_name")
    expected = (
        now.loc[branch, "revenue_amount"]
        / past.loc[branch, "revenue_amount"]
        - 1
    ) * 100
    assert row["revenue_final_growth"] == pytest.approx(expected)


def test_table_shares_are_used_as_given(dataset):
    """비중은 원본 값 그대로다. 금액에서 되계산하지 않는다."""
    month = reference_month(dataset)
    _total, rows = TAB.tables[0].build(dataset, {})
    branch = dataset.branch_names[0]
    row = rows[rows["branch_name"] == branch].iloc[0]

    picked = dataset.revenue[
        (dataset.revenue["branch_name"] == branch)
        & (dataset.revenue["base_month"] == month)
    ].set_index("revenue_type")
    # 분모가 다른 두 비중을 이름으로 갈라 둔다.
    assert row["share_common"] == pytest.approx(
        picked.loc[REVENUE_FINAL, "common_revenue_share"]
    )
    assert row["share_pension"] == pytest.approx(
        picked.loc[REVENUE_PENSION, "revenue_share"]
    )


def test_table_total_row_uses_the_source_total(dataset):
    """전체 행은 지점을 더하지 않고 원본의 '전체' 행을 쓴다."""
    month = reference_month(dataset)
    total, rows = TAB.tables[0].build(dataset, {})
    assert total["branch_name"] == TOTAL_LABEL
    assert TOTAL_LABEL not in set(rows["branch_name"])
    assert len(rows) == len(dataset.branch_names)

    given = _final_rows(dataset, month, total=True).iloc[0]
    assert total["revenue_final"] == pytest.approx(given["revenue_amount"])
    assert total["share_common"] == pytest.approx(
        given["common_revenue_share"]
    )


def test_table_has_no_empty_cells_with_the_sample(dataset):
    """표본에는 모든 분류가 있으므로 빈 칸이 없어야 한다."""
    from dashboard.tabs.profit import TABLE_FIELDS

    _total, rows = TAB.tables[0].build(dataset, {})
    assert not rows[list(TABLE_FIELDS)].isna().to_numpy().any()


def test_table_is_empty_without_the_source():
    """수익1이 없으면 표가 비고 화면은 안내 문구만 남긴다."""
    from dashboard.tabs.profit import TABLE_FIELDS

    empty = pd.DataFrame()
    total, rows = metrics.branch_table(
        empty, empty, (), (), TABLE_FIELDS, "2026-07", "2025-07", TOTAL_LABEL
    )
    assert total == {}
    assert rows.empty
    assert list(rows.columns) == list(TABLE_FIELDS)
