# Databricks notebook source
# MAGIC %md
# MAGIC # Decision science: next-best-ask + Monte Carlo forecast
# MAGIC Moves from descriptive stats to prescriptive action:
# MAGIC - **Next-best-ask** (method #2): RFM-scored prospects with a suggested ask.
# MAGIC - **Monte Carlo forecast** (method #4): P10/P50/P90 range and probability of goal.

# COMMAND ----------

from blackbaud_intel.montecarlo import simulate

# COMMAND ----------

dbutils.widgets.text("gold_catalog", "blackbaud_demo_bbcon", "Gold catalog")
dbutils.widgets.text("gold_schema", "default", "Gold schema")
dbutils.widgets.text("n_trials", "10000", "Monte Carlo trials")

gold_catalog = dbutils.widgets.get("gold_catalog")
gold_schema = dbutils.widgets.get("gold_schema")
n_trials = int(dbutils.widgets.get("n_trials"))
gold = f"{gold_catalog}.{gold_schema}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Method #2 — Top prospects to solicit next (RFM + next-best-ask)

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {gold}.prospect_next_best_ask LIMIT 50"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Method #4 — Monte Carlo campaign forecast with confidence bands

# COMMAND ----------

open_opps = spark.sql(f"""
    SELECT ask_amount, win_probability
    FROM {gold}.opp_enriched
    WHERE win_probability > 0 AND win_probability < 1
""").toPandas()

summary = spark.sql(f"SELECT raised, goal FROM {gold}.exec_summary").toPandas().iloc[0]

distribution = simulate(
    open_asks=open_opps["ask_amount"].tolist(),
    open_probabilities=open_opps["win_probability"].tolist(),
    committed=float(summary["raised"]),
    goal=float(summary["goal"]),
    n_trials=n_trials,
)
print(distribution)

# COMMAND ----------

# Persist the distribution as a managed table so the dashboard can read it.
spark.createDataFrame(
    [(
        distribution.committed,
        distribution.p10,
        distribution.p50,
        distribution.p90,
        distribution.mean,
        distribution.probability_of_goal,
    )],
    ["committed", "p10", "p50", "p90", "mean", "probability_of_goal"],
).write.mode("overwrite").saveAsTable(f"{gold}.montecarlo_forecast")

display(spark.table(f"{gold}.montecarlo_forecast"))
