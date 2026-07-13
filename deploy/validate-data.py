#!/usr/bin/env python3
"""Validate externalized AI training cards without modifying them."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate(root: Path) -> dict:
    report = {"root": str(root), "categories": 0, "scenes": 0, "files": 0, "errors": [], "warnings": [], "info": []}
    digest = hashlib.sha256()
    if not root.is_dir():
        report["errors"].append("data root does not exist or is not a directory")
        report["sha256"] = digest.hexdigest()
        return report
    scene_names: dict[str, str] = {}
    category_dirs = sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))
    report["categories"] = len(category_dirs)
    if not category_dirs:
        report["errors"].append("data root contains no category directories")
    for category in category_dirs:
        scene_dirs = sorted(path for path in category.iterdir() if path.is_dir() and not path.name.startswith("."))
        if not scene_dirs:
            report["errors"].append(f"empty category: {category.name}")
        for scene in scene_dirs:
            rel = scene.relative_to(root).as_posix()
            files = sorted(path for path in scene.iterdir() if path.is_file())
            report["files"] += len(files)
            report["scenes"] += 1
            if not files:
                report["errors"].append(f"empty scene directory: {rel}")
                continue
            for path in files:
                if path.stat().st_size == 0:
                    report["errors"].append(f"empty file: {path.relative_to(root).as_posix()}")
            card_path = scene / "scene_card.json"
            if not card_path.is_file():
                report["errors"].append(f"missing scene_card.json: {rel}")
            else:
                try:
                    card = load_json(card_path)
                    if not isinstance(card, dict):
                        raise ValueError("root must be an object")
                    for field in ("scenario_name", "client_profile", "scoring_points"):
                        if not card.get(field):
                            report["errors"].append(f"missing required field {field}: {rel}/scene_card.json")
                    profile = card.get("client_profile")
                    if not isinstance(profile, dict) or not profile.get("role"):
                        report["errors"].append(f"client_profile.role is required: {rel}/scene_card.json")
                    scenario_name = str(card.get("scenario_name") or "").strip()
                    if scenario_name:
                        if scenario_name in scene_names:
                            report["errors"].append(f"duplicate scenario_name: {scenario_name} ({scene_names[scenario_name]}, {rel})")
                        scene_names[scenario_name] = rel
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    report["errors"].append(f"invalid scene card {rel}/scene_card.json: {type(exc).__name__}")
            knowledge_path = scene / "knowledge_cards.json"
            if not knowledge_path.is_file():
                report["warnings"].append(f"missing optional knowledge_cards.json: {rel}")
            else:
                try:
                    knowledge = load_json(knowledge_path)
                    if not isinstance(knowledge, (list, dict)):
                        raise ValueError("root must be an array or object")
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    report["errors"].append(f"invalid knowledge cards {rel}/knowledge_cards.json: {type(exc).__name__}")
            for path in files:
                if path.suffix.lower() == ".json":
                    digest.update(path.relative_to(root).as_posix().encode("utf-8"))
                    digest.update(path.read_bytes())
    report["sha256"] = digest.hexdigest()
    report["info"].append(f"validated {report['categories']} categories, {report['scenes']} scenes and {report['files']} files")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="../ai-visit-training/knowcard_output")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = validate(Path(args.path).expanduser().resolve())
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"data={report['root']} categories={report['categories']} scenes={report['scenes']} files={report['files']}")
        print(f"sha256={report['sha256']}")
        for item in report["errors"]:
            print(f"ERROR: {item}")
        for item in report["warnings"]:
            print(f"WARNING: {item}")
        for item in report["info"]:
            print(f"INFO: {item}")
        print("PASS" if not report["errors"] else "FAIL")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
