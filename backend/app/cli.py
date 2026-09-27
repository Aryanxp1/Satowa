"""Unified SETOWA Command-Line Interface.

Provides a polished, zero-duplication CLI path for:
- satova/setowa ingest <dir>
- satova/setowa skill list
- satova/setowa workflow list
- satova/setowa workflow run <workflow_id> [--input-json <json>]
- satova/setowa run status <execution_id>
- satova/setowa story show <project_id>

Reuses existing domain services, SkillRuntime, WorkflowEngine, and EvidenceStore.
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Add backend directory to sys.path if not present
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.services import evidence_store as store
from app.skills import get_default_registry
from app.workflows import get_default_workflow_engine, get_default_workflow_store
from app.workflows.models import WorkflowExecutionRequest
from app.services import impact_story as impact_story_service


def cmd_ingest(args):
    """Ingest local media files using the media pipeline."""
    target_dir = Path(args.directory).resolve()
    if not target_dir.is_dir():
        print(f"Error: Directory '{target_dir}' does not exist or is not a directory.", file=sys.stderr)
        return 1

    from scripts.ingest_collection import ingest_directory

    print(f"[SETOWA] Ingesting media collection from: {target_dir}")
    print(f"         Project ID: {args.project_id}")
    print(f"         Source:     {args.source}")
    print(f"         Visit Date: {args.date}")

    result = ingest_directory(
        directory=target_dir,
        project_id=args.project_id,
        source=args.source,
        visit_date=args.date,
        permission_status=args.permission,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"\n[Ingest Summary]")
    print(f"  Total Found:  {result.get('total_found', 0)}")
    print(f"  Successful:   {result.get('successful', 0)}")
    print(f"  Failed:       {result.get('failed', 0)}")

    for item in result.get("results", []):
        status = item.get("status")
        name = item.get("filename")
        if status == "success":
            print(f"  [OK] {name} -> {item.get('media_type')} ({item.get('asset_id')})")
        else:
            print(f"  [FAIL] {name} -> {item.get('error')}")

    return 0 if result.get("failed", 0) == 0 else 1


def cmd_skill_list(args):
    """List all registered skills in the SETOWA skill runtime."""
    registry = get_default_registry()
    skills = registry.list_skills()
    if getattr(args, "json", False):
        print(json.dumps([s.model_dump() for s in skills], indent=2))
        return 0

    print("=" * 75)
    print(f"{'SKILL NAME':<30} {'VERSION':<10} {'KIND':<12} {'DESCRIPTION'}")
    print("=" * 75)
    for s in skills:
        desc = (s.description[:30] + "...") if len(s.description) > 30 else s.description
        kind_str = getattr(s.kind, "value", str(s.kind))
        print(f"{s.name:<30} {s.version:<10} {kind_str:<12} {desc}")
    print("=" * 75)
    print(f"Total Skills Available: {len(skills)}")
    return 0


def cmd_workflow_list(args):
    """List all available workflows in the SETOWA workflow engine."""
    wf_store = get_default_workflow_store()
    workflows = wf_store.list()

    if getattr(args, "json", False):
        print(json.dumps([w.model_dump() for w in workflows], indent=2))
        return 0

    print("=" * 75)
    print(f"{'WORKFLOW ID':<25} {'NAME':<30} {'NODES':<8} {'EDGES':<8}")
    print("=" * 75)
    for w in workflows:
        print(f"{w.id:<25} {w.name:<30} {w.node_count:<8} {w.edge_count:<8}")
    print("=" * 75)
    print(f"Total Workflows Available: {len(workflows)}")
    return 0


def cmd_workflow_run(args):
    """Execute a workflow DAG using the SETOWA workflow engine."""
    import asyncio
    wf_store = get_default_workflow_store()
    engine = get_default_workflow_engine()

    workflow = wf_store.get(args.workflow_id)
    if not workflow:
        print(f"Error: Workflow '{args.workflow_id}' not found.", file=sys.stderr)
        return 1

    inputs = {}
    input_json = getattr(args, "input_json", None)
    input_list = getattr(args, "input", None)
    if input_json:
        try:
            inputs = json.loads(input_json)
        except Exception as e:
            print(f"Error: Invalid JSON for --input-json: {e}", file=sys.stderr)
            return 1
    elif input_list:
        for item in input_list:
            if "=" in item:
                k, v = item.split("=", 1)
                inputs[k.strip()] = v.strip()
    else:
        # Default demo inputs for wf_evidence_compare if none supplied
        if args.workflow_id == "wf_evidence_compare":
            inputs = {
                "before_asset_id": "ast_mombasa_before",
                "after_asset_id": "ast_mombasa_after",
            }

    req = WorkflowExecutionRequest(workflow_id=args.workflow_id, inputs=inputs)
    print(f"[SETOWA] Running Workflow: {workflow.name} ({workflow.id})")

    result = asyncio.run(engine.execute(workflow, req))
    wf_store.save_execution(result)

    if getattr(args, "json", False):
        print(json.dumps(result.model_dump(), indent=2))
        return 0

    print(f"\n[Execution Summary]")
    print(f"  Execution ID:  {result.execution_id}")
    print(f"  Status:        {result.status.value.upper()}")
    print(f"  Total Latency: {result.duration_ms:.1f}ms")
    if result.errors:
        print(f"  Errors:        {', '.join(result.errors)}")

    print("\n[Node Execution Results]")
    for node_id, node_res in result.node_results.items():
        print(f"  Node: {node_id:<20} Status: {node_res.status.value:<12} Latency: {node_res.latency_ms:.1f}ms")
        if node_res.errors:
            print(f"    Errors: {', '.join(node_res.errors)}")

    return 0 if result.status.value in ("success", "completed") else 1


def cmd_run_status(args):
    """Inspect the status and outputs of a past workflow execution."""
    wf_store = get_default_workflow_store()
    execution = wf_store.get_execution(args.execution_id)

    if not execution:
        print(f"Error: Execution '{args.execution_id}' not found.", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(execution.model_dump(), indent=2))
        return 0

    print(f"\n[Workflow Execution Detail]")
    print(f"  Execution ID: {execution.execution_id}")
    print(f"  Workflow ID:  {execution.workflow_id}")
    print(f"  Status:       {execution.status.value.upper()}")
    print(f"  Started:      {execution.started_at}")
    print(f"  Completed:    {execution.completed_at}")
    print(f"  Latency:      {execution.duration_ms:.1f}ms")
    if execution.errors:
        print(f"  Errors:       {', '.join(execution.errors)}")

    print("\n[Node Breakdown]")
    for node_id, res in execution.node_results.items():
        print(f"  Node {node_id}: {res.status.value} ({res.latency_ms:.1f}ms)")
        if res.outputs:
            print(f"    Outputs: {list(res.outputs.keys())}")
        if res.errors:
            print(f"    Errors:  {', '.join(res.errors)}")

    return 0


def cmd_story_show(args):
    """Display the Impact Story for a project."""
    with store.connection() as db:
        story = impact_story_service.get_project_impact_story(db, args.project_id)

    if not story:
        print(f"Error: No Impact Story found for project '{args.project_id}'.", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(story.model_dump(), indent=2))
        return 0

    print("=" * 70)
    print(f"  SETOWA IMPACT STORY -- {story.title}")
    print("=" * 70)
    print(f"  Project ID:   {story.project_id}")
    print(f"  Status:       {story.status.upper()}")
    start_d = story.date_range.get("start") if story.date_range else "N/A"
    end_d = story.date_range.get("end") if story.date_range else "N/A"
    print(f"  Date Range:   {start_d} to {end_d}")
    print(f"  Share Token:  {story.share_token or 'None'}")
    if story.share_url:
        print(f"  Public URL:   {story.share_url}")
    print("\n[Summary Narrative]")
    print(f"  {story.summary_narrative}")
    print("\n[Uncertainty & Caveats]")
    print(f"  {story.uncertainty_note}")
    print("=" * 70)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="setowa",
        description="SETOWA Command-Line Interface — Environmental Evidence & Impact",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Ingest command
    p_ingest = subparsers.add_parser("ingest", help="Ingest local media files into SETOWA")
    p_ingest.add_argument("directory", help="Path to local media folder")
    p_ingest.add_argument("--project-id", default="proj_mombasa_marine", help="Target project ID")
    p_ingest.add_argument("--source", default="Field Collection", help="Source attribution")
    p_ingest.add_argument("--date", default="2026-09-27", help="Capture/visit date (YYYY-MM-DD)")
    p_ingest.add_argument("--permission", default="granted", choices=["granted", "revoked", "pending_consent"])
    p_ingest.add_argument("--json", action="store_true", help="Output results as JSON")

    # Skill command
    p_skill = subparsers.add_parser("skill", help="Inspect and execute SETOWA skills")
    p_skill_sub = p_skill.add_subparsers(dest="skill_subcommand", help="Skill commands")
    p_skill_list = p_skill_sub.add_parser("list", help="List registered skills")
    p_skill_list.add_argument("--json", action="store_true", help="Output results as JSON")

    # Workflow command
    p_wf = subparsers.add_parser("workflow", help="Inspect and execute workflow DAGs")
    p_wf_sub = p_wf.add_subparsers(dest="workflow_subcommand", help="Workflow commands")
    p_wf_list = p_wf_sub.add_parser("list", help="List available workflows")
    p_wf_list.add_argument("--json", action="store_true", help="Output results as JSON")

    p_wf_run = p_wf_sub.add_parser("run", help="Execute a workflow DAG")
    p_wf_run.add_argument("workflow_id", help="ID of the workflow to run")
    p_wf_run.add_argument("--input-json", help="Inputs as a JSON string")
    p_wf_run.add_argument("-i", "--input", action="append", help="Key=value input argument")
    p_wf_run.add_argument("--json", action="store_true", help="Output execution as JSON")

    # Run status command
    p_run = subparsers.add_parser("run", help="Inspect workflow execution runs")
    p_run_sub = p_run.add_subparsers(dest="run_subcommand", help="Run commands")
    p_run_status = p_run_sub.add_parser("status", help="Get execution status by ID")
    p_run_status.add_argument("execution_id", help="Workflow execution ID")
    p_run_status.add_argument("--json", action="store_true", help="Output execution as JSON")

    # Story command
    p_story = subparsers.add_parser("story", help="Inspect project impact stories")
    p_story_sub = p_story.add_subparsers(dest="story_subcommand", help="Story commands")
    p_story_show = p_story_sub.add_parser("show", help="Show story for a project")
    p_story_show.add_argument("project_id", help="Target project ID")
    p_story_show.add_argument("--json", action="store_true", help="Output story as JSON")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "ingest":
        return cmd_ingest(args)

    if args.command == "skill":
        if args.skill_subcommand == "list":
            return cmd_skill_list(args)
        parser.parse_args(["skill", "--help"])
        return 0

    if args.command == "workflow":
        if args.workflow_subcommand == "list":
            return cmd_workflow_list(args)
        if args.workflow_subcommand == "run":
            return cmd_workflow_run(args)
        parser.parse_args(["workflow", "--help"])
        return 0

    if args.command == "run":
        if args.run_subcommand == "status":
            return cmd_run_status(args)
        parser.parse_args(["run", "--help"])
        return 0

    if args.command == "story":
        if args.story_subcommand == "show":
            return cmd_story_show(args)
        parser.parse_args(["story", "--help"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
