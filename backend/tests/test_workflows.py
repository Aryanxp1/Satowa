"""Comprehensive test suite for SETOWA Workflow Engine and DAG Execution (Milestone T013)."""
import asyncio
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.skills import (
    BaseSkill,
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillInputDefinition,
    SkillManifest,
    SkillOutputDefinition,
    SkillRegistry,
    SkillRuntime,
    get_default_registry,
    get_default_runtime,
)
from app.workflows import (
    DAGGraph,
    CycleError,
    NodeExecutionStatus,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowEngine,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
    WorkflowExecutionStatus,
    WorkflowInputDefinition,
    WorkflowNode,
    WorkflowStore,
    get_default_workflow_engine,
    get_default_workflow_store,
    validate_workflow,
)

client = TestClient(app)


# Test helper skills
class UpperCaseSkill(BaseSkill):
    def __init__(self, name="text-upper", version="1.0.0"):
        manifest = SkillManifest(
            name=name,
            version=version,
            description="Converts text to uppercase.",
            kind="deterministic",
            permissions=["media:read"],
            inputs=[
                SkillInputDefinition(name="text", type="string", description="Input string", required=True),
            ],
            outputs=[
                SkillOutputDefinition(name="upper_text", type="string", description="Uppercase string"),
            ],
        )
        super().__init__(manifest)

    async def execute(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> SkillExecutionResult:
        text = inputs.get("text", "")
        return SkillExecutionResult(
            skill_name=self.name,
            skill_version=self.version,
            status=SkillExecutionStatus.SUCCESS,
            outputs={"upper_text": text.upper()},
        )


class PrefixSkill(BaseSkill):
    def __init__(self, name="text-prefix", version="1.0.0"):
        manifest = SkillManifest(
            name=name,
            version=version,
            description="Prepends a prefix to text.",
            kind="deterministic",
            permissions=["media:read"],
            inputs=[
                SkillInputDefinition(name="text", type="string", description="Input string", required=True),
                SkillInputDefinition(name="prefix", type="string", description="Prefix", required=False, default="[SETOWA] "),
            ],
            outputs=[
                SkillOutputDefinition(name="prefixed_text", type="string", description="Prefixed string"),
            ],
        )
        super().__init__(manifest)

    async def execute(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> SkillExecutionResult:
        text = inputs.get("text", "")
        prefix = inputs.get("prefix", "[SETOWA] ")
        return SkillExecutionResult(
            skill_name=self.name,
            skill_version=self.version,
            status=SkillExecutionStatus.SUCCESS,
            outputs={"prefixed_text": f"{prefix}{text}"},
        )


class DeliberateFailSkill(BaseSkill):
    def __init__(self, name="fail-skill", version="1.0.0"):
        manifest = SkillManifest(
            name=name,
            version=version,
            description="Always fails to test error propagation.",
            kind="deterministic",
            permissions=["media:read"],
            inputs=[
                SkillInputDefinition(name="item", type="string", description="Dummy item", required=True),
            ],
            outputs=[
                SkillOutputDefinition(name="result", type="string", description="Never reached"),
            ],
        )
        super().__init__(manifest)

    async def execute(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> SkillExecutionResult:
        return SkillExecutionResult(
            skill_name=self.name,
            skill_version=self.version,
            status=SkillExecutionStatus.FAILED,
            outputs={},
            errors=["Simulated failure in DeliberateFailSkill"],
        )


def _setup_isolated_engine():
    reg = SkillRegistry()
    reg.register(UpperCaseSkill())
    reg.register(PrefixSkill())
    reg.register(DeliberateFailSkill())
    rt = SkillRuntime(reg)
    engine = WorkflowEngine(runtime=rt, registry=reg)
    return engine, reg, rt


# 1. Valid Workflow Schema
def test_valid_workflow_schema():
    wf = WorkflowDefinition(
        name="test-pipeline",
        version="1.0.0",
        description="A test workflow",
        inputs=[WorkflowInputDefinition(name="raw_text", type="string")],
        nodes=[
            WorkflowNode(id="step1", skill="text-upper", skill_version="1.0.0", inputs={"text": "$input.raw_text"}),
            WorkflowNode(id="step2", skill="text-prefix", skill_version="1.0.0", inputs={"text": "$node.step1.upper_text"}),
        ],
        edges=[
            WorkflowEdge(source_node="step1", source_output="upper_text", target_node="step2", target_input="text")
        ],
    )
    assert wf.name == "test-pipeline"
    assert len(wf.nodes) == 2
    assert len(wf.edges) == 1


# 2. Invalid Workflow Schema (Missing name / empty nodes)
def test_invalid_workflow_schema():
    engine, reg, _ = _setup_isolated_engine()
    wf_no_nodes = WorkflowDefinition(name="empty-flow", nodes=[])
    res = engine.validate(wf_no_nodes)
    assert not res.is_valid
    assert any("at least one node" in err.lower() for err in res.errors)

    wf_blank_name = WorkflowDefinition(name="", nodes=[
        WorkflowNode(id="s1", skill="text-upper", inputs={"text": "hi"})
    ])
    res2 = engine.validate(wf_blank_name)
    assert not res2.is_valid
    assert any("name" in err.lower() for err in res2.errors)


# 3. Duplicate Node IDs
def test_duplicate_node_ids():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="duplicate-nodes",
        nodes=[
            WorkflowNode(id="step_a", skill="text-upper", inputs={"text": "hello"}),
            WorkflowNode(id="step_a", skill="text-prefix", inputs={"text": "world"}),
        ],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("duplicate node id" in err.lower() for err in res.errors)


# 4. Missing / Unregistered Skill Reference
def test_missing_skill_reference():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="missing-skill-flow",
        nodes=[
            WorkflowNode(id="step1", skill="non-existent-skill", skill_version="1.0.0", inputs={"x": "val"})
        ],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("unregistered or unavailable" in err.lower() for err in res.errors)


# 5. Missing Skill Version
def test_missing_skill_version():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="wrong-version-flow",
        nodes=[
            WorkflowNode(id="step1", skill="text-upper", skill_version="9.9.9", inputs={"text": "hello"})
        ],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("9.9.9" in err for err in res.errors)


# 6. Invalid Edge Nodes
def test_invalid_edge_nodes():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="bad-edge-flow",
        nodes=[
            WorkflowNode(id="step1", skill="text-upper", inputs={"text": "hello"})
        ],
        edges=[
            WorkflowEdge(source_node="step1", source_output="upper_text", target_node="phantom_node", target_input="text")
        ],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("nonexistent target_node" in err.lower() for err in res.errors)


# 7. Invalid Edge Ports
def test_invalid_edge_ports():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="bad-port-flow",
        nodes=[
            WorkflowNode(id="step1", skill="text-upper", inputs={"text": "hello"}),
            WorkflowNode(id="step2", skill="text-prefix", inputs={"text": "placeholder"}),
        ],
        edges=[
            WorkflowEdge(source_node="step1", source_output="fake_output", target_node="step2", target_input="text")
        ],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("fake_output" in err for err in res.errors)


# 8. Invalid Input Mappings
def test_invalid_input_mappings():
    engine, reg, _ = _setup_isolated_engine()
    # Reference to undeclared workflow input $input.missing_var
    wf = WorkflowDefinition(
        name="bad-input-mapping",
        inputs=[WorkflowInputDefinition(name="declared_input", type="string")],
        nodes=[
            WorkflowNode(id="step1", skill="text-upper", inputs={"text": "$input.missing_var"}),
        ],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("undeclared workflow input 'missing_var'" in err for err in res.errors)

    # Reference to invalid output on upstream node
    wf2 = WorkflowDefinition(
        name="bad-node-ref",
        nodes=[
            WorkflowNode(id="step1", skill="text-upper", inputs={"text": "hello"}),
            WorkflowNode(id="step2", skill="text-prefix", inputs={"text": "$node.step1.nonexistent_out"}),
        ],
    )
    res2 = engine.validate(wf2)
    assert not res2.is_valid
    assert any("nonexistent_out" in err for err in res2.errors)


# 9. Self-Loop Detection
def test_self_loop_detection():
    engine, reg, _ = _setup_isolated_engine()
    # Explicit self-edge
    wf = WorkflowDefinition(
        name="self-loop-edge",
        nodes=[WorkflowNode(id="loop_node", skill="text-upper", inputs={"text": "hi"})],
        edges=[WorkflowEdge(source_node="loop_node", source_output="upper_text", target_node="loop_node", target_input="text")],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("self-loop" in err.lower() for err in res.errors)

    # Implicit self-reference in inputs
    wf2 = WorkflowDefinition(
        name="self-loop-input",
        nodes=[WorkflowNode(id="loop_node2", skill="text-upper", inputs={"text": "$node.loop_node2.upper_text"})],
    )
    res2 = engine.validate(wf2)
    assert not res2.is_valid
    assert any("cannot reference its own output" in err.lower() for err in res2.errors)


# 10. Cycle Detection (A -> B -> C -> A)
def test_cycle_detection():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="circular-workflow",
        nodes=[
            WorkflowNode(id="node_a", skill="text-upper", inputs={"text": "$node.node_c.upper_text"}),
            WorkflowNode(id="node_b", skill="text-upper", inputs={"text": "$node.node_a.upper_text"}),
            WorkflowNode(id="node_c", skill="text-upper", inputs={"text": "$node.node_b.upper_text"}),
        ],
        edges=[
            WorkflowEdge(source_node="node_a", source_output="upper_text", target_node="node_b", target_input="text"),
            WorkflowEdge(source_node="node_b", source_output="upper_text", target_node="node_c", target_input="text"),
            WorkflowEdge(source_node="node_c", source_output="upper_text", target_node="node_a", target_input="text"),
        ],
    )
    res = engine.validate(wf)
    assert not res.is_valid
    assert any("circular dependency" in err.lower() or "cycle" in err.lower() for err in res.errors)


# 11. Topological Execution Order Computation
def test_topological_execution_order():
    engine, reg, _ = _setup_isolated_engine()
    # Diamond graph:
    #      start
    #     /     \
    #  left     right
    #     \     /
    #       join
    wf = WorkflowDefinition(
        name="diamond-workflow",
        inputs=[WorkflowInputDefinition(name="initial", type="string")],
        nodes=[
            WorkflowNode(id="start", skill="text-upper", inputs={"text": "$input.initial"}),
            WorkflowNode(id="left", skill="text-prefix", inputs={"text": "$node.start.upper_text", "prefix": "[LEFT] "}),
            WorkflowNode(id="right", skill="text-prefix", inputs={"text": "$node.start.upper_text", "prefix": "[RIGHT] "}),
            WorkflowNode(id="join", skill="text-upper", inputs={"text": "$node.left.prefixed_text"}),
        ],
        edges=[
            WorkflowEdge(source_node="start", source_output="upper_text", target_node="left", target_input="text"),
            WorkflowEdge(source_node="start", source_output="upper_text", target_node="right", target_input="text"),
            WorkflowEdge(source_node="left", source_output="prefixed_text", target_node="join", target_input="text"),
        ],
    )
    res = engine.validate(wf)
    assert res.is_valid
    order = res.execution_order
    assert order.index("start") < order.index("left")
    assert order.index("start") < order.index("right")
    assert order.index("left") < order.index("join")


# 12. Workflow Input Propagation ($input.var)
def test_workflow_input_propagation():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="input-prop-test",
        inputs=[WorkflowInputDefinition(name="greeting", type="string")],
        nodes=[
            WorkflowNode(id="step1", skill="text-upper", inputs={"text": "$input.greeting"}),
        ],
    )
    req = WorkflowExecutionRequest(inputs={"greeting": "welcome to setowa"})
    res = asyncio.run(engine.execute(wf, req))
    assert res.status == WorkflowExecutionStatus.SUCCESS
    assert res.node_results["step1"].status == NodeExecutionStatus.SUCCESS
    assert res.node_results["step1"].outputs["upper_text"] == "WELCOME TO SETOWA"


# 13. Node Output Propagation ($node.id.output and edge)
def test_node_output_propagation():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="output-prop-test",
        inputs=[WorkflowInputDefinition(name="msg", type="string")],
        nodes=[
            WorkflowNode(id="n1", skill="text-upper", inputs={"text": "$input.msg"}),
            WorkflowNode(id="n2", skill="text-prefix", inputs={"text": "$node.n1.upper_text", "prefix": "[PROVEN] "}),
        ],
        edges=[
            WorkflowEdge(source_node="n1", source_output="upper_text", target_node="n2", target_input="text")
        ],
    )
    req = WorkflowExecutionRequest(inputs={"msg": "cleanup verified"})
    res = asyncio.run(engine.execute(wf, req))
    assert res.status == WorkflowExecutionStatus.SUCCESS
    assert res.node_results["n2"].outputs["prefixed_text"] == "[PROVEN] CLEANUP VERIFIED"


# 14. Successful Multi-Node Execution
def test_successful_multi_node_execution():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="tri-stage-flow",
        inputs=[WorkflowInputDefinition(name="site_name", type="string")],
        nodes=[
            WorkflowNode(id="stage1", skill="text-upper", inputs={"text": "$input.site_name"}),
            WorkflowNode(id="stage2", skill="text-prefix", inputs={"text": "$node.stage1.upper_text", "prefix": "STAGE2: "}),
            WorkflowNode(id="stage3", skill="text-prefix", inputs={"text": "$node.stage2.prefixed_text", "prefix": "FINAL: "}),
        ],
        edges=[
            WorkflowEdge(source_node="stage1", source_output="upper_text", target_node="stage2", target_input="text"),
            WorkflowEdge(source_node="stage2", source_output="prefixed_text", target_node="stage3", target_input="text"),
        ],
    )
    req = WorkflowExecutionRequest(inputs={"site_name": "green river"})
    res = asyncio.run(engine.execute(wf, req))
    assert res.status == WorkflowExecutionStatus.SUCCESS
    assert len(res.node_results) == 3
    assert res.node_results["stage3"].outputs["prefixed_text"] == "FINAL: STAGE2: GREEN RIVER"
    assert res.outputs["stage3_output"]["prefixed_text"] == "FINAL: STAGE2: GREEN RIVER"


# 15. Node Failure Propagation & Skipped Downstream Nodes
def test_node_failure_propagation():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="failure-prop-flow",
        inputs=[WorkflowInputDefinition(name="val", type="string")],
        nodes=[
            WorkflowNode(id="good_start", skill="text-upper", inputs={"text": "$input.val"}),
            WorkflowNode(id="failing_step", skill="fail-skill", inputs={"item": "$node.good_start.upper_text"}),
            WorkflowNode(id="downstream_step", skill="text-prefix", inputs={"text": "$node.failing_step.result"}),
        ],
        edges=[
            WorkflowEdge(source_node="good_start", source_output="upper_text", target_node="failing_step", target_input="item"),
            WorkflowEdge(source_node="failing_step", source_output="result", target_node="downstream_step", target_input="text"),
        ],
    )
    req = WorkflowExecutionRequest(inputs={"val": "data"})
    res = asyncio.run(engine.execute(wf, req))
    assert res.status == WorkflowExecutionStatus.FAILED
    assert res.node_results["good_start"].status == NodeExecutionStatus.SUCCESS
    assert res.node_results["failing_step"].status == NodeExecutionStatus.FAILED
    assert res.node_results["downstream_step"].status == NodeExecutionStatus.SKIPPED
    assert any("upstream dependencies did not succeed" in err.lower() for err in res.node_results["downstream_step"].errors)


