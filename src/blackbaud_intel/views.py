"""Gold-view definitions for the Blackbaud fundraising-intelligence demo.

The source is a read-only Blackbaud CRM (SQL Server), exposed through a Lakehouse
Federation foreign catalog. Credentials live in a Databricks secret scope and are
resolved by the federation connection, so no credentials appear here.

Views are defined as Python so they are importable, lintable and shipped in the
whl (see the project README for why config lives in Python, not YAML).
"""

STAGE_WEIGHTS = {
    "Qualified": 0.25,
    "Response pending": 0.50,
    "Accepted": 1.00,
    "Rejected": 0.00,
    "Unqualified": 0.00,
    "Canceled": 0.00,
}


def _stage_weight_values() -> str:
    rows = ",\n  ".join(f"('{stage}', {weight})" for stage, weight in STAGE_WEIGHTS.items())
    return rows


def build_view_statements(source_catalog: str, gold_catalog: str, gold_schema: str) -> list[str]:
    """Return the ordered CREATE VIEW statements for the demo.

    Args:
        source_catalog: Federated foreign catalog mirroring the Blackbaud database.
        gold_catalog: Unity Catalog catalog that will hold the gold views.
        gold_schema: Schema within ``gold_catalog`` for the views.
    """
    src = source_catalog
    gold = f"{gold_catalog}.{gold_schema}"

    return [
        f"""
        CREATE OR REPLACE VIEW {gold}.stage_weight AS
        SELECT * FROM VALUES
          {_stage_weight_values()}
        AS t(status, win_probability)
        """,
        f"""
        CREATE OR REPLACE VIEW {gold}.opp_enriched AS
        SELECT
          o.ID                            AS opportunity_id,
          o.STATUS                        AS stage,
          o.ASKAMOUNT                     AS ask_amount,
          o.EXPECTEDASKDATE               AS expected_ask_date,
          o.ASKDATE                       AS ask_date,
          w.win_probability,
          o.ASKAMOUNT * w.win_probability AS weighted_amount,
          pp.ID                           AS prospect_plan_id,
          pc.DISPLAYNAME                  AS prospect_name,
          fc.ID                           AS fundraiser_id,
          fc.DISPLAYNAME                  AS fundraiser_name
        FROM {src}.dbo.OPPORTUNITY o
        JOIN {src}.dbo.PROSPECTPLAN pp ON o.PROSPECTPLANID = pp.ID
        LEFT JOIN {src}.dbo.PROSPECT    pr ON pp.PROSPECTID = pr.ID
        LEFT JOIN {src}.dbo.CONSTITUENT pc ON pr.ID = pc.ID
        LEFT JOIN {src}.dbo.CONSTITUENT fc ON pp.PRIMARYMANAGERFUNDRAISERID = fc.ID
        LEFT JOIN {gold}.stage_weight    w ON o.STATUS = w.status
        """,
        f"""
        CREATE OR REPLACE VIEW {gold}.pipeline_forecast AS
        SELECT
          COUNT(*)                                                        AS n_opportunities,
          ROUND(SUM(ask_amount), 0)                                       AS total_ask,
          ROUND(SUM(weighted_amount), 0)                                  AS weighted_forecast,
          ROUND(SUM(CASE WHEN win_probability BETWEEN 0.01 AND 0.99
                         THEN ask_amount END), 0)                         AS open_pipeline,
          ROUND(SUM(CASE WHEN stage = 'Accepted' THEN ask_amount END), 0) AS committed
        FROM {gold}.opp_enriched
        """,
        f"""
        CREATE OR REPLACE VIEW {gold}.pipeline_by_stage AS
        SELECT stage,
               COUNT(*)                       AS n,
               ROUND(SUM(ask_amount), 0)      AS total_ask,
               ROUND(SUM(weighted_amount), 0) AS weighted
        FROM {gold}.opp_enriched
        GROUP BY stage
        ORDER BY weighted DESC
        """,
        f"""
        CREATE OR REPLACE VIEW {gold}.pipeline_risk AS
        WITH open_opps AS (
          SELECT * FROM {gold}.opp_enriched WHERE win_probability BETWEEN 0.01 AND 0.99
        ),
        ranked AS (
          SELECT ask_amount,
                 SUM(ask_amount) OVER () AS total_open,
                 ROW_NUMBER() OVER (ORDER BY ask_amount DESC) AS rnk
          FROM open_opps
        )
        SELECT
          ROUND(SUM(CASE WHEN rnk <= 10 THEN ask_amount END) / MAX(total_open) * 100, 1)
                                                              AS top10_pct_of_open,
          (SELECT COUNT(*) FROM open_opps WHERE expected_ask_date IS NULL)
                                                              AS open_opps_missing_ask_date,
          (SELECT COUNT(*) FROM open_opps)                    AS n_open_opps
        FROM ranked
        """,
        f"""
        CREATE OR REPLACE VIEW {gold}.fundraiser_portfolio AS
        SELECT
          fundraiser_name,
          COUNT(*)                       AS n_opps,
          ROUND(SUM(ask_amount), 0)      AS total_ask,
          ROUND(SUM(weighted_amount), 0) AS weighted_forecast
        FROM {gold}.opp_enriched
        WHERE fundraiser_name IS NOT NULL
        GROUP BY fundraiser_name
        ORDER BY weighted_forecast DESC
        """,
        f"""
        CREATE OR REPLACE VIEW {gold}.designation_attainment AS
        WITH goal AS (
          SELECT DESIGNATIONID, SUM(GOAL) AS goal_amount
          FROM {src}.dbo.DESIGNATIONGOAL
          GROUP BY DESIGNATIONID
        ),
        raised AS (
          SELECT DESIGNATIONID, SUM(AMOUNT) AS raised_amount
          FROM {src}.dbo.REVENUESPLIT
          GROUP BY DESIGNATIONID
        )
        SELECT
          d.NAME                                                   AS designation_name,
          ROUND(g.goal_amount, 0)                                  AS goal_amount,
          ROUND(COALESCE(r.raised_amount, 0), 0)                   AS raised_amount,
          ROUND(g.goal_amount - COALESCE(r.raised_amount, 0), 0)   AS gap_amount,
          ROUND(COALESCE(r.raised_amount, 0) / g.goal_amount * 100, 1) AS pct_to_goal
        FROM {src}.dbo.DESIGNATION d
        JOIN goal g ON d.ID = g.DESIGNATIONID
        LEFT JOIN raised r ON d.ID = r.DESIGNATIONID
        WHERE g.goal_amount > 0
        ORDER BY raised_amount DESC
        """,
        f"""
        CREATE OR REPLACE VIEW {gold}.campaign_goals AS
        SELECT
          c.NAME                    AS campaign_name,
          c.STARTDATE               AS start_date,
          c.ENDDATE                 AS end_date,
          ROUND(SUM(hg.AMOUNT), 0)  AS goal_amount
        FROM {src}.dbo.CAMPAIGN c
        LEFT JOIN {src}.dbo.CAMPAIGNHIERARCHYGOAL hg ON c.ID = hg.CAMPAIGNID
        GROUP BY c.NAME, c.STARTDATE, c.ENDDATE
        ORDER BY goal_amount DESC NULLS LAST
        """,
    ]


def build_scenario_statement(
    gold_catalog: str, gold_schema: str, response_pending_uplift: float
) -> str:
    """Return the executive what-if scenario query (Output 5).

    Recomputes the weighted forecast after raising the win probability of
    ``Response pending`` opportunities by ``response_pending_uplift`` (capped at 1.0),
    holding all other stages fixed. Returned as a query, not a view, because the
    uplift is a caller-supplied parameter rather than stored state.

    Args:
        gold_catalog: Catalog holding the gold views.
        gold_schema: Schema holding the gold views.
        response_pending_uplift: Absolute uplift to win probability (e.g. 0.10 = +10pts).
    """
    gold = f"{gold_catalog}.{gold_schema}"
    return f"""
    SELECT
      ROUND(SUM(weighted_amount), 0)                                       AS base_forecast,
      ROUND(SUM(CASE WHEN stage = 'Response pending'
                     THEN ask_amount * LEAST(win_probability + {response_pending_uplift}, 1.0)
                     ELSE weighted_amount END), 0)                         AS scenario_forecast
    FROM {gold}.opp_enriched
    """
