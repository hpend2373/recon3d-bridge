#!/usr/bin/env python3
"""CLI usable from either the repository or an installed skill directory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from recon3d_bridge import APIError, ContractError, JevClient, load_instructions, prioritize
from recon3d_bridge.client import validate_request


def write_json(path: Path, value) -> None:
    """Atomically update reports so an interruption cannot create partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prompt = commands.add_parser("prompt", help="Export canonical instructions for any agent framework")
    prompt.add_argument("--json", action="store_true", help="Return a generic system-message object")
    for name in ("evaluate", "models", "prioritize"):
        sub = commands.add_parser(name)
        sub.add_argument("--provider", choices=("jev", "laya"), default="jev")
        sub.add_argument("--base-url", help="API base including /v1; default is official Jev or loopback Laya")
        sub.add_argument("--model", help="Requested model/alias")
        sub.add_argument("--timeout", type=float, default=30)
        sub.add_argument("--max-retries", type=int, default=2)
        if name != "models":
            sub.add_argument("--input", type=Path, required=True)
            sub.add_argument("--output", type=Path, required=True)
        if name == "evaluate":
            sub.add_argument("--dry-run", action="store_true", help="Validate and write request; make no API call")
        if name == "prioritize":
            sub.add_argument("--no-model", action="store_true", help="Retain the supplied full candidate order")
    args = parser.parse_args(argv)
    try:
        if args.command == "prompt":
            instructions = load_instructions()
            print(json.dumps({"role": "system", "content": instructions}, ensure_ascii=False) if args.json else instructions)
            return 0
        payload = None
        if args.command != "models":
            payload = json.loads(args.input.read_text(encoding="utf-8"))
        if args.command == "evaluate" and args.dry_run:
            validate_request(payload)
            write_json(args.output, payload)
            print("Request validated; no API call made.")
            return 0
        if args.command == "prioritize" and args.no_model:
            report = prioritize(payload, checkpoint=lambda report: write_json(args.output, report))
            print(f"Retained {report['candidate_count']} candidates; scientific review remains pending.")
            return 0
        laya = args.provider == "laya"
        api_key = os.environ.get("LAYA_API_KEY", "") if laya else None
        client = JevClient(base_url=args.base_url or ("http://127.0.0.1:8000/v1" if laya else "https://api.typesafe.ai/v1"),
                           api_key=api_key, model=args.model or ("laya" if laya else "jev-latest"),
                           timeout=args.timeout, max_retries=args.max_retries)
        if args.command == "models":
            print(json.dumps(client.list_models(), indent=2))
            return 0
        if args.command == "evaluate":
            validate_request(payload)
            if args.model:
                payload["model"] = args.model
            write_json(args.output, client.evaluate(**payload))
            print(f"Validated System One response saved to {args.output}")
            return 0
        report = prioritize(payload, client=client, checkpoint=lambda report: write_json(args.output, report))
        print(f"Scored {report['scored_count']}/{report['candidate_count']}; scientific review remains pending.")
        return 0 if report["guidance_complete"] else 1
    except (APIError, ContractError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