# 16. Unavailable Skill Handling
def test_unavailable_skill_handling():
    # Build workflow that registers properly, then unregister skill to simulate mid-lifecycle unavailability
    reg = SkillRegistry()
    reg.register(UpperCaseSkill())
    rt = SkillRuntime(reg)
    engine = WorkflowEngine(runtime=rt, registry=reg)

    wf = WorkflowDefinition(
        name="transient-skill-flow",
        inputs=[WorkflowInputDefinition(name="txt", type="string")],
        nodes=[WorkflowNode(id="step1", skill="text-upper", inputs={"text": "$input.txt"})],
    )
    # Validation passes while registered
    val = engine.validate(wf)
    assert val.is_valid

    # Now unregister skill
    reg.unregister("text-upper")
    # Execution detects skill became unavailable
    req = WorkflowExecutionRequest(inputs={"txt": "test"})
    res = asyncio.run(engine.execute(wf, req))
    assert res.status == WorkflowExecutionStatus.FAILED


# 17. Execution Reporting (Duration, Status, Timestamps, Node Results)
def test_execution_reporting():
    engine, reg, _ = _setup_isolated_engine()
    wf = WorkflowDefinition(
        name="telemetry-test",
        inputs=[WorkflowInputDefinition(name="raw", type="string")],
        nodes=[WorkflowNode(id="s1", skill="text-upper", inputs={"text": "$input.raw"})],
    )
    req = WorkflowExecutionRequest(inputs={"raw": "test telemetry"})
    res = asyncio.run(engine.execute(wf, req))

    assert res.execution_id is not None
    assert res.workflow_id == wf.id
    assert res.started_at is not None
    assert res.completed_at is not None
    assert res.duration_ms >= 0.0
    assert "s1" in res.node_results
    assert res.node_results["s1"].latency_ms >= 0.0


