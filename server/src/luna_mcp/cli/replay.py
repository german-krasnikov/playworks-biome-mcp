"""Replay a recorded MCP session.

Usage: python -m luna_mcp.cli.replay <session_name> [--dry-run]

NOTE: Live replay requires a running MCP server stack (Chrome + bridge).
Standalone CLI invocation supports only --dry-run for now.
"""
import argparse
import asyncio
import pathlib
import sys


async def main():
    parser = argparse.ArgumentParser(description="Replay a recorded Playworks Biome session")
    parser.add_argument("name", help="Session name (without .jsonl)")
    parser.add_argument("--dry-run", action="store_true", help="Print steps without executing")
    parser.add_argument("--data-dir", default=None, help="Base path for recordings")
    args = parser.parse_args()

    from luna_mcp.config import data_dir as _data_dir
    base = pathlib.Path(args.data_dir).expanduser() / "recordings" if args.data_dir else _data_dir() / "recordings"
    path = base / f"{args.name}.jsonl"

    if not path.exists():
        print(f"recording not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Replaying {path}, dry_run={args.dry_run}", file=sys.stderr)

    from luna_mcp.record.replayer import Replayer
    from luna_mcp.tools.batch import dispatch as batch_dispatch
    replayer = Replayer(batch_dispatch)
    report = await replayer.replay(path, dry_run=args.dry_run)
    if report.diverged_at >= 0:
        print(f"DIVERGED at step {report.diverged_at}/{report.total}: {report.divergence_reason}")
        for line in report.summary[-5:]:
            print(line)
        sys.exit(2)
    print(f"OK {report.ok_steps}/{report.total} steps")
    for line in report.summary[-3:]:
        print(line)


if __name__ == "__main__":
    asyncio.run(main())
