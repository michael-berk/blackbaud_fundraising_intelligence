---
name: deploy-refresh
description: Deploy the Blackbaud fundraising-intelligence DABs bundle and refresh all analytics against the current Blackbaud data — rebuild the gold views, then run the decision-science layer (RFM next-best-ask + Monte Carlo forecast). Use when asked to deploy, refresh, rebuild, or re-run this project against new/updated Blackbaud data.
allowed-tools: Bash, Read
argument-hint: "[optional: note on what changed]"
---

# Deploy & refresh Blackbaud fundraising intelligence

Refreshing: $ARGUMENTS

Deploys the bundle and rebuilds every gold view + decision-science output from the
**live federated Blackbaud data**. Run this after Blackbaud loads new data, or after
changing `src/blackbaud_intel/views.py` / the notebooks.

Profile: `fe-vm-blackbaud-demo-bbcon` · Warehouse: `094bda4b4eaaf6b9` ·
Gold: `blackbaud_demo_bbcon.default`

## Steps

1. **Verify auth.** The workspace OAuth token expires often. Check it first:
   ```bash
   databricks current-user me -p fe-vm-blackbaud-demo-bbcon -o json
   ```
   If it fails with an invalid-refresh-token error, STOP and tell the user to run
   `databricks auth login --profile fe-vm-blackbaud-demo-bbcon` (interactive browser
   login — you cannot do it for them). Continue once it returns a username.

2. **Start the warehouse** (serverless cold-start is ~1–2 min; do this early so it's
   warm by the time queries run):
   ```bash
   databricks warehouses start 094bda4b4eaaf6b9 -p fe-vm-blackbaud-demo-bbcon
   ```

3. **Deploy the bundle** from the repo root (builds the wheel, uploads notebooks + jobs):
   ```bash
   databricks bundle deploy -p fe-vm-blackbaud-demo-bbcon
   ```

4. **Run the two jobs IN ORDER** — `build_gold_views` must finish before
   `decision_science`, because the Monte Carlo step reads `exec_summary` (a gold view).
   Run each in the background and poll to `TERMINATED`; on new/large data a run can take
   several minutes.
   ```bash
   databricks bundle run build_gold_views_serverless -p fe-vm-blackbaud-demo-bbcon
   # wait for TERMINATED SUCCESS, then:
   databricks bundle run decision_science_serverless -p fe-vm-blackbaud-demo-bbcon
   ```

5. **Verify** the refresh produced real numbers:
   ```bash
   databricks api post /api/2.0/sql/statements -p fe-vm-blackbaud-demo-bbcon \
     --json '{"warehouse_id":"094bda4b4eaaf6b9","statement":"SELECT * FROM blackbaud_demo_bbcon.default.exec_summary","wait_timeout":"50s"}'
   ```
   Also spot-check `montecarlo_forecast` and `prospect_next_best_ask`.

## Notes

- If a query fails with `FAILED_JDBC.CONNECTION` (a TCP-level "failed to connect",
  not a login error), the Blackbaud firewall is dropping our serverless egress —
  this is a Blackbaud-side whitelist issue, not something a redeploy fixes. The
  workspace egresses from the **Azure East US** serverless IP pool (confirmed via the
  workspace CNAME `eastus-c3.azuredatabricks.net`). Hand Blackbaud the East US
  outbound CIDRs from `https://www.databricks.com/networking/v1/ip-ranges.json`
  (`azure`/`eastus`/`outbound`) or the `AzureDatabricksServerless.EastUS` service tag.
- The dashboard reads the views live, so it reflects the refresh automatically — no
  dashboard redeploy needed unless you changed its layout.
- Credentials live in the `blackbaud` secret scope (`bb_user`, `bb_password`); never
  print or inline them.
