# Blackbaud Fundraising Intelligence

A BBCon 2026 demo: **Blackbaud CRM is the System of Record, Databricks is the
System of Intelligence.** It reads live fundraising data from Blackbaud CRM (via
Lakehouse Federation) and turns it into an executive campaign view — forecasts,
concentration risk, goal attainment, and the specific prospects and opportunities
to act on next.

The demo answers three questions a fundraising executive owns:

1. **Are we on track to our goal?** → forecast, gap, probability of goal
2. **What could stop us?** → gift-concentration and pipeline risk
3. **What should we do next?** → ranked prospects with a suggested ask, forecast confidence bands

## Quickstart

**Prerequisites**

- A Lakehouse Federation connection to the Blackbaud SQL Server, surfaced as a
  foreign catalog (default `blackbaud_nxt_test`), with credentials in the
  `blackbaud` secret scope (`bb_user`, `bb_password`).
- A serverless-enabled workspace. The default target is `adb-7405614847929963`;
  change `workspace.host` in `databricks.yml` for your own.

**Run it** (from this directory)

```sh
# 1. Deploy the bundle (builds the wheel, uploads notebooks + jobs)
databricks bundle deploy -p fe-vm-blackbaud-demo-bbcon

# 2. Build the analytics views from live Blackbaud data
databricks bundle run build_gold_views_serverless -p fe-vm-blackbaud-demo-bbcon

# 3. Run the decision-science layer (prospect scoring + Monte Carlo forecast)
databricks bundle run decision_science_serverless -p fe-vm-blackbaud-demo-bbcon
```

Point it at a different catalog/schema without editing code:
`--var gold_catalog=my_catalog --var gold_schema=my_schema`.

Then open the dashboard (see [Dashboard](#dashboard)).

## What it builds

Three layers of views in `<gold_catalog>.<gold_schema>`, all read live from the
federated Blackbaud database. Each layer builds on the one above it.

**1. Foundation** — the enriched grain everything else reads

| View | Purpose |
| --- | --- |
| `stage_weight` | Stage → win-probability seed (the only tunable config, not CRM data) |
| `opp_enriched` | One row per opportunity ⋈ prospect ⋈ fundraiser ⋈ stage weight |

**2. Analytics** — descriptive: where the campaign stands

| View | Answers |
| --- | --- |
| `pipeline_forecast` | Total ask, weighted forecast, open pipeline, committed |
| `pipeline_by_stage` | Pipeline totals per opportunity stage |
| `pipeline_risk` | Gift concentration (top-10 share of open pipeline) + missing close dates |
| `fundraiser_portfolio` | Pipeline and weighted forecast per fundraiser |
| `designation_attainment` | Goal vs. raised vs. gap and % to goal, by designation |
| `campaign_goals` | Campaign goal amounts with start/end dates |
| `exec_summary` | One-row rollup: goal, raised, forecast, gap, probability of goal |
| `scenario_forecast` | Forecast under five fixed what-if scenarios |

**3. Decision science** — prescriptive: what to do next
(built by the `decision_science` notebook, in `src/blackbaud_intel/`)

| Output | Method | What it gives you |
| --- | --- | --- |
| `prospect_next_best_ask` (view) | RFM quintile scoring over gift history | Ranked prospects with a suggested ask amount |
| `montecarlo_forecast` (table) | Monte Carlo simulation of the open pipeline | P10 / P50 / P90 forecast band + probability of goal |

## Dashboard

`dashboards/campaign_executive_dashboard.lvdash.json` is the exported two-page
Lakeview dashboard that reads these views:

- **Campaign Executive View** — the descriptive story (KPIs, scenarios, attainment)
- **Actionable Insights** — the prescriptive story (forecast band, prospects to solicit)

Recreate it in a workspace:

```sh
databricks api post /api/2.0/lakeview/dashboards -p <profile> --json '{
  "display_name": "Blackbaud Campaign Executive Dashboard",
  "warehouse_id": "<warehouse_id>",
  "parent_path": "/Users/<you>",
  "serialized_dashboard": "<contents of the .lvdash.json, as a JSON string>"
}'
```

## Project map

```
databricks.yml                     bundle config, targets, variables
src/blackbaud_intel/
  views.py                         gold-view SQL, grouped by domain
  montecarlo.py                    pure-Python forecast simulation (unit-tested)
notebooks/
  build_gold_views.py              runs views.py against the warehouse
  decision_science.py              RFM prospects + Monte Carlo forecast
resources/jobs/                    one serverless job per notebook
tests/unit/                        tests for the SQL builders and simulation
dashboards/                        exported Lakeview dashboard
```

Structure follows the reusable-IP `projects/dabs/repo_template`: SQL and logic
live in importable modules under `src/`, notebooks stay thin, and everything ships
in a wheel. Run `uv run --group dev pytest` for the unit tests (no cluster needed).

## Scope notes (honest limits of the sample data)

- **Win probabilities are a fixed lookup, not a learned model.** `stage_weight`
  assigns each stage a conversion odds; the forecast is arithmetic on top. A real
  engagement would learn these rates from the customer's own history.
- **Pipeline can't be split by designation** — the `OPPORTUNITYDESIGNATION` link
  table is empty in the sample DB, so `designation_attainment` uses *realized*
  revenue (`REVENUESPLIT`), not open pipeline.
- The numbers reflect an early-campaign sample dataset, so attainment and
  probability-of-goal read low. The methods, not the figures, are the point.
