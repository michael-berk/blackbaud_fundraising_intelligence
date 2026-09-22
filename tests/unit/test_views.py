import pytest

from blackbaud_intel.views import (
    STAGE_WEIGHTS,
    build_scenario_statement,
    build_view_statements,
)

SOURCE = "blackbaud_nxt_test"
GOLD_CATALOG = "blackbaud_demo_bbcon"
GOLD_SCHEMA = "default"

EXPECTED_VIEWS = [
    "stage_weight",
    "opp_enriched",
    "pipeline_forecast",
    "pipeline_by_stage",
    "pipeline_risk",
    "fundraiser_portfolio",
    "designation_attainment",
    "campaign_goals",
    "designation_performance",
    "exec_summary",
    "scenario_forecast",
    "prospect_next_best_ask",
]


@pytest.fixture
def statements():
    return build_view_statements(SOURCE, GOLD_CATALOG, GOLD_SCHEMA)


def test_one_statement_per_expected_view(statements):
    assert len(statements) == len(EXPECTED_VIEWS)


@pytest.mark.parametrize("view_name", EXPECTED_VIEWS)
def test_each_view_is_created(statements, view_name):
    fqn = f"{GOLD_CATALOG}.{GOLD_SCHEMA}.{view_name}"
    assert any(f"CREATE OR REPLACE VIEW {fqn} AS" in s for s in statements)


def test_designation_goal_uses_max_not_sum(statements):
    # A designation can have several nested goal levels; summing double-counts,
    # so the top-level goal must be taken as MAX(GOAL).
    attainment_sql = next(s for s in statements if "designation_attainment AS" in s)
    assert "MAX(GOAL)" in attainment_sql
    assert "SUM(GOAL)" not in attainment_sql


def test_pipeline_risk_guards_zero_open_pipeline(statements):
    risk_sql = next(s for s in statements if "pipeline_risk AS" in s)
    assert "NULLIF(MAX(total_open), 0)" in risk_sql


def test_source_catalog_is_interpolated(statements):
    joined = "\n".join(statements)
    assert f"{SOURCE}.dbo.OPPORTUNITY" in joined
    assert f"{SOURCE}.dbo.REVENUESPLIT" in joined
    assert f"{SOURCE}.dbo.DESIGNATIONGOAL" in joined


def test_stage_weights_are_all_present_in_seed(statements):
    stage_weight_sql = next(s for s in statements if "stage_weight AS" in s)
    for stage, weight in STAGE_WEIGHTS.items():
        assert f"('{stage}', {weight})" in stage_weight_sql


@pytest.mark.parametrize(
    ("uplift", "should_cap"),
    [
        (0.10, True),
        (0.0, True),
        (0.5, True),
    ],
)
def test_scenario_statement_caps_probability(uplift, should_cap):
    sql = build_scenario_statement(GOLD_CATALOG, GOLD_SCHEMA, uplift)
    assert f"win_probability + {uplift}" in sql
    assert should_cap == ("LEAST(" in sql)
    assert f"{GOLD_CATALOG}.{GOLD_SCHEMA}.opp_enriched" in sql
