"""
Databricks SQL warehouse client.
Handles connection via M2M OAuth (Databricks Apps runtime) or
PAT from environment variables / ~/.databrickscfg (local dev).
"""

import os
import logging
from typing import Any, List, Dict, Optional

from databricks import sql as dbsql
from databricks.sdk import WorkspaceClient
from databricks.sdk.config import Config

logger = logging.getLogger(__name__)

CATALOG      = os.getenv("CATALOG", "danonedemo_catalog")
SCHEMA       = os.getenv("SCHEMA", "marketing")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "50e0bc7f9918a201")
AI_ENDPOINT  = os.getenv("AI_ENDPOINT_NAME", "danone-gpt5")


def _get_host_and_token() -> tuple[str, str]:
    host  = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    token = os.getenv("DATABRICKS_TOKEN", "") or os.getenv("DATABRICKS_PAT", "")

    # Fall back to ~/.databrickscfg DEFAULT profile for local development
    if not host or not token:
        try:
            cfg = Config()
            host  = host  or cfg.host or ""
            token = token or cfg.token or ""
        except Exception:
            pass

    if not host:
        host = "https://fevm-danonedemo.cloud.databricks.com"

    return host, token


def get_workspace_client() -> WorkspaceClient:
    host, token = _get_host_and_token()
    return WorkspaceClient(host=host, token=token)


def execute_query(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Run a SQL query against the SQL warehouse and return rows as dicts."""
    host, token = _get_host_and_token()
    server_hostname = host.replace("https://", "").replace("http://", "")

    with dbsql.connect(
        server_hostname=server_hostname,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        access_token=token,
        catalog=CATALOG,
        schema=SCHEMA,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, parameters=params)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]


def execute_ai_query(prompt: str) -> str:
    """Run a one-off ai_query() call via SQL warehouse for ad-hoc report generation."""
    safe_prompt = prompt.replace("'", "''")
    sql = f"SELECT ai_query('{AI_ENDPOINT}', '{safe_prompt}') AS result"
    rows = execute_query(sql)
    return rows[0]["result"] if rows else ""