# 18. Workflow Persistence (Store CRUD and Executions)
def test_workflow_store_crud_and_executions():
    store = get_default_workflow_store()
    test_id = "wf_crud_test"

    # Clean up if exists
    store.delete(test_id)

    wf = WorkflowDefinition(
        id=test_id,
        name="CRUD Test Workflow",
        version="1.0.0",
        description="Testing SQLite storage",
        inputs=[WorkflowInputDefinition(name="sample_in", type="string")],
        nodes=[WorkflowNode(id="n1", skill="media-metadata", inputs={"asset_id": "$input.sample_in"})],
    )
    # 1. Create
    created = store.create(wf)
    assert created.id == test_id

    # 2. Get
    retrieved = store.get(test_id)
    assert retrieved is not None
    assert retrieved.name == "CRUD Test Workflow"

    # 3. List
    summaries = store.list()
    assert any(s.id == test_id for s in summaries)

    # 4. Update
    retrieved.description = "Updated description"
    updated = store.update(retrieved)
    assert updated.description == "Updated description"
    assert store.get(test_id).description == "Updated description"

    # 5. Save & List Execution
    exec_res = WorkflowExecutionResult(
        execution_id="exec_test_123",
        workflow_id=test_id,
        workflow_version="1.0.0",
        status=WorkflowExecutionStatus.SUCCESS,
        inputs={"sample_in": "test"},
        outputs={"res": "ok"},
        node_results={},
        execution_order=["n1"],
        started_at="2026-09-27T00:00:00Z",
        completed_at="2026-09-27T00:00:01Z",
        duration_ms=100.0,
    )
    store.save_execution(exec_res)
    history = store.list_executions(workflow_id=test_id)
    assert any(h["id"] == "exec_test_123" for h in history)

    fetched_exec = store.get_execution("exec_test_123")
    assert fetched_exec is not None
    assert fetched_exec.execution_id == "exec_test_123"

    # 6. Delete
    deleted = store.delete(test_id)
    assert deleted
    assert store.get(test_id) is None


