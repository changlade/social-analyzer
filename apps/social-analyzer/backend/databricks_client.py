"""
Databricks SQL warehouse client.
Uses direct REST API calls via httpx for maximum compatibility with
Databricks Apps M2M OAuth tokens (avoids SDK auth layer complexities).
"""

import os
import time
import logging
import httpx
from typing import Any, List, Dict, Optional

logger = logging.getLogger(__name__)

CATALOG      = os.getenv("CATALOG", "danonedemo_catalog")
SCHEMA       = os.getenv("SCHEMA", "marketing")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "50e0bc7f9918a201")
AI_ENDPOINT  = os.getenv("AI_ENDPOINT_NAME", "danone-gpt5")

_DATABRICKS_HOST = os.getenv(
    "DATABRICKS_HOST", "https://fevm-danonedemo.cloud.databricks.com"
).rstrip("/")
_SQL_ENDPOINT    = f"{_DATABRICKS_HOST}/api/2.0/sql/statements"
_TIMEOUT         = 90.0   # httpx request timeout
_MAX_POLL        = 25     # max polling iterations (~25s at 1s interval)


def _token() -> str:
    return os.getenv("DATABRICKS_TOKEN") or os.getenv("DATABRICKS_PAT", "")


def _headers() -> dict:
    tok = _token()
    if not tok:
        # Fallback: try to read DEFAULT profile for local dev
        try:
            import configparser, pathlib
            cfg = configparser.ConfigParser()
            cfg.read(pathlib.Path.home() / ".databrickscfg")
            tok = cfg.get("DEFAULT", "token", fallback="")
        except Exception:
            pass
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
    }


def execute_query(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute a SQL statement against the Databricks SQL warehouse.
    Returns rows as a list of dicts. Returns [] on any error.
    """
    payload = {
        "statement": sql,
        "warehouse_id": WAREHOUSE_ID,
        "catalog": CATALOG,
        "schema": SCHEMA,
        "wait_timeout": "30s",    # wait up to 30s in the HTTP response
        "on_wait_timeout": "CONTINUE",  # if not done, keep running and return statement_id
        "disposition": "INLINE",
        "format": "JSON_ARRAY",
    }

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            # Submit statement
            resp = client.post(_SQL_ENDPOINT, headers=_headers(), json=payload)
            if resp.status_code not in (200, 201):
                logger.error(
                    f"SQL statement submit failed ({resp.status_code}): "
                    f"{resp.text[:300]} | SQL: {sql[:200]}"
                )
                return []

            data = resp.json()
            sid  = data.get("statement_id")
            if not sid:
                logger.error(f"No statement_id in response: {data}")
                return []

            # Poll until done if not immediately SUCCEEDED
            state = data.get("status", {}).get("state", "")
            for _ in range(_MAX_POLL):
                if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
                    break
                time.sleep(1.0)
                poll = client.get(f"{_SQL_ENDPOINT}/{sid}", headers=_headers())
                if poll.status_code == 200:
                    data  = poll.json()
                    state = data.get("status", {}).get("state", "")

            if state != "SUCCEEDED":
                err = data.get("status", {}).get("error", {})
                logger.error(f"Statement {sid} ended with state={state}: {err} | SQL: {sql[:200]}")
                return []

            # Parse inline results
            manifest = data.get("manifest", {})
            schema   = manifest.get("schema", {})
            columns  = [c["name"] for c in schema.get("columns", [])]
            result   = data.get("result", {})
            rows_raw = result.get("data_array", []) or []

            return [dict(zip(columns, row)) for row in rows_raw]

    except Exception as exc:
        logger.error(f"execute_query error: {exc} | SQL: {sql[:200]}")
        return []


def execute_ai_query(prompt: str) -> str:
    """Run a one-off ai_query() call via SQL warehouse for ad-hoc report generation."""
    safe_prompt = prompt.replace("'", "''")
    sql = f"SELECT ai_query('{AI_ENDPOINT}', '{safe_prompt}') AS result"
    rows = execute_query(sql)
    return rows[0]["result"] if rows else ""


def get_workspace_client():
    """Return a WorkspaceClient for non-SQL operations."""
    from databricks.sdk import WorkspaceClient
    host  = _DATABRICKS_HOST
    token = _token()
    if token:
        return WorkspaceClient(host=host, token=token)
    return WorkspaceClient(host=host)
