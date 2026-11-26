"""Configuration, validation and conservative persistent storage."""
from __future__ import annotations

import json
import os
import re
import tempfile
from importlib.resources import files
from pathlib import Path

ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
SKILL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")  # ':' allows plugin-qualified names
MAX_ROLE_SKILLS = 8
PROVIDERS = {"claude", "codex", "antigravity"}
ROLE_MODES = {"worker", "reviewer", "researcher", "observer"}
AUTONOMY = ("full", "supervised")


class OrgError(Exception):
    """Actionable, user-safe CLI error."""


def org_home() -> Path:
    override = os.environ.get("AGENTORG_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "herdr-agent-org"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "herdr-agent-org"


def profiles_path() -> Path:
    return org_home() / "profiles.json"


def known_projects() -> list:
    return read_json(org_home() / "projects.json", default={"projects": []}).get("projects", [])


def register_project(root: Path):
    """Remember a project root so `agentorg resume --all` can find it. Local paths only."""
    projects = known_projects()
    if str(root.resolve()) not in projects:
        write_json(org_home() / "projects.json", {"schema_version": 1, "projects": [*projects, str(root.resolve())]})


def read_json(path: Path, *, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise OrgError(f"Missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OrgError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data, *, overwrite=True, private=False):
    if not overwrite and path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    fd, tempname = tempfile.mkstemp(prefix=".tmp-agentorg-", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(raw)
        if private and os.name != "nt":
            os.chmod(tempname, 0o600)
        os.replace(tempname, path)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)
    return True


def load_profiles() -> dict:
    doc = read_json(profiles_path(), default={"schema_version": 1, "profiles": {}})
    if not isinstance(doc, dict) or not isinstance(doc.get("profiles"), dict):
        raise OrgError("Bad local profiles.json: expected {profiles: {...}}")
    return doc["profiles"]


def save_profiles(profiles: dict):
    write_json(profiles_path(), {"schema_version": 1, "profiles": profiles}, private=True)


def validate_id(value: str, label: str):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise OrgError(f"Invalid {label} '{value}'. Use lowercase a-z, digits, - or _; start with a letter; max 40 chars.")


def validate_skills(value, label: str):
    if not isinstance(value, list) or len(value) > MAX_ROLE_SKILLS or len(set(map(str, value))) != len(value):
        raise OrgError(f"{label} skills must be a list of at most {MAX_ROLE_SKILLS} unique skill names")
    for name in value:
        if not isinstance(name, str) or not SKILL_RE.fullmatch(name):
            raise OrgError(f"Invalid skill name '{name}' for {label}. Use letters, digits, - _ . and : (plugin:skill); max 64 chars.")


def check_safe_text(value, label: str):
    """Reject text that cmd.exe would interpret when it reaches a .cmd shim argv."""
    if not isinstance(value, str) or any(c in value for c in '"%&|<>^') or any(ord(c) < 32 for c in value):
        raise OrgError(f"{label} must be a string without any of \" % & | < > ^ or control characters")


def project_file(root: Path) -> Path:
    return root / ".ai" / "TEAM.json"


def load_project(root: Path) -> dict:
    return validate_project(read_json(project_file(root)))


def validate_project(doc) -> dict:
    if not isinstance(doc, dict) or doc.get("schema_version") != 2:
        raise OrgError("TEAM.json requires schema_version: 2")
    validate_id(doc.get("project_id"), "project_id")
    if doc.get("kind") not in ("software", "research", "content", "general"):
        raise OrgError("Project kind must be software, research, content, or general")
    if doc.get("autonomy", "supervised") not in AUTONOMY:
        raise OrgError("autonomy must be full or supervised")
    roles = doc.get("roles")
    if not isinstance(roles, list) or not roles:
        raise OrgError("TEAM.json must contain at least one role")
    seen = set()
    for role in roles:
        if not isinstance(role, dict):
            raise OrgError("Every team role must be an object")
        rid = role.get("id")
        validate_id(rid, "role id")
        if rid in seen:
            raise OrgError(f"Duplicate role id: {rid}")
        seen.add(rid)
        validate_id(role.get("profile"), f"profile alias for role {rid}")
        if role.get("mode") not in ROLE_MODES:
            raise OrgError(f"Role {rid} has unsupported mode")
        if role.get("enabled", True) not in (True, False):
            raise OrgError(f"Role {rid} enabled must be bool")
        for opt in ("title", "focus", "model", "effort"):
            if opt in role:
                check_safe_text(role[opt], f"Role {rid} {opt}")
        if "skills" in role:
            validate_skills(role["skills"], f"Role {rid}")
        for opt in ("model", "effort"):
            if opt in role and not role[opt].strip():
                raise OrgError(f"Role {rid} optional {opt} must be a nonempty string")
    # Review routing is optional for backwards compatibility. If supplied, fail fast
    # when a worker points to an invalid or disabled reviewer.
    by_id = {role["id"]: role for role in roles}
    for role in roles:
        reviewer_id = role.get("reviewer_role")
        if reviewer_id is None:
            continue
        if role.get("mode") != "worker":
            raise OrgError(f"Role {role['id']}: reviewer_role is only valid on worker roles")
        if not role.get("enabled", True):
            continue  # a disabled worker may keep a stale route
        reviewer = by_id.get(reviewer_id)
        if reviewer is None or reviewer.get("mode") != "reviewer" or not reviewer.get("enabled", True):
            raise OrgError(f"Role {role['id']}: reviewer_role must name an enabled reviewer role")
    policies = doc.get("policies", {})
    if not isinstance(policies, dict) or not isinstance(policies.get("max_parallel_workers", 1), int) or policies.get("max_parallel_workers", 1) < 1:
        raise OrgError("policies.max_parallel_workers must be a positive integer")
    return doc


def autonomy(doc: dict) -> str:
    """A project without the field keeps the pre-0.8 behavior."""
    return doc.get("autonomy", "supervised")


def template_document(name: str):
    if name not in ("engineering", "research", "content"):
        raise OrgError("Unknown template; choose engineering, research or content")
    raw = files("agentorg").joinpath("data", name + ".json").read_text(encoding="utf-8")
    return json.loads(raw)


def resolve_role(doc: dict, role_id: str) -> dict:
    for role in doc["roles"]:
        if role["id"] == role_id:
            return role
    raise OrgError(f"Unknown role: {role_id}")


def resolve_profile(role: dict, profiles: dict) -> dict:
    name = role["profile"]
    if name not in profiles:
        raise OrgError(f"Missing local profile '{name}' for role {role['id']}. Use agentorg profile add {name} ...")
    profile = profiles[name]
    if profile.get("provider") not in PROVIDERS:
        raise OrgError(f"Invalid provider in local profile '{name}'")
    if not isinstance(profile.get("command"), str) or not profile["command"].strip():
        raise OrgError(f"Profile '{name}' has no command")
    return profile
