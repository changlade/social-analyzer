# Databricks notebook source
# MAGIC %md
# MAGIC # Danone Social Analyzer — One-Time Setup
# MAGIC
# MAGIC This notebook:
# MAGIC 1. Creates the `marketing` schema in `danonedemo_catalog`
# MAGIC 2. Creates the `social_landing` volume for scraping data
# MAGIC 3. Creates the required sub-directories in the volume
# MAGIC 4. Verifies that `ai_query('databricks-gpt-5-4', ...)` works (native endpoint)
# MAGIC 5. Creates a secret scope and stores the workspace PAT for the exploration app

# COMMAND ----------

def _get(key, default):
    try:
        val = dbutils.widgets.get(key)
        return val if val else default
    except Exception:
        return default

CATALOG      = _get("CATALOG", "danonedemo_catalog")
SCHEMA       = _get("SCHEMA", "marketing")
VOLUME_NAME  = _get("VOLUME_NAME", "social_landing")
WAREHOUSE_ID = _get("WAREHOUSE_ID", "50e0bc7f9918a201")
AI_ENDPOINT_NAME = _get("AI_ENDPOINT_NAME", "databricks-gpt-5-4")

print(f"Setup: {CATALOG}.{SCHEMA}, volume={VOLUME_NAME}, ai_endpoint={AI_ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md ## 1. Create Schema

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}` COMMENT 'Danone Social Impact Analyzer'")
print(f"Schema {CATALOG}.{SCHEMA} ready")

# COMMAND ----------

# MAGIC %md ## 2. Create Volume and sub-directories

# COMMAND ----------

spark.sql(f"""
CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.`{VOLUME_NAME}`
COMMENT 'Landing zone for raw scraping outputs'
""")

volume_root = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME_NAME}"
for subdir in ["raw_scrapes", "raw_rss", "checkpoints"]:
    dbutils.fs.mkdirs(f"{volume_root}/{subdir}")
    print(f"  OK: {volume_root}/{subdir}")

print("Volume ready")

# COMMAND ----------

# MAGIC %md ## 3. Verify native AI endpoint

# COMMAND ----------

try:
    result = spark.sql(f"""
    SELECT ai_query('{AI_ENDPOINT_NAME}', 'Reply with exactly: SETUP_OK') AS r
    """).collect()[0]["r"]
    print(f"ai_query OK: {result}")
except Exception as e:
    print(f"Warning: ai_query test failed ({e}). The endpoint may need a moment to warm up.")

# COMMAND ----------

# MAGIC %md ## 4. Create Secret Scope for App

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

try:
    token = (
        dbutils.notebook.entry_point.getDbutils()
        .notebook()
        .getContext()
        .apiToken()
        .get()
    )
except Exception:
    import os
    token = os.environ.get("DATABRICKS_TOKEN", "")

try:
    host = spark.conf.get("spark.databricks.workspaceUrl", "fevm-danonedemo.cloud.databricks.com")
    w.secrets.create_scope(scope="social-analyzer-secrets")
    print("Secret scope created")
except Exception as e:
    if "already exists" in str(e).lower():
        print("Secret scope already exists")
    else:
        print(f"Warning: {e}")

for key, val in [
    ("databricks-host", f"https://fevm-danonedemo.cloud.databricks.com"),
    ("databricks-pat",  token),
]:
    try:
        w.secrets.put_secret(scope="social-analyzer-secrets", key=key, string_value=val)
        print(f"  Stored secret: {key}")
    except Exception as e:
        print(f"  Warning ({key}): {e}")

# COMMAND ----------

print("Setup complete! Schema, volume, and secrets are ready.")
print(f"  ai_query endpoint: {AI_ENDPOINT_NAME}")
print("  Next: run the scraper job, then the DLT pipeline will trigger automatically.")
