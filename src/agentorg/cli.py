"""User-facing CLI. No hidden side effects: team startup requires --apply."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from . import __version__
from .config import (OrgError, load_profiles, save_profiles, profiles_path, validate_id,
                     load_project, validate_project, known_projects, register_project, write_json, read_json, check_safe_text, template_document, resolve_role, project_file)
from .runtime import (blocked_info, redact_record, start_team, launch_agent_process, terminal_name, role_labels, hc_ready,
                      existing_terminal, run_process, validate_binaries, which, stop_team, inbox_pending,
                      install_protocol, task_states, team_warnings, cleanup_report, _active, pending_owner_decisions, watch_once, STALE_MINUTES,
                      resume_team, register_pm, resume_pm_process, discover_sessions)


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
    det = ps.add_parser("detect", help="Find logged-in Claude/Codex config dirs and Antigravity (existence checks only; reads no file contents)")
    det.add_argument("--add", action="store_true", help="Register every detected, unregistered entry whose command is found")
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
    setrole.add_argument("--title", help="Job title fitted to the project, e.g. 'Senior AI Scientist'")
    setrole.add_argument("--focus", help="What this role concentrates on in this project")
    routes = setrole.add_mutually_exclusive_group()
    routes.add_argument("--reviewer-role", help="Reviewer role for a worker (direct Worker → Reviewer reporting)")
    routes.add_argument("--clear-reviewer-role", action="store_true")
    group = setrole.add_mutually_exclusive_group()
    group.add_argument("--enable", action="store_true")
    group.add_argument("--disable", action="store_true")
    rs.add_parser("list").add_argument("--path", default=".")
    addrole = rs.add_parser("add", help="Add a role with a real job title; mode is only its level")
    addrole.add_argument("role", help="Role id, e.g. ai-scientist")
    addrole.add_argument("--mode", choices=("reviewer", "worker"), required=True)
    addrole.add_argument("--title", required=True)
    addrole.add_argument("--focus", required=True)
    addrole.add_argument("--profile", required=True)
    addrole.add_argument("--reviewer-role", help="Reviewer role for a worker")
    addrole.add_argument("--model")
    addrole.add_argument("--effort")
    addrole.add_argument("--path", default=".")
    rmrole = rs.add_parser("remove")
    rmrole.add_argument("role")
    rmrole.add_argument("--path", default=".")

    q = sub.add_parser("team", help="Plan, launch and monitor Herdr team")
    ts = q.add_subparsers(dest="op", required=True)
    for op in ("plan", "up", "status", "reconcile", "down", "watch", "cleanup"):
        a = ts.add_parser(op)
        a.add_argument("--path", default=".")
        if op == "up":
            a.add_argument("--no-panes", action="store_true", help="Do not show roles as panes in the current Herdr App tab")
        if op in ("up", "down", "cleanup"):
            a.add_argument("--apply", action="store_true", help="Required to actually create/stop worktrees and agents")
        if op in ("status", "reconcile", "watch"):
            a.add_argument("--stale-minutes", type=float, default=STALE_MINUTES, help="Minutes without task activity before a task is stale")
        if op == "watch":
            a.add_argument("--loop", action="store_true", help="Keep checking until interrupted")
            a.add_argument("--interval", type=int, default=60, help="Seconds between checks with --loop")
        if op == "down":
            a.add_argument("--remove-worktrees", action="store_true", help="git worktree remove (no --force) for stopped workers; branches are kept")
    a = ts.add_parser("smoke", help="Live end-to-end check with fake agents (no model tokens)")
    a.add_argument("--keep", action="store_true", help="Keep the temp project and terminals for inspection")
    a = ts.add_parser("send", help="Send scoped task to a role")
    a.add_argument("role")
    a.add_argument("message")
    a.add_argument("--path", default=".")
    a.add_argument("--wait", action="store_true")

    q = sub.add_parser("resume", help="After a restart: bring the team and PM back in their own panes and conversations")
    q.add_argument("--path", default=".")
    q.add_argument("--all", action="store_true", help="Every project that team up --apply recorded")
    q.add_argument("--apply", action="store_true", help="Required to actually restart agents")
    q.add_argument("--no-panes", action="store_true")
    q = sub.add_parser("pm", help="PM session bookkeeping")
    q.add_argument("op", choices=("register",))
    q.add_argument("--path", default=".")
    q.add_argument("--provider", choices=("claude", "codex", "antigravity"), help="Only when it cannot be detected from the environment")
    q.add_argument("--model", help="Your own model, so resume reopens you on it (else the provider default)")
    q.add_argument("--effort", help="Your own reasoning effort, for the same reason")

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
    q.add_argument("--session-id", help=argparse.SUPPRESS)
    q.add_argument("--resume", help=argparse.SUPPRESS)
    q = sub.add_parser("_resume_pm", help=argparse.SUPPRESS)
    q.add_argument("--project", required=True)
    q.add_argument("--profile-store", required=True, help=argparse.SUPPRESS)
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
        ".ai/STATE.md": "# Project checkpoint\n\n## Current milestone\nM0 — Foundations\n\n## Active tasks\nNone yet.\n\n## Open PRs/artifacts\nNone yet.\n\n## Blockers\nNone yet.\n\n## Handled escalations\nNone yet. The PM appends inbox ids here before moving files to inbox/done/.\n\n## Next action\nReview project scope and assign first scoped task.\n",
        ".ai/DECISIONS.md": "# Decisions\n\nRecord context, options, chosen action, evidence, and reversible/irreversible impacts.\n",
        "QUESTION.md": "# Questions for the human owner\n\nRecord only decisions requiring human approval, with options, recommendation and safe work while awaiting answer.\nOwner: write your answer after the `Answer:` line under each question.\n",
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
    protocol = install_protocol(root)
    if template.get("experimental"):
        print(f"WARNING: the {ns.template} template is experimental; only the software team (PM + worker + reviewer) is supported.", file=sys.stderr)
    print(json.dumps({"project": str(root), "created": created, "already_present": skipped, "protocol": protocol}, indent=2))


def profile_cmd(ns):
    profiles = load_profiles()
    if ns.op == "list":
        safe = {}
        for name, item in profiles.items():
            safe[name] = {k: v for k, v in item.items() if k in ("provider", "command", "model", "effort", "native_profile", "config_dir")}
        print(json.dumps({"profile_file": str(profiles_path()), "profiles": safe}, indent=2))
        return
    if ns.op == "detect":
        return detect_cmd(ns, profiles)
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
    profiles[ns.name] = build_profile(ns.provider, ns.executable, ns.config_dir, ns.native_profile, ns.model, ns.effort)
    save_profiles(profiles)
    print(f"Saved local-only profile '{ns.name}' at {profiles_path()} (no tokens stored).")


def build_profile(provider, executable, config_dir, native_profile, model, effort) -> dict:
    """Validate and build one profile record (shared by `profile add` and `profile detect --add`)."""
    if native_profile and provider != "codex":
        raise OrgError("--native-profile is supported for Codex only")
    if provider == "antigravity" and config_dir:
        raise OrgError("--config-dir is not supported for antigravity")
    for opt, value in (("model", model), ("effort", effort), ("native-profile", native_profile)):
        if value:
            check_safe_text(value, "--" + opt)
    resolved = None
    if config_dir:
        path = Path(config_dir).expanduser().resolve()
        if not path.is_dir():
            raise OrgError(f"Config directory does not exist: {path}")
        resolved = str(path)
    command = executable or ("agy" if provider == "antigravity" else provider)
    if not command or any(ch in command for ch in ("\n", "\r", "\0")):
        raise OrgError("Invalid executable command")
    if not which(command):
        raise OrgError(f"Executable not found: {command}. Use an installed CLI or full path to wrapper executable.")
    return {"provider": provider, "command": command, "config_dir": resolved,
            "native_profile": native_profile, "model": model, "effort": effort}


# (provider, default dir name, marker files/dirs; any one is enough)
_DETECT = (("claude", ".claude", ("settings.json", ".credentials.json", "projects")),
           ("codex", ".codex", ("config.toml", "auth.json")))


def detect_profiles(profiles: dict) -> list:
    """Existence checks only: no file under a config dir is ever opened."""
    home = Path.home()
    found = []
    for provider, base, markers in _DETECT:
        for entry in sorted(home.glob(base + "*"), key=lambda p: p.name):
            if entry.name != base and not entry.name.startswith(base + "-"):
                continue
            if not entry.is_dir() or not any((entry / m).exists() for m in markers):
                continue
            default = entry.name == base
            found.append({"alias": entry.name.lstrip("."), "provider": provider, "_dir": entry.resolve(), "_default": default,
                          "config_dir": None if default else str(entry.resolve())})
    if which("agy"):
        found.append({"alias": "antigravity", "provider": "antigravity", "config_dir": None, "_dir": None, "_default": True})
    for item in found:
        item["command_found"] = bool(which("agy" if item["provider"] == "antigravity" else item["provider"]))
        item["registered_as"] = None
        for name, prof in profiles.items():
            cfg = prof.get("config_dir")
            # A default dir is matched by a null config_dir or by a profile pointing at that dir explicitly.
            same = (cfg is None and item["_default"]) or (cfg is not None and item["_dir"] is not None and Path(cfg).resolve() == item["_dir"])
            if prof.get("provider") == item["provider"] and same:
                item["registered_as"] = name
                break
    return found


def detect_cmd(ns, profiles):
    found = detect_profiles(profiles)
    out = {"profiles": [{k: v for k, v in i.items() if not k.startswith("_")} for i in found]}
    if ns.add:
        added, skipped = [], []
        for item in found:
            alias = item["alias"]
            if item["registered_as"] or not item["command_found"]:
                continue
            try:
                validate_id(alias, "profile alias")
                if alias in profiles:
                    raise OrgError(f"alias '{alias}' is already used by a different profile")
                profiles[alias] = build_profile(item["provider"], None, item["config_dir"], None, None, None)
                added.append(alias)
            except OrgError as exc:
                skipped.append({"alias": alias, "reason": str(exc)})
        if added:
            save_profiles(profiles)
        out["added"] = added
        out["skipped"] = skipped
    print(json.dumps(out, indent=2))


def role_cmd(ns):
    root = rootpath(ns.path)
    doc = load_project(root)
    if ns.op == "list":
        print(json.dumps(doc["roles"], indent=2))
        return
    if ns.op == "add":
        validate_id(ns.role, "role id")
        validate_id(ns.profile, "profile alias")
        if any(r["id"] == ns.role for r in doc["roles"]):
            raise OrgError(f"Role '{ns.role}' already exists; use role set to change it")
        for opt in ("title", "focus"):
            if not getattr(ns, opt).strip():
                raise OrgError(f"--{opt} must not be empty")
        role = {"id": ns.role, "title": ns.title, "mode": ns.mode, "profile": ns.profile, "focus": ns.focus, "enabled": True}
        for opt in ("model", "effort"):
            if getattr(ns, opt):
                role[opt] = getattr(ns, opt)
        if ns.reviewer_role:
            role["reviewer_role"] = ns.reviewer_role
        doc["roles"].append(role)
    elif ns.op == "remove":
        resolve_role(doc, ns.role)
        users = [r["id"] for r in doc["roles"] if r.get("enabled", True) and r.get("reviewer_role") == ns.role]
        if users:
            raise OrgError(f"Cannot remove {ns.role}: enabled worker(s) {', '.join(users)} route to it. Re-route or remove them first.")
        doc["roles"] = [r for r in doc["roles"] if r["id"] != ns.role]
    if ns.op in ("add", "remove"):
        validate_project(doc)
        write_json(project_file(root), doc)
        print(f"{'Added' if ns.op == 'add' else 'Removed'} role {ns.role} in {project_file(root)}")
        return
    role = resolve_role(doc, ns.role)
    for opt in ("model", "effort", "title", "focus"):
        if getattr(ns, opt):
            check_safe_text(getattr(ns, opt), f"--{opt}")
    for opt in ("title", "focus"):
        if getattr(ns, opt):
            role[opt] = getattr(ns, opt)
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
    if ns.op in ("status", "watch"):
        register_project(root)  # teams created before 0.9.0 never ran team up --apply since
    if ns.op in ("plan", "up"):
        report = {}
        items = start_team(root, apply=(ns.op == "up" and ns.apply), panes=not getattr(ns, "no_panes", False), report=report)
        safe = [{k: v for k, v in item.items() if k != "command"} for item in items]
        for item, visible in zip(items, safe):
            if not (ns.op == "up" and ns.apply):
                visible["argv"] = item["command"]
        out = {"mode": "apply" if ns.op == "up" and ns.apply else "dry_run", "roles": safe}
        out.update(report)
        if doc.get("experimental"):
            out["experimental"] = True
        print(json.dumps(out, indent=2))
        if ns.op == "up" and not ns.apply:
            print("No agents started. Add --apply to launch.")
        return
    if ns.op == "cleanup":
        print(json.dumps({"mode": "apply" if ns.apply else "dry_run", "tasks": cleanup_report(root, apply=ns.apply)}, indent=2))
        if not ns.apply:
            print("Nothing removed. Add --apply to remove clean worktrees and delete merged branches.")
        return
    hc_ready()
    if ns.op == "down":
        items = stop_team(root, apply=ns.apply, remove_worktrees=ns.remove_worktrees)
        print(json.dumps({"mode": "apply" if ns.apply else "dry_run", "roles": items}, indent=2))
        if not ns.apply:
            print("Nothing stopped. Add --apply to stop the listed terminals.")
        return
    if ns.op == "watch":
        while True:
            print(json.dumps(watch_once(root, ns.stale_minutes)), flush=True)
            if not ns.loop:
                return
            time.sleep(max(ns.interval, 5))
    if ns.op == "send":
        role = resolve_role(doc, ns.role)
        name = terminal_name(root, role["id"])
        if existing_terminal(name, role_labels(root, role)) is None:
            raise OrgError(f"Role {role['id']} has no visible live terminal. Run team up --apply first.")
        busy = [t["id"] for t in task_states(root, full=True) if _active(t) and t["worker"] == role["id"] and t["id"] not in ns.message]
        if busy:
            print(f"WARNING: {role['id']} already has active task(s) {', '.join(busy)}; sending anyway.", file=sys.stderr)
        command = ["hc", "send"] + (["--wait"] if ns.wait else []) + [name, ns.message]
        result = run_process(command, timeout=220 if ns.wait else 90)
        if result.returncode not in (0, 124):
            raise OrgError(f"hc send failed: {result.stderr.strip() or result.stdout.strip()}")
        print(result.stdout.strip() or f"Send check-in returned {result.returncode}; inspect terminal before retry.")
        return
    status, blocked = [], []
    for role in doc["roles"]:
        if not role.get("enabled", True):
            continue
        name = terminal_name(root, role["id"])
        try:
            active = existing_terminal(name, role_labels(root, role))
            status.append({"role": role["id"], "terminal": name, "live": active is not None,
                           "details": redact_record(active) if active is not None else None})
            if blocked_info(role["id"], name, active):
                blocked.append(blocked_info(role["id"], name, active))
        except OrgError as exc:
            status.append({"role": role["id"], "terminal": name, "live": False, "details": None, "error": str(exc)})
    if ns.op == "reconcile":
        runtime = read_json(root / ".ai" / "RUNTIME.json", default={"schema_version": 2, "terminals": {}})
        for s in status:
            runtime.setdefault("terminals", {}).setdefault(s["role"], {}).update({"name": s["terminal"], "live": s["live"]})
        discover_sessions(runtime)
        write_json(root / ".ai" / "RUNTIME.json", runtime)
    tasks = task_states(root, getattr(ns, "stale_minutes", STALE_MINUTES), full=True)
    wake = read_json(root / ".ai" / "RUNTIME.json", default={}).get("watch_last_wake")
    print(json.dumps({"project": doc["project_id"], "inbox_pending": inbox_pending(root), "blocked": blocked, "warnings": team_warnings(doc, tasks),
                      "watcher_last_wake": wake, "owner_decisions": pending_owner_decisions(root), "tasks": [{k: v for k, v in t.items() if k not in ("worker", "paths")} for t in tasks], "status": status}, indent=2))


def resume_cmd(ns):
    roots = [rootpath(p) for p in known_projects() if (Path(p) / ".ai" / "TEAM.json").exists()] if ns.all else [rootpath(ns.path)]
    out = []
    if ns.all and not roots:
        print("No registered projects. Run agentorg resume once inside each project folder to register it.", file=sys.stderr)
    for root in roots:
        if not ns.all and (root / ".ai" / "TEAM.json").exists():
            register_project(root)
        try:
            out.append({"project": str(root), "roles": resume_team(root, apply=ns.apply, panes=not ns.no_panes)})
        except OrgError as exc:
            if not ns.all:
                raise
            out.append({"project": str(root), "error": str(exc)})
    print(json.dumps({"mode": "apply" if ns.apply else "dry_run", "projects": out}, indent=2))
    if not ns.apply:
        print("Nothing restarted. Add --apply to resume the listed agents.")


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
        elif ns.command == "resume":
            resume_cmd(ns)
        elif ns.command == "pm":
            print(json.dumps(register_pm(rootpath(ns.path), ns.provider, ns.model, ns.effort), indent=2))
        elif ns.command == "doctor":
            doctor(ns)
        elif ns.command == "install":
            install_skills(ns)
        elif ns.command == "_launch":
            os.environ["AGENTORG_HOME"] = str(rootpath(ns.profile_store))
            sys.exit(launch_agent_process(rootpath(ns.project), ns.role, ns.pm, ns.session_id, ns.resume))
        elif ns.command == "_resume_pm":
            os.environ["AGENTORG_HOME"] = str(rootpath(ns.profile_store))
            sys.exit(resume_pm_process(rootpath(ns.project)))
    except OrgError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
