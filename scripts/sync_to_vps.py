#!/usr/bin/env python3
"""Incremental sync of Parquet files to VPS using manifest comparison.

Compares local manifest against the VPS manifest (fetched via SSH), then
rsyncs only the files whose MD5 hashes differ.

Usage:
    python scripts/sync_to_vps.py --host VPS_HOST [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# Allow imports from src/ when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.audit import create_audit_entry, write_audit_entry
from src.pipeline.manifest import (
    MANIFEST_FILENAME,
    compare_manifests,
    generate_manifest,
    save_manifest,
)


def fetch_remote_manifest(host: str, remote_data_dir: str, ssh_key: str | None = None) -> dict:
    """Fetch the manifest file from the remote VPS via SSH."""
    remote_path = f"{remote_data_dir}/{MANIFEST_FILENAME}"
    cmd = ["ssh"]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    cmd.extend([host, f"cat {remote_path} 2>/dev/null || echo '{{}}'"])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"Warning: Could not fetch remote manifest: {result.stderr.strip()}")
        return {}
    return json.loads(result.stdout)


def rsync_files(
    files: list[str],
    data_dir: Path,
    host: str,
    remote_data_dir: str,
    *,
    ssh_key: str | None = None,
    dry_run: bool = False,
) -> int:
    """Rsync specific files to the remote host. Returns bytes transferred."""
    if not files:
        return 0

    # Write file list to a temp file for --files-from
    filelist_path = data_dir / ".sync_filelist.tmp"
    filelist_path.write_text("\n".join(files) + "\n")

    cmd = [
        "rsync",
        "-avz",
        "--progress",
        f"--files-from={filelist_path}",
    ]
    if ssh_key:
        cmd.extend(["-e", f"ssh -i {ssh_key}"])
    if dry_run:
        cmd.append("--dry-run")

    cmd.extend([str(data_dir) + "/", f"{host}:{remote_data_dir}/"])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    filelist_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"rsync error: {result.stderr}", file=sys.stderr)
        return 0

    if not dry_run:
        print(result.stdout)

    # Estimate bytes from file sizes
    total_bytes = 0
    for f in files:
        fp = data_dir / f
        if fp.exists():
            total_bytes += fp.stat().st_size
    return total_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="VPS SSH host (e.g., user@hostname)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
        help="Local data directory",
    )
    parser.add_argument(
        "--remote-data-dir",
        default="/opt/noorinalabs-isnad-graph/data",
        help="Remote data directory on VPS",
    )
    parser.add_argument("--ssh-key", default=None, help="Path to SSH private key")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be transferred without doing it"
    )
    args = parser.parse_args()

    start = time.monotonic()

    # Generate current local manifest
    print("Generating local manifest...")
    local_manifest = generate_manifest(args.data_dir)
    if not local_manifest:
        print("No Parquet files found locally. Nothing to sync.")
        sys.exit(0)
    save_manifest(local_manifest, args.data_dir / MANIFEST_FILENAME)
    print(f"  {len(local_manifest)} files in local manifest.")

    # Fetch remote manifest
    print("Fetching remote manifest...")
    remote_manifest = fetch_remote_manifest(args.host, args.remote_data_dir, args.ssh_key)
    print(f"  {len(remote_manifest)} files in remote manifest.")

    # Compare
    diff = compare_manifests(local_manifest, remote_manifest)
    files_to_transfer = diff.changed_files

    print(f"\nFiles to transfer: {len(files_to_transfer)}")
    print(f"  Added:     {len(diff.added)}")
    print(f"  Modified:  {len(diff.modified)}")
    print(f"  Unchanged: {len(diff.unchanged)}")
    print(f"  Removed:   {len(diff.removed)}")

    if not files_to_transfer:
        print("\nAll files up-to-date. Nothing to transfer.")
        return

    # Estimate savings
    total_local_bytes = sum(e["size_bytes"] for e in local_manifest.values())
    transfer_bytes = sum(local_manifest[f]["size_bytes"] for f in files_to_transfer)
    saved_bytes = total_local_bytes - transfer_bytes

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Transferring {len(files_to_transfer)} files ({transfer_bytes:,} bytes)...")
    if saved_bytes > 0:
        print(f"{prefix}Bytes saved by skipping unchanged files: {saved_bytes:,}")

    bytes_sent = rsync_files(
        files_to_transfer,
        args.data_dir,
        args.host,
        args.remote_data_dir,
        ssh_key=args.ssh_key,
        dry_run=args.dry_run,
    )

    duration = time.monotonic() - start

    if not args.dry_run:
        # Push local manifest to remote so next sync can diff against it
        manifest_path = args.data_dir / MANIFEST_FILENAME
        scp_cmd = ["scp"]
        if args.ssh_key:
            scp_cmd.extend(["-i", args.ssh_key])
        scp_cmd.extend(
            [
                str(manifest_path),
                f"{args.host}:{args.remote_data_dir}/{MANIFEST_FILENAME}",
            ]
        )
        subprocess.run(scp_cmd, check=False)

        # Write audit entry
        file_details = []
        for f in files_to_transfer:
            entry = {"file": f, "md5_after": local_manifest[f]["md5"]}
            if f in remote_manifest:
                entry["md5_before"] = remote_manifest[f]["md5"]
            file_details.append(entry)

        audit = create_audit_entry(
            "sync",
            duration_seconds=round(duration, 2),
            files_changed=file_details,
            summary={
                "files_transferred": len(files_to_transfer),
                "files_skipped": len(diff.unchanged),
                "bytes_transferred": bytes_sent,
                "bytes_saved": saved_bytes,
            },
        )
        write_audit_entry(args.data_dir, audit)

    print(f"\nSync complete in {duration:.1f}s.")


if __name__ == "__main__":
    main()