# 19. API Workflows CRUD
def test_api_workflows_crud():
    wf_payload = {
        "id": "wf_api_test",
        "name": "API Test Workflow",
        "version": "1.0.0",
        "description": "Created via REST API",
        "inputs": [{"name": "asset_id", "type": "asset_id", "required": True}],
        "nodes": [
            {
                "id": "meta_step",
                "skill": "media-metadata",
                "skill_version": "1.0.0",
                "inputs": {"asset_id": "$input.asset_id"},
            }
        ],
        "edges": [],
    }

    # Delete if exists
    client.delete("/api/v1/workflows/wf_api_test")

    # POST create
    res = client.post("/api/v1/workflows", json=wf_payload)
    assert res.status_code == 201
    created_data = res.json()
    assert created_data["id"] == "wf_api_test"

    # GET list
    list_res = client.get("/api/v1/workflows")
    assert list_res.status_code == 200
    assert any(w["id"] == "wf_api_test" for w in list_res.json())

    # GET single
    get_res = client.get("/api/v1/workflows/wf_api_test")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "API Test Workflow"

    # PUT update
    wf_payload["name"] = "API Test Workflow Renamed"
    put_res = client.put("/api/v1/workflows/wf_api_test", json=wf_payload)
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "API Test Workflow Renamed"

    # DELETE
    del_res = client.delete("/api/v1/workflows/wf_api_test")
    assert del_res.status_code == 200

    # Verify 404 after delete
    get_del = client.get("/api/v1/workflows/wf_api_test")
    assert get_del.status_code == 404


