"""Persistence store for SETOWA workflows and execution history using SQLite."""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.services.evidence_store import connection
from app.config import settings
from app.workflows.models import (
    WorkflowDefinition,
    WorkflowExecutionResult,
    WorkflowInputDefinition,
    WorkflowNode,
    WorkflowEdge,
    WorkflowSummary,
)

WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_executions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    inputs_json TEXT,
    result_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms REAL
);
"""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStore:
    """Manages storage and retrieval of workflow definitions and execution runs."""

    def __init__(self):
        self.db_path = settings.LEX_DB_PATH
        self._ensure_schema()
        self._seed_builtins()

    def _ensure_schema(self) -> None:
        """Create workflows and workflow_executions tables if they do not exist."""
        with connection() as db:
            db.executescript(WORKFLOW_SCHEMA)

    def _seed_builtins(self) -> None:
        """Seed default demonstration workflows if they do not already exist."""
        builtin_id = "wf_evidence_compare"
        existing = self.get(builtin_id)
        if not existing:
            demo_workflow = WorkflowDefinition(
                id=builtin_id,
                name="Before-After Evidence Comparison",
                version="1.0.0",
                description="Fetches Cloudinary metadata for before and after cleanup assets, then performs Gemini structured visual change assessment.",
                inputs=[
                    WorkflowInputDefinition(
                        name="before_asset_id",
                        type="asset_id",
                        description="Database asset ID or public ID for pre-cleanup photo",
                        required=True,
                    ),
                    WorkflowInputDefinition(
                        name="after_asset_id",
                        type="asset_id",
                        description="Database asset ID or public ID for post-cleanup photo",
                        required=True,
                    ),
                ],
                nodes=[
                    WorkflowNode(
                        id="before_meta",
                        skill="media-metadata",
                        skill_version="1.0.0",
                        inputs={"asset_id": "$input.before_asset_id"},
                        position={"x": 100, "y": 80},
                        metadata={"label": "01 / Before Media Metadata"},
                    ),
                    WorkflowNode(
                        id="after_meta",
                        skill="media-metadata",
                        skill_version="1.0.0",
                        inputs={"asset_id": "$input.after_asset_id"},
                        position={"x": 100, "y": 280},
                        metadata={"label": "02 / After Media Metadata"},
                    ),
                    WorkflowNode(
                        id="compare",
                        skill="evidence-comparison",
                        skill_version="1.0.0",
                        inputs={
                            "before_url": "$node.before_meta.secure_url",
                            "after_url": "$node.after_meta.secure_url",
                        },
                        position={"x": 460, "y": 180},
                        metadata={"label": "03 / Visual AI Comparison"},
                    ),
                ],
                edges=[
                    WorkflowEdge(
                        source_node="before_meta",
                        source_output="secure_url",
                        target_node="compare",
                        target_input="before_url",
                    ),
                    WorkflowEdge(
                        source_node="after_meta",
                        source_output="secure_url",
                        target_node="compare",
                        target_input="after_url",
                    ),
                ],
                metadata={"category": "environmental-cleanup", "is_builtin": True},
                created_at=_iso_now(),
                updated_at=_iso_now(),
            )
            self.create(demo_workflow)

    def create(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Persist a new workflow definition."""
        now = _iso_now()
        workflow.created_at = workflow.created_at or now
        workflow.updated_at = now
        definition_json = workflow.model_dump_json()

        with connection() as db:
            db.execute(
                """
                INSERT INTO workflows (id, name, version, description, definition_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow.id,
                    workflow.name,
                    workflow.version,
                    workflow.description,
                    definition_json,
                    workflow.created_at,
                    workflow.updated_at,
                ),
            )
            db.commit()
        return workflow

    def get(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Retrieve a workflow by its ID."""
        try:
            with connection() as db:
                cur = db.execute("SELECT definition_json FROM workflows WHERE id = ?", (workflow_id,))
                row = cur.fetchone()
                if not row:
                    return None
                data = json.loads(row["definition_json"])
                return WorkflowDefinition(**data)
        except sqlite3.OperationalError:
            self._ensure_schema()
            self._seed_builtins()
            with connection() as db:
                cur = db.execute("SELECT definition_json FROM workflows WHERE id = ?", (workflow_id,))
                row = cur.fetchone()
                if not row:
                    return None
                data = json.loads(row["definition_json"])
                return WorkflowDefinition(**data)

    def list(self) -> List[WorkflowSummary]:
        """List summary descriptions of all stored workflows."""
        try:
            with connection() as db:
                cur = db.execute(
                    "SELECT id, name, version, description, definition_json, updated_at FROM workflows ORDER BY updated_at DESC"
                )
                rows = cur.fetchall()
        except sqlite3.OperationalError:
            self._ensure_schema()
            self._seed_builtins()
            with connection() as db:
                cur = db.execute(
                    "SELECT id, name, version, description, definition_json, updated_at FROM workflows ORDER BY updated_at DESC"
                )
                rows = cur.fetchall()

        summaries = []
        for row in rows:
            try:
                data = json.loads(row["definition_json"])
                node_count = len(data.get("nodes", []))
                edge_count = len(data.get("edges", []))
            except Exception:
                node_count = 0
                edge_count = 0
            summaries.append(
                WorkflowSummary(
                    id=row["id"],
                    name=row["name"],
                    version=row["version"],
                    description=row["description"] or "",
                    node_count=node_count,
                    edge_count=edge_count,
                    updated_at=row["updated_at"],
                )
            )
        return summaries

    def update(self, workflow: WorkflowDefinition) -> Optional[WorkflowDefinition]:
        """Update an existing workflow definition."""
        now = _iso_now()
        workflow.updated_at = now
        definition_json = workflow.model_dump_json()

        with connection() as db:
            cur = db.execute(
                """
                UPDATE workflows
                SET name = ?, version = ?, description = ?, definition_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    workflow.name,
                    workflow.version,
                    workflow.description,
                    definition_json,
                    workflow.updated_at,
                    workflow.id,
                ),
            )
            db.commit()
            if cur.rowcount == 0:
                return None
        return workflow

    def delete(self, workflow_id: str) -> bool:
        """Delete a workflow and its execution history."""
        with connection() as db:
            cur = db.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            db.commit()
            return cur.rowcount > 0

    def save_execution(self, result: WorkflowExecutionResult) -> None:
        """Persist a workflow execution audit record."""
        with connection() as db:
            db.execute(
                """
                INSERT INTO workflow_executions (
                    id, workflow_id, status, inputs_json, result_json, started_at, completed_at, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.execution_id,
                    result.workflow_id,
                    result.status.value,
                    json.dumps(result.inputs),
                    result.model_dump_json(),
                    result.started_at,
                    result.completed_at,
                    result.duration_ms,
                ),
            )
            db.commit()

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecutionResult]:
        """Retrieve a specific execution result by ID."""
        with connection() as db:
            cur = db.execute("SELECT result_json FROM workflow_executions WHERE id = ?", (execution_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = json.loads(row["result_json"])
            return WorkflowExecutionResult(**data)

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List execution records, optionally filtered by workflow_id."""
        with connection() as db:
            if workflow_id:
                cur = db.execute(
                    """
                    SELECT id, workflow_id, status, started_at, completed_at, duration_ms
                    FROM workflow_executions
                    WHERE workflow_id = ?
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    (workflow_id, limit),
                )
            else:
                cur = db.execute(
                    """
                    SELECT id, workflow_id, status, started_at, completed_at, duration_ms
                    FROM workflow_executions
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]
