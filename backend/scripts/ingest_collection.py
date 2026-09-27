"""Setowa CLI: Ingest a local collection of images and videos into Cloudinary & Setowa Workspace."""
import argparse
import json
import mimetypes
import os
import sys
from datetime import date
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.services import evidence_store as store
from app.services import media

SUPPORTED_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}


def ingest_directory(
    directory: Path,
    project_id: str,
    source: str,
    visit_date: str,
    permission_status: str = "granted",
) -> dict:
    if not directory.is_dir():
        raise ValueError(f"Directory '{directory}' does not exist or is not a directory")

    files = [
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort(key=lambda p: p.name)

    if not files:
        return {
            "total_found": 0,
            "successful": 0,
            "failed": 0,
            "results": [],
            "message": f"No supported media files found in '{directory}'",
        }

    with store.connection() as db:
        visit_id = store.ensure_ingestion_visit(db, project_id, visit_date)

    results = []
    successful = 0
    failed = 0

    for file_path in files:
        ext = file_path.suffix.lower()
        mime_type = SUPPORTED_EXTENSIONS.get(ext) or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        filename = file_path.name

        try:
            data = file_path.read_bytes()
            result = media.ingest_media(
                data=data,
                content_type=mime_type,
                project_id=project_id,
                source=source,
                visit_date=visit_date,
                original_filename=filename,
            )

            record = {
                "asset_id": result["asset_id"],
                "visit_id": visit_id,
                "public_id": result["public_id"],
                "version": result["version"],
                "secure_url": result["secure_url"],
                "source": source,
                "width": result.get("width") or 800,
                "height": result.get("height") or 600,
                "format": result.get("format") or ext.lstrip("."),
                "permission_status": permission_status,
                "thumbnail_url": result.get("thumbnail_url"),
                "site_id": project_id,
                "media_type": result.get("media_type") or "image",
                "processing_status": "ready",
                "original_filename": filename,
                "duration": result.get("duration"),
                "preview_url": result.get("preview_url"),
            }

            with store.connection() as db:
                store.save_asset(db, record)

            results.append({
                "filename": filename,
                "status": "success",
                "media_type": record["media_type"],
                "asset_id": record["asset_id"],
                "public_id": record["public_id"],
                "secure_url": record["secure_url"],
                "thumbnail_url": record["thumbnail_url"],
                "duration": record["duration"],
            })
            successful += 1
        except Exception as exc:
            results.append({
                "filename": filename,
                "status": "failed",
                "error": str(getattr(exc, "detail", exc)),
            })
            failed += 1

    return {
        "project_id": project_id,
        "visit_id": visit_id,
        "visit_date": visit_date,
        "total_found": len(files),
        "successful": successful,
        "failed": failed,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Setowa Media Pipeline: Bulk Ingest Images and Videos into Cloudinary and Setowa Workspace."
    )
    parser.add_argument("--dir", required=True, type=Path, help="Path to directory containing media files")
    parser.add_argument("--project", default="field-collection", help="Setowa project/site identifier (e.g. river-delta)")
    parser.add_argument("--source", default="Field Collection Sweep", help="Source attribution / collector name")
    parser.add_argument("--date", default=date.today().isoformat(), help="Collection date (YYYY-MM-DD)")
    parser.add_argument("--permission", default="granted", choices=["granted", "pending_verification", "revoked"], help="Permission status")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    summary = ingest_directory(
        directory=args.dir,
        project_id=args.project,
        source=args.source,
        visit_date=args.date,
        permission_status=args.permission,
    )

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print("=" * 64)
    print("SETOWA MEDIA PIPELINE — BULK INGESTION SUMMARY")
    print("=" * 64)
    print(f"Project:     {summary.get('project_id', args.project)}")
    print(f"Collection:  {summary.get('visit_date', args.date)}")
    print(f"Total Found: {summary.get('total_found', 0)}")
    print(f"Successful:  {summary.get('successful', 0)}")
    print(f"Failed:      {summary.get('failed', 0)}")
    print("-" * 64)

    for r in summary.get("results", []):
        if r["status"] == "success":
            kind = f"[{r['media_type'].upper()}]"
            dur = f" ({r['duration']:.1f}s)" if r.get("duration") else ""
            print(f"✓ {kind:8} {r['filename']}{dur}")
            print(f"         Public ID: {r['public_id']}")
            print(f"         Delivery:  {r['thumbnail_url']}")
        else:
            print(f"✗ [FAILED] {r['filename']}: {r.get('error')}")
    print("=" * 64)


if __name__ == "__main__":
    main()