# 20. API Workflow Validation Endpoints
def test_api_workflow_validation():
    # Built-in workflow should validate successfully
    res = client.post("/api/v1/workflows/wf_evidence_compare/validate")
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0
    assert len(data["execution_order"]) == 3

    # Draft validation endpoint with invalid schema
    invalid_draft = {
        "name": "Invalid Draft",
        "nodes": [
            {"id": "s1", "skill": "nonexistent-skill-99", "inputs": {}}
        ]
    }
    draft_res = client.post("/api/v1/workflows/validate-draft", json=invalid_draft)
    assert draft_res.status_code == 200
    draft_data = draft_res.json()
    assert draft_data["is_valid"] is False
    assert len(draft_data["errors"]) > 0


# 21. API Workflow Execution Endpoint
def test_api_workflow_execution():
    exec_payload = {
        "inputs": {
            "before_asset_id": "nonexistent_asset_before",
            "after_asset_id": "nonexistent_asset_after",
        }
    }
    # Execute built-in workflow
    res = client.post("/api/v1/workflows/wf_evidence_compare/execute", json=exec_payload)
    assert res.status_code == 200
    data = res.json()
    assert "execution_id" in data
    assert data["workflow_id"] == "wf_evidence_compare"
    assert "node_results" in data

    # Check executions list
    hist_res = client.get("/api/v1/workflows/wf_evidence_compare/executions")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1

    # Check execution retrieval by ID
    single_res = client.get(f"/api/v1/workflow-executions/{data['execution_id']}")
    assert single_res.status_code == 200
    assert single_res.json()["execution_id"] == data["execution_id"]


