"""User-facing CLI. No hidden side effects: team startup requires --apply."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import (OrgError, load_profiles, save_profiles, profiles_path, validate_id,
                     load_project, validate_project, write_json, read_json, check_safe_text, template_document, resolve_role, project_file)
from .runtime import (start_team, launch_agent_process, terminal_name, role_labels, hc_ready,
                      existing_terminal, run_process, validate_binaries, which, stop_team, inbox_pending)


def add_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentorg", description="Herdr AI organization bootstrap, local profiles and team coordination")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("init", help="Create safe project manifests; never overwrite")
    q.add_argument("--path", default=".")
    q.add_argument("--name")
    q.add_argument("--template", choices=("engineering", "research", "content"), default="engineering")

    q = sub.add_parser("profile", help="Manage local-only provider profiles")
    ps = q.add_subparsers(dest="op", required=True)
    add = ps.add_parser("add", help="Create/update a named local profile")
    add.add_argument("name")
    add.add_argument("--provider", choices=("claude", "codex", "antigravity"), required=True)
    add.add_argument("--command", dest="executable", help="Executable name/path, not a shell alias")
    add.add_argument("--config-dir", help="CLAUDE_CONFIG_DIR or CODEX_HOME (not antigravity); no secret values")
    add.add_argument("--native-profile", help="Optional Codex --profile name")
    add.add_argument("--model")
    add.add_argument("--effort")
    add.add_argument("--replace", action="store_true", help="Explicitly replace existing profile")
    ps.add_parser("list")
    delete = ps.add_parser("remove")
    delete.add_argument("name")

    q = sub.add_parser("role", help="Configure project team role")
    rs = q.add_subparsers(dest="op", required=True)
    setrole = rs.add_parser("set")
    setrole.add_argument("role")
    setrole.add_argument("--path", default=".")
    setrole.add_argument("--profile")
    setrole.add_argument("--model")
    setrole.add_argument("--effort")
    routes = setrole.add_mutually_exclusive_group()
    routes.add_argument("--reviewer-role", help="Reviewer role for a worker (direct Worker → Reviewer reporting)")
    routes.add_argument("--clear-reviewer-role", action="store_true")
    group = setrole.add_mutually_exclusive_group()
    group.add_argument("--enable", action="store_true")
    group.add_argument("--disable", action="store_true")
    rs.add_parser("list").add_argument("--path", default=".")

    q = sub.add_parser("team", help="Plan, launch and monitor Herdr team")
    ts = q.add_subparsers(dest="op", required=True)
    for op in ("plan", "up", "status", "reconcile", "down"):
        a = ts.add_parser(op)
        a.add_argument("--path", default=".")
        if op in ("up", "down"):
            a.add_argument("--apply", action="store_true", help="Required to actually create/stop worktrees and agents")
        if op == "down":
            a.add_argument("--remove-worktrees", action="store_true", help="git worktree remove (no --force) for stopped workers; branches are kept")
    a = ts.add_parser("smoke", help="Live end-to-end check with fake agents (no model tokens)")
    a.add_argument("--keep", action="store_true", help="Keep the temp project and terminals for inspection")
    a = ts.add_parser("send", help="Send scoped task to a role")
    a.add_argument("role")
    a.add_argument("message")
    a.add_argument("--path", default=".")
    a.add_argument("--wait", action="store_true")

    q = sub.add_parser("doctor", help="Check local availability (no provider API calls)")
    q.add_argument("--path", default=".")
    q = sub.add_parser("install", help="Install skills in Claude Code, Codex, and/or Antigravity")
    q.add_argument("--target", choices=("claude", "codex", "antigravity", "both", "all"), default="both")
    q.add_argument("--force", action="store_true", help="Replace named skill folders")
    q = sub.add_parser("_launch", help=argparse.SUPPRESS)
    q.add_argument("--project", required=True)
    q.add_argument("--role", required=True)
    q.add_argument("--profile-store", required=True, help=argparse.SUPPRESS)
    q.add_argument("--pm", help=argparse.SUPPRESS)
    return p


def rootpath(value: str) -> Path:
    return Path(value).expanduser().resolve()


def init_project(ns):
    root = rootpath(ns.path)
    root.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9_-]+", "-", (ns.name or root.name).lower()).strip("-")[:40] or "project"
    if not slug[0].isalpha():
        slug = "p-" + slug[:38]
    validate_id(slug, "project name")
    template = template_document(ns.template)
    template["project_id"] = slug
    paths = {
        ".ai/TEAM.json": json.dumps(template, indent=2, ensure_ascii=False) + "\n",
        ".ai/PROJECT.md": f"# {ns.name or root.name}\n\n## Mission\nDescribe desired outcomes and users.\n\n## Non-goals\n- No publishing, deployment, or release without explicit human approval.\n\n## Constraints\nDocument important domain, legal, budget and system constraints.\n",
        ".ai/ROADMAP.md": "# Capability milestones (no dates required)\n\n## M0 — Foundations\n- [ ] Identify critical assumptions, tests, and dependencies\n\n## Next\n- [ ] Define first meaningful deliverable and acceptance criteria\n",
        ".ai/STATE.md": "# Project checkpoint\n\n## Current milestone\nM0 — Foundations\n\n## Active tasks\nNone yet.\n\n## Open PRs/artifacts\nNone yet.\n\n## Blockers\nNone yet.\n\n## Next action\nReview project scope and assign first scoped task.\n",
        ".ai/DECISIONS.md": "# Decisions\n\nRecord context, options, chosen action, evidence, and reversible/irreversible impacts.\n",
        "QUESTION.md": "# Questions for the human owner\n\nRecord only decisions requiring human approval, with options, recommendation and safe work while awaiting answer.\n",
        ".ai/.gitignore": "RUNTIME.json\ninbox/\n",
    }
    created, skipped = [], []
    for rel, content in paths.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            skipped.append(rel)
        else:
            p.write_text(content, encoding="utf-8", newline="\n")
            created.append(rel)
    print(json.dumps({"project": str(root), "created": created, "already_present": skipped}, indent=2))


def profile_cmd(ns):
    profiles = load_profiles()
    if ns.op == "list":
        safe = {}
        for name, item in profiles.items():
            safe[name] = {k: v for k, v in item.items() if k in ("provider", "command", "model", "effort", "native_profile", "config_dir")}
        print(json.dumps({"profile_file": str(profiles_path()), "profiles": safe}, indent=2))
        return
    validate_id(ns.name, "profile name")
    if ns.op == "remove":
        if ns.name not in profiles:
            raise OrgError(f"Unknown profile: {ns.name}")
        del profiles[ns.name]
        save_profiles(profiles)
        print(f"Removed local profile alias '{ns.name}' (credentials untouched).")
        return
    if ns.name in profiles and not ns.replace:
        raise OrgError(f"Profile '{ns.name}' exists; use --replace to update it")
    if ns.native_profile and ns.provider != "codex":
        raise OrgError("--native-profile is supported for Codex only")
    if ns.provider == "antigravity" and ns.config_dir:
        raise OrgError("--config-dir is not supported for antigravity")
    for opt in ("model", "effort", "native_profile"):
        if getattr(ns, opt):
            check_safe_text(getattr(ns, opt), "--" + opt.replace("_", "-"))
    config_dir = None
    if ns.config_dir:
        path = Path(ns.config_dir).expanduser().resolve()
        if not path.is_dir():
            raise OrgError(f"Config directory does not exist: {path}")
        config_dir = str(path)
    command = ns.executable or ("agy" if ns.provider == "antigravity" else ns.provider)
    if not command or any(ch in command for ch in ("\n", "\r", "\0")):
        raise OrgError("Invalid executable command")
    if not which(command):
        raise OrgError(f"Executable not found: {command}. Use an installed CLI or full path to wrapper executable.")
    profiles[ns.name] = {"provider": ns.provider, "command": command, "config_dir": config_dir,
                         "native_profile": ns.native_profile, "model": ns.model, "effort": ns.effort}
    save_profiles(profiles)
    print(f"Saved local-only profile '{ns.name}' at {profiles_path()} (no tokens stored).")


def role_cmd(ns):
    root = rootpath(ns.path)
    doc = load_project(root)
    if ns.op == "list":
        print(json.dumps(doc["roles"], indent=2))
        return
    role = resolve_role(doc, ns.role)
    for opt in ("model", "effort"):
        if getattr(ns, opt):
            check_safe_text(getattr(ns, opt), f"--{opt}")
    if ns.profile:
        validate_id(ns.profile, "profile alias")
        role["profile"] = ns.profile
    if ns.model:
        role["model"] = ns.model
    if ns.effort:
        role["effort"] = ns.effort
    if ns.reviewer_role:
        reviewer = resolve_role(doc, ns.reviewer_role)
        if role["mode"] != "worker" or reviewer["mode"] != "reviewer" or not reviewer.get("enabled", True):
            raise OrgError("--reviewer-role requires a worker role and an enabled reviewer role")
        role["reviewer_role"] = ns.reviewer_role
    if ns.clear_reviewer_role:
        role.pop("reviewer_role", None)
    if ns.disable:
        role["enabled"] = False
    if ns.enable:
        role["enabled"] = True
    validate_project(doc)  # never write a manifest that load_project would reject
    write_json(project_file(root), doc)
    print(f"Updated role {ns.role} in {project_file(root)}")


def doctor(ns):
    root = rootpath(ns.path)
    checks = {"python": sys.version.split()[0], "hc": bool(which("hc")), "git": bool(which("git")),
              "claude": bool(which("claude")), "codex": bool(which("codex")), "agy": bool(which("agy")), "project_initialized": project_file(root).exists()}
    if checks["project_initialized"]:
        doc = load_project(root)
        checks["project_id"] = doc["project_id"]
        checks["profile_issues"] = validate_binaries(doc, load_profiles())
    print(json.dumps(checks, indent=2))
    if checks.get("profile_issues"):
        raise OrgError("Resolve listed profile issues before team up")


def skill_sources():
    # In editable and wheel installs, skills are bundled as package data.
    from importlib.resources import files
    return files("agentorg").joinpath("data", "skills")


def install_skills(ns):
    if ns.target in ("claude", "both", "all"):
        claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
        targets = [claude_home / "skills"]
    else:
        targets = []
    if ns.target in ("codex", "both", "all"):
        targets.append(Path.home() / ".agents" / "skills")
    if ns.target in ("antigravity", "all"):
        targets.append(Path.home() / ".gemini" / "config" / "skills")
    src_root = skill_sources()
    names = ("agent-org-manager", "agent-org-engineering", "agent-org-bootstrap", "agent-org-recovery")
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            source = src_root.joinpath(name)
            dest = target / name
            if dest.exists():
                if not ns.force:
                    print(f"SKIP {dest} (exists; --force to replace)")
                    continue
                if dest.is_symlink() or dest.is_file():
                    raise OrgError(f"Refusing to overwrite non-directory skill path: {dest}")
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            dest.joinpath("SKILL.md").write_text(source.joinpath("SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
            print(f"INSTALLED {dest}")


def team_cmd(ns):
    if ns.op == "smoke":
        from .smoke import run_smoke
        report = run_smoke(keep=ns.keep)
        print(json.dumps(report, indent=2))
        if not report["ok"]:
            sys.exit(1)
        return
    root = rootpath(ns.path)
    doc = load_project(root)
    if ns.op in ("plan", "up"):
        items = start_team(root, apply=(ns.op == "up" and ns.apply))
        safe = [{k: v for k, v in item.items() if k != "command"} for item in items]
        for item, visible in zip(items, safe):
            if not (ns.op == "up" and ns.apply):
                visible["argv"] = item["command"]
        print(json.dumps({"mode": "apply" if ns.op == "up" and ns.apply else "dry_run", "roles": safe}, indent=2))
        if ns.op == "up" and not ns.apply:
            print("No agents started. Add --apply to launch.")
        return
    hc_ready()
    if ns.op == "down":
        items = stop_team(root, apply=ns.apply, remove_worktrees=ns.remove_worktrees)
        print(json.dumps({"mode": "apply" if ns.apply else "dry_run", "roles": items}, indent=2))
        if not ns.apply:
            print("Nothing stopped. Add --apply to stop the listed terminals.")
        return
    if ns.op == "send":
        role = resolve_role(doc, ns.role)
        name = terminal_name(root, role["id"])
        if existing_terminal(name, role_labels(root, role)) is None:
            raise OrgError(f"Role {role['id']} has no visible live terminal. Run team up --apply first.")
        command = ["hc", "send"] + (["--wait"] if ns.wait else []) + [name, ns.message]
        result = run_process(command, timeout=220 if ns.wait else 90)
        if result.returncode not in (0, 124):
            raise OrgError(f"hc send failed: {result.stderr.strip() or result.stdout.strip()}")
        print(result.stdout.strip() or f"Send check-in returned {result.returncode}; inspect terminal before retry.")
        return
    status = []
    for role in doc["roles"]:
        if not role.get("enabled", True):
            continue
        name = terminal_name(root, role["id"])
        try:
            active = existing_terminal(name, role_labels(root, role))
            status.append({"role": role["id"], "terminal": name, "live": active is not None,
                           "details": active if active is not None else None})
        except OrgError as exc:
            status.append({"role": role["id"], "terminal": name, "live": False, "details": None, "error": str(exc)})
    if ns.op == "reconcile":
        runtime = read_json(root / ".ai" / "RUNTIME.json", default={"schema_version": 2, "terminals": {}})
        for s in status:
            runtime.setdefault("terminals", {}).setdefault(s["role"], {}).update({"name": s["terminal"], "live": s["live"]})
        write_json(root / ".ai" / "RUNTIME.json", runtime)
    print(json.dumps({"project": doc["project_id"], "inbox_pending": inbox_pending(root), "status": status}, indent=2))


def main(argv=None):
    ns = add_parser().parse_args(argv)
    try:
        if ns.command == "init":
            init_project(ns)
        elif ns.command == "profile":
            profile_cmd(ns)
        elif ns.command == "role":
            role_cmd(ns)
        elif ns.command == "team":
            team_cmd(ns)
        elif ns.command == "doctor":
            doctor(ns)
        elif ns.command == "install":
            install_skills(ns)
        elif ns.command == "_launch":
            os.environ["AGENTORG_HOME"] = str(rootpath(ns.profile_store))
            sys.exit(launch_agent_process(rootpath(ns.project), ns.role, ns.pm))
    except OrgError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
