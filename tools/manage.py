#!/usr/bin/env python3
"""Install, validate, or package the same skill for native Agent Skills clients."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "recon3d-cross-cell-deg"
SOURCE = ROOT / "skills" / NAME
ORIGINAL_BYTES = 17107
ORIGINAL_SHA256 = "8c940dbced24938533ce69dc0260fa88159d6b49e4a33812bb871840ad76fdd8"
FRAMEWORK_PATHS = {
    "agents": Path(".agents/skills"),
    "codex": Path(".agents/skills"),
    "claude": Path(".claude/skills"),
    "cursor": Path(".cursor/skills"),
    "gemini": Path(".gemini/skills"),
}


def files_in(directory: Path) -> list[Path]:
    paths = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink is not allowed in a distribution: {path}")
        if "__pycache__" in path.parts or path.name == ".DS_Store" or path.suffix == ".pyc":
            continue
        if path.is_file():
            paths.append(path)
    return paths


def fingerprint(directory: Path) -> dict[str, str]:
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files_in(directory)}


def install(framework: str, *, home: Path | None = None, project: Path | None = None,
            destination: Path | None = None, replace: bool = False) -> dict:
    """Copy the complete skill. Different existing content requires --replace.

    destination is the skills parent directory, not the skill folder. Replaced
    content is moved outside the discovery directory to a recoverable backup.
    """
    parent = destination if destination is not None else (project or home or Path.home()) / FRAMEWORK_PATHS[framework]
    parent = parent.expanduser().absolute()
    target = parent / NAME
    if target.is_symlink():
        raise ValueError("existing skill is a symlink; choose an explicit destination")
    if target.exists():
        if not target.is_dir():
            raise ValueError("existing skill path is not a directory")
        if fingerprint(target) == fingerprint(SOURCE):
            return {"status": "unchanged", "path": str(target)}
        if not replace:
            raise ValueError("different skill already exists; use --replace to back it up and replace it")
    parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix=".recon3d-install-", dir=parent) as stage:
        staged = Path(stage) / NAME
        staged.mkdir()
        for source in files_in(SOURCE):
            relative = source.relative_to(SOURCE)
            output = staged / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
        if target.exists():
            backup_parent = parent.parent / "skill-backups"
            backup_parent.mkdir(parents=True, exist_ok=True)
            backup = backup_parent / f"{NAME}-{uuid.uuid4().hex}"
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
    return {"status": "installed", "path": str(target), "backup": str(backup) if backup else None}


def validate() -> dict:
    raw = (SOURCE / "SKILL.md").read_bytes()
    if hashlib.sha256(raw[:ORIGINAL_BYTES]).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("original skill text was changed")
    text = raw.decode("utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError("invalid skill frontmatter")
    fields = dict(line.split(":", 1) for line in parts[1].strip().splitlines())
    if fields.get("name", "").strip() != NAME or not 1 <= len(fields.get("description", "").strip()) <= 1024:
        raise ValueError("invalid skill name or description")
    manifests = [ROOT / "plugin.json", ROOT / ".codex-plugin/plugin.json", ROOT / ".claude-plugin/plugin.json"]
    versions = set()
    for path in manifests:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["name"] != NAME:
            raise ValueError("plugin identity mismatch")
        versions.add(manifest["version"])
    if len(versions) != 1:
        raise ValueError("plugin versions differ")
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    if marketplace["plugins"][0]["name"] != NAME or marketplace["plugins"][0]["source"] != "./":
        raise ValueError("marketplace source mismatch")
    if marketplace["plugins"][0]["version"] not in versions:
        raise ValueError("marketplace version mismatch")
    if json.loads(manifests[1].read_text())["skills"] != "./skills/":
        raise ValueError("Codex skill path mismatch")
    distribution_files = files_in(SOURCE)
    return {"status": "PASS", "version": versions.pop(), "skill_files": len(distribution_files),
            "skill_sha256": hashlib.sha256(raw).hexdigest(), "original_prefix_sha256": ORIGINAL_SHA256}


def pack(output: Path, *, kind: str = "plugin") -> dict:
    validate()
    output = output.expanduser().absolute()
    if output.exists():
        raise ValueError("output already exists; choose a new archive path")
    if output.is_relative_to(SOURCE):
        raise ValueError("archive must be outside the skill directory")
    sources = files_in(SOURCE)
    base = SOURCE
    if kind == "plugin":
        sources += [ROOT / "plugin.json"] + files_in(ROOT / ".codex-plugin")
        # A standalone plugin manifest is useful to Claude; marketplace is not
        # needed in the upload ZIP and remains in the GitHub repository.
        sources += [ROOT / ".claude-plugin/plugin.json"]
        base = ROOT
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(sources):
            archive.write(source, source.relative_to(base).as_posix())
    return {"path": str(output), "kind": kind, "files": len(sources),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    ins = commands.add_parser("install")
    ins.add_argument("--framework", choices=FRAMEWORK_PATHS, required=True)
    ins.add_argument("--project", type=Path, help="Install into a project instead of the local user home")
    ins.add_argument("--destination", type=Path, help="Explicit skills parent directory")
    ins.add_argument("--replace", action="store_true", help="Back up and replace different existing content")
    archive = commands.add_parser("pack")
    archive.add_argument("--kind", choices=("plugin", "skill"), default="plugin")
    archive.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = validate()
        elif args.command == "install":
            validate()
            result = install(args.framework, project=args.project, destination=args.destination, replace=args.replace)
        else:
            result = pack(args.output, kind=args.kind)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
