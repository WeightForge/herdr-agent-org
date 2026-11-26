"""Read-only discovery of installed provider skills.

Only skill folder names and the `name` / `description` frontmatter of each SKILL.md are read.
Nothing else under a provider config dir (auth, settings, tokens) is ever opened; the one
other files read are Claude's installed_plugins.json (plugin names and versions) and each plugin's
plugin.json manifest (its `skills` path only).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import SKILL_RE

BUILTIN_PREFIX = "agent-org-"  # our own skills: always present, never suggested
DESC_MAX = 120


def _frontmatter(path: Path) -> dict:
    """`name` and `description` from a SKILL.md header; plain, quoted and `>` / `|` block scalars."""
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as fh:
            head = fh.read(4096).splitlines()
    except OSError:
        return {}
    if not head or head[0].strip() != "---":
        return {}
    out, key = {}, None
    for line in head[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m and not line[0].isspace():
            key, val = m.group(1), m.group(2).strip()
            out[key] = "" if val in (">", "|", ">-", "|-") else val.strip("\"'")
        elif key and line.strip():
            out[key] = (out[key] + " " + line.strip()).strip()
    return {k: out.get(k, "") for k in ("name", "description")}


def _short(text: str) -> str:
    first = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    return first if len(first) <= DESC_MAX else first[:DESC_MAX - 3].rstrip() + "..."


def _item(skill_md: Path, fallback: str, source: str, prefix: str) -> dict:
    meta = _frontmatter(skill_md)
    name = meta.get("name") or fallback
    return {"name": prefix + name, "description": _short(meta.get("description", "")), "source": source,
            "builtin": name.startswith(BUILTIN_PREFIX)}


def _skills_in(folder: Path, source: str, prefix: str = "") -> list:
    """Skills in `<folder>/*/SKILL.md`."""
    try:
        entries = sorted(p for p in folder.iterdir() if p.is_dir())
    except OSError:
        return []
    return [_item(e / "SKILL.md", e.name, source, prefix) for e in entries if (e / "SKILL.md").is_file()]


def _installed_versions(path: Path) -> dict:
    """`plugin@marketplace` -> version from Claude's installed_plugins.json (names and versions only)."""
    try:
        plugins = json.loads(path.read_text(encoding="utf-8-sig")).get("plugins", {})
        return {k: v[0].get("version") for k, v in plugins.items() if isinstance(v, list) and v}
    except (OSError, ValueError, AttributeError, IndexError):
        return {}


def _manifest_skill_dirs(root: Path) -> list:
    """Skill folders a plugin declares in its manifest (`"skills": "./.claude/skills/"`, a string or list), else `skills/`.

    Live: ui-ux-pro-max keeps its skills under `.claude/skills`. Paths outside the plugin folder are ignored.
    """
    for manifest in (root / ".claude-plugin" / "plugin.json", root / ".codex-plugin" / "plugin.json"):
        try:
            declared = json.loads(manifest.read_text(encoding="utf-8-sig")).get("skills")
        except (OSError, ValueError, AttributeError):
            continue
        paths = [declared] if isinstance(declared, str) else declared if isinstance(declared, list) else []
        dirs = []
        for p in paths:
            if isinstance(p, str):
                d = (root / p).resolve()
                if d.is_relative_to(root.resolve()):
                    dirs.append(d)
        if dirs:
            return dirs
    return [root / "skills"]


def _plugin_skills(base: Path, qualify: bool, installed: dict) -> list:
    """Skills of the installed version of each plugin under `<base>/plugins/cache/<marketplace>/<plugin>/<version>`."""
    out = []
    for market in sorted(p for p in (base / "plugins" / "cache").glob("*") if p.is_dir()):
        for plugin in sorted(p for p in market.glob("*") if p.is_dir()):
            versions = [v for v in plugin.glob("*") if v.is_dir()]
            root = next((v for v in versions if v.name == installed.get(f"{plugin.name}@{market.name}")), None)
            if root is None and versions:
                # shortcut: newest by mtime when the installed version is unknown; wrong only if an older dir was touched later
                root = max(versions, key=lambda v: v.stat().st_mtime)
            if root is None:
                continue
            prefix = plugin.name + ":" if qualify else ""
            for folder in _manifest_skill_dirs(root):
                out += _skills_in(folder, plugin.name, prefix)
            if (root / "SKILL.md").is_file():
                out.append(_item(root / "SKILL.md", plugin.name, plugin.name, prefix))
    return out


def discover_skills(provider: str, config_dir=None, home=None) -> list:
    """Installed skills for one provider profile: [{name, description, source, builtin}], deduplicated by name."""
    home = Path(home) if home else Path.home()
    cfg = Path(config_dir) if config_dir else None
    if provider == "claude":
        base = cfg or home / ".claude"
        found = _skills_in(base / "skills", "user")
        found += _plugin_skills(base, True, _installed_versions(base / "plugins" / "installed_plugins.json"))
    elif provider == "codex":
        base = cfg or home / ".codex"
        found = _skills_in(base / "skills", "user") + _skills_in(home / ".agents" / "skills", "user")
        found += _plugin_skills(base, False, {})
    elif provider == "antigravity":
        base = home / ".gemini" / "config"
        found = _skills_in(base / "skills", "user")
        for plugin in sorted(p for p in (base / "plugins").glob("*") if p.is_dir()):
            found += _skills_in(plugin / "skills", plugin.name)
    else:
        return []
    seen, unique = set(), []
    for item in found:
        if item["name"] not in seen and SKILL_RE.fullmatch(item["name"]):
            seen.add(item["name"])
            unique.append(item)
    return unique
