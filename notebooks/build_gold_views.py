# Databricks notebook source
# MAGIC %md
# MAGIC # Build Blackbaud fundraising-intelligence gold views
# MAGIC Blackbaud CRM (System of Record) → Databricks (System of Intelligence). Reads the
# MAGIC federated Blackbaud SQL Server and creates the pipeline-forecast and risk views.

# COMMAND ----------

dbutils.widgets.text("source_catalog", "blackbaud_nxt_test", "Federated Blackbaud catalog")
dbutils.widgets.text("gold_catalog", "blackbaud_demo_bbcon", "Gold catalog")
dbutils.widgets.text("gold_schema", "default", "Gold schema")

source_catalog = dbutils.widgets.get("source_catalog")
gold_catalog = dbutils.widgets.get("gold_catalog")
gold_schema = dbutils.widgets.get("gold_schema")

# COMMAND ----------

from blackbaud_intel.views import build_view_statements

for statement in build_view_statements(source_catalog, gold_catalog, gold_schema):
    spark.sql(statement)

# COMMAND ----------

display(spark.table(f"{gold_catalog}.{gold_schema}.pipeline_forecast"))

# COMMAND ----------

display(spark.table(f"{gold_catalog}.{gold_schema}.pipeline_risk"))

# COMMAND ----------

display(spark.table(f"{gold_catalog}.{gold_schema}.designation_attainment"))

# COMMAND ----------

display(spark.table(f"{gold_catalog}.{gold_schema}.campaign_goals"))