# 22. Real Built-in Multi-Skill Workflow Execution
def test_builtin_before_after_comparison_workflow():
    store = get_default_workflow_store()
    engine = get_default_workflow_engine()

    builtin_wf = store.get("wf_evidence_compare")
    assert builtin_wf is not None
    assert builtin_wf.name == "Before-After Evidence Comparison"
    assert len(builtin_wf.nodes) == 3
    assert len(builtin_wf.edges) == 2

    # Seed test assets in DB so media-metadata resolves them
    from app.services.evidence_store import connection, ensure_ingestion_visit, save_asset
    with connection() as db:
        db.execute("DELETE FROM assets WHERE asset_id IN ('sample_before_asset', 'sample_after_asset')")
        db.commit()
        v_id = ensure_ingestion_visit(db, "test-wf-site", "2026-09-27")
        save_asset(db, {
            "asset_id": "sample_before_asset",
            "visit_id": v_id,
            "public_id": "sample_before",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/sample_before.jpg",
            "source": "test_wf",
            "width": 800,
            "height": 600,
            "format": "jpg",
            "permission_status": "granted",
            "thumbnail_url": "https://res.cloudinary.com/demo/image/upload/w_200/sample_before.jpg",
            "site_id": "test-wf-site",
            "media_type": "image",
            "processing_status": "ready",
            "original_filename": "before.jpg",
            "duration": None,
            "preview_url": None,
            "metadata_json": "{}",
        })
        save_asset(db, {
            "asset_id": "sample_after_asset",
            "visit_id": v_id,
            "public_id": "sample_after",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/sample_after.jpg",
            "source": "test_wf",
            "width": 800,
            "height": 600,
            "format": "jpg",
            "permission_status": "granted",
            "thumbnail_url": "https://res.cloudinary.com/demo/image/upload/w_200/sample_after.jpg",
            "site_id": "test-wf-site",
            "media_type": "image",
            "processing_status": "ready",
            "original_filename": "after.jpg",
            "duration": None,
            "preview_url": None,
            "metadata_json": "{}",
        })

    # Execute with explicit inputs
    req = WorkflowExecutionRequest(
        inputs={
            "before_asset_id": "sample_before_asset",
            "after_asset_id": "sample_after_asset",
        }
    )
    result = asyncio.run(engine.execute(builtin_wf, req))
    assert result.workflow_id == "wf_evidence_compare"
    assert "before_meta" in result.node_results
    assert "after_meta" in result.node_results
    assert "compare" in result.node_results
    assert result.node_results["before_meta"].status == NodeExecutionStatus.SUCCESS
    assert result.node_results["after_meta"].status == NodeExecutionStatus.SUCCESS
    assert result.node_results["before_meta"].outputs["secure_url"] == "https://res.cloudinary.com/demo/image/upload/sample_before.jpg"
    assert result.node_results["after_meta"].outputs["secure_url"] == "https://res.cloudinary.com/demo/image/upload/sample_after.jpg"
    # compare node should have received the resolved secure_urls from before_meta and after_meta
    assert result.node_results["compare"].inputs["before_url"] == "https://res.cloudinary.com/demo/image/upload/sample_before.jpg"
    assert result.node_results["compare"].inputs["after_url"] == "https://res.cloudinary.com/demo/image/upload/sample_after.jpg"
