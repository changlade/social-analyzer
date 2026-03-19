# Databricks notebook source
# MAGIC %md
# MAGIC # Danone Social Analyzer — One-Time Setup
# MAGIC
# MAGIC This notebook:
# MAGIC 1. Creates the `marketing` schema in `danonedemo_catalog`
# MAGIC 2. Creates the `social_landing` volume for scraping data
# MAGIC 3. Creates the required sub-directories in the volume
# MAGIC 4. Registers the GPT 5.4 AI Gateway as an External Model endpoint (`danone-gpt5`)
# MAGIC    so that `ai_query('danone-gpt5', ...)` works in SQL / DLT pipelines
# MAGIC 5. Creates a secret scope for the exploration app

# COMMAND ----------

# MAGIC %pip install databricks-sdk>=0.40.0 --quiet

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# Parameters injected by the setup job (or run manually)
CATALOG         = dbutils.widgets.get("CATALOG")         if dbutils.widgets.getAll().get("CATALOG") else "danonedemo_catalog"
SCHEMA          = dbutils.widgets.get("SCHEMA")          if dbutils.widgets.getAll().get("SCHEMA") else "marketing"
VOLUME_NAME     = dbutils.widgets.get("VOLUME_NAME")     if dbutils.widgets.getAll().get("VOLUME_NAME") else "social_landing"
WAREHOUSE_ID    = dbutils.widgets.get("WAREHOUSE_ID")    if dbutils.widgets.getAll().get("WAREHOUSE_ID") else "50e0bc7f9918a201"
GPT5_ENDPOINT_URL = dbutils.widgets.get("GPT5_ENDPOINT_URL") if dbutils.widgets.getAll().get("GPT5_ENDPOINT_URL") else "https://7474655187458913.ai-gateway.cloud.databricks.com/mlflow/v1/chat/completions"
AI_ENDPOINT_NAME  = dbutils.widgets.get("AI_ENDPOINT_NAME")  if dbutils.widgets.getAll().get("AI_ENDPOINT_NAME") else "danone-gpt5"

print(f"Setting up: {CATALOG}.{SCHEMA} | volume={VOLUME_NAME} | endpoint={AI_ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md ## 1. Create Schema

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA} COMMENT 'Danone Social Impact Analyzer — marketing-facing tables'")
print(f"Schema {CATALOG}.{SCHEMA} ready")

# COMMAND ----------

# MAGIC %md ## 2. Create Volume

# COMMAND ----------

spark.sql(f"""
CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME_NAME}
COMMENT 'Landing zone for raw scraping outputs from the Danone Social Analyzer pipeline'
""")

volume_root = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME_NAME}"

# Sub-directories used by the scraper and Auto Loader
for subdir in ["raw_scrapes", "raw_rss", "checkpoints"]:
    dbutils.fs.mkdirs(f"{volume_root}/{subdir}")
    print(f"Created: {volume_root}/{subdir}")

# COMMAND ----------

# MAGIC %md ## 3. Register GPT 5.4 as External Model Endpoint

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ExternalModel,
    ExternalModelProvider,
    OpenAiConfig,
    ServedEntityInput,
    EndpointCoreConfigInput,
)

w = WorkspaceClient()

# Retrieve the current workspace host token for proxying requests to the AI gateway
# The gateway endpoint uses Databricks token authentication
import subprocess, json

token = (
    dbutils.notebook.entry_point.getDbutils()
    .notebook()
    .getContext()
    .apiToken()
    .get()
)

# Check if endpoint already exists
existing = [e.name for e in w.serving_endpoints.list()]
if AI_ENDPOINT_NAME in existing:
    print(f"Endpoint '{AI_ENDPOINT_NAME}' already exists — skipping creation")
else:
    endpoint = w.serving_endpoints.create_and_wait(
        name=AI_ENDPOINT_NAME,
        config=EndpointCoreConfigInput(
            served_entities=[
                ServedEntityInput(
                    name="gpt5-gateway",
                    external_model=ExternalModel(
                        name="gpt-4o",          # model name sent in requests
                        provider=ExternalModelProvider.OPENAI,
                        task="llm/v1/chat",
                        openai_config=OpenAiConfig(
                            openai_api_base=GPT5_ENDPOINT_URL.replace("/mlflow/v1/chat/completions", ""),
                            openai_api_key_plaintext=token,
                            openai_api_type="openai",
                            openai_deployment_name="gpt-4o",
                        ),
                    ),
                )
            ]
        ),
    )
    print(f"Endpoint '{AI_ENDPOINT_NAME}' created: {endpoint.state}")

# COMMAND ----------

# MAGIC %md ## 4. Verify ai_query works

# COMMAND ----------

test_result = spark.sql(f"""
SELECT ai_query(
  '{AI_ENDPOINT_NAME}',
  'Reply with exactly: DANONE_SETUP_OK'
) AS test_response
""").collect()[0]["test_response"]

print(f"ai_query test response: {test_result}")
assert "DANONE_SETUP_OK" in str(test_result), "ai_query endpoint test failed — check endpoint configuration"

# COMMAND ----------

# MAGIC %md ## 5. Create Secret Scope for App (if not exists)

# COMMAND ----------

try:
    w.secrets.create_scope(scope="social-analyzer-secrets")
    print("Secret scope 'social-analyzer-secrets' created")
except Exception as e:
    if "already exists" in str(e).lower():
        print("Secret scope already exists — OK")
    else:
        print(f"Warning: {e}")

# Store the current token so the app can connect to the SQL warehouse
try:
    w.secrets.put_secret(
        scope="social-analyzer-secrets",
        key="databricks-pat",
        string_value=token,
    )
    print("PAT stored in secret scope")
except Exception as e:
    print(f"Warning storing PAT: {e}")

# COMMAND ----------

print("""
✅  Setup complete!

Next steps:
  1. Deploy the bundle:  databricks bundle deploy
  2. Run the setup job:  databricks bundle run danone_social_setup
  3. Run the scraper:    databricks bundle run danone_social_scraper
  4. Check the pipeline: Pipelines → [dev] Danone Social Analyzer ETL
  5. Deploy the app:     databricks bundle deploy && check Apps section
""")
