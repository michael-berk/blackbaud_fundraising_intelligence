# Blackbaud Fundraising Intelligence

A DABs project that turns Blackbaud CRM fundraising data into pipeline forecasts and
gift-concentration risk analysis. Blackbaud CRM is the **System of Record**; Databricks
is the **System of Intelligence**. Built for the BBCon 2026 demo.

Structure follows the reusable-IP `projects/dabs/repo_template` (separate `notebooks`
and `src`, whl-based deployment, Python config over YAML).

## What it builds

Six gold views in `${gold_catalog}.${gold_schema}`, read live from the federated
Blackbaud SQL Server (`source_catalog`):

| View | Purpose |
| --- | --- |
| `stage_weight` | Stage → win-probability seed (the only config input, not CRM data) |
| `opp_enriched` | Opportunity ⋈ prospect ⋈ fundraiser ⋈ stage weight (silver) |
| `pipeline_forecast` | Total ask, weighted forecast, open pipeline, committed |
| `pipeline_by_stage` | Pipeline totals by opportunity stage |
| `pipeline_risk` | Gift concentration (top-10 share of open pipeline) + data-quality gaps |
| `fundraiser_portfolio` | Per-fundraiser pipeline and weighted forecast |
| `designation_attainment` | Goal vs. raised vs. gap and % to goal, by designation |
| `campaign_goals` | Campaign goal amounts with start/end dates |

Scope note: pipeline-to-designation attribution is omitted — the
`OPPORTUNITYDESIGNATION` link table is empty in the source test database, so open
pipeline cannot be split by designation. Realized revenue (`REVENUESPLIT`) is
attributed by designation, which powers `designation_attainment`.

## Prerequisites

- A Lakehouse Federation connection to the Blackbaud SQL Server, surfaced as the
  foreign catalog named in `source_catalog` (default `blackbaud_nxt_test`).
  Credentials live in the `blackbaud` secret scope (`bb_user`, `bb_password`).
- A serverless SQL/compute-enabled workspace (default target
  `adb-7405614847929963`).

## Deploy

1. Handle any `SETUP TODO`s (search the repo).
2. Build + deploy the bundle, then run the job:

```sh
databricks bundle deploy -p fe-vm-blackbaud-demo-bbcon
databricks bundle run build_gold_views_serverless -p fe-vm-blackbaud-demo-bbcon
```

Override a variable at deploy time with `--var`, e.g.
`--var gold_schema=blackbaud_intel`.
