"""`agentorg team smoke`: live end-to-end check against the running Herdr core, with fake agents (zero model tokens)."""
from __future__ import annotations

import contextlib
import io
import json
import os
import secrets
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from .config import OrgError, read_json, write_json, project_file
from .runtime import hc_ready, run_process, terminal_name, kill_and_remove, worktree_info

WIN = os.name == "nt"


def _script(path: Path, lines: list[str]) -> str:
    """Write a .cmd (Windows) or sh script. Env is set inside because `hc run` does not inherit it."""
    path = path.with_suffix(".cmd" if WIN else ".sh")
    path.write_text(("\r\n" if WIN else "\n").join((["@echo off"] if WIN else ["#!/bin/sh"]) + lines) + ("\r\n" if WIN else "\n"),
                    encoding="utf-8", newline="")
    if not WIN:
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def _set(key: str, value: str) -> str:
    return f'set "{key}={value}"' if WIN else f"export {key}='{value}'"


def _env(ctx: dict) -> dict:
    env = dict(os.environ)
    env.pop("HC_TERMINAL_ID", None)  # the smoke project must not adopt a caller's PM
    env["AGENTORG_HOME"] = str(ctx["home"])
    return env


def _agentorg(ctx: dict, *args, timeout=120):
    r = run_process([sys.executable, "-m", "agentorg", *args], cwd=ctx["proj"], env=_env(ctx), timeout=timeout)
    if r.returncode != 0:
        raise OrgError(f"agentorg {' '.join(args)} failed: {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stdout


def _json_out(text: str):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _hc_get(name: str) -> dict:
    r = run_process(["hc", "get", name, "--json"], timeout=20)
    data = json.loads(r.stdout or "{}")
    if r.returncode != 0:
        raise OrgError(f"hc get {name}: {r.stdout.strip() or r.stderr.strip()}")
    return data


def _wait(pred, timeout=30.0, step=0.5):
    end = time.monotonic() + timeout
    while True:
        value = pred()
        if value or time.monotonic() >= end:
            return value
        time.sleep(step)


def _need(cond, message):
    if not cond:
        raise AssertionError(message)


def _setup(ctx: dict) -> None:
    from .cli import init_project
    tmp, proj = ctx["tmp"], ctx["tmp"] / "smoke"
    ctx.update(proj=proj, home=tmp / "home", fake=tmp / "fake", pm_name="ao-smoke-pm-" + secrets.token_hex(3))
    for d in (proj, ctx["home"], ctx["fake"], tmp / "bin"):
        d.mkdir(parents=True, exist_ok=True)
    ctx["names"].append(ctx["pm_name"])
    shim = _script(tmp / "bin" / "fakeagent", [_set("AGENTORG_FAKE_DIR", str(ctx["fake"])),
                                               f'"{sys.executable}" -m agentorg._fake_agent ' + ('%*' if WIN else '"$@"')])
    profile = {"provider": "claude", "command": shim, "config_dir": None, "native_profile": None, "model": "fake-model", "effort": "low"}
    write_json(ctx["home"] / "profiles.json", {"schema_version": 1, "profiles": {"reviewer": profile, "implementer": dict(profile, provider="codex")}})
    run_process(["git", "init", "-q"], cwd=proj, timeout=30)
    with contextlib.redirect_stdout(io.StringIO()):
        init_project(SimpleNamespace(path=str(proj), name="smoke", template="engineering"))
    doc = read_json(project_file(proj))
    doc["roles"] = [r for r in doc["roles"] if r["id"] in ("technical-reviewer", "backend-worker")]
    write_json(project_file(proj), doc)
    ident = ["-c", "user.email=smoke@example.invalid", "-c", "user.name=agentorg-smoke"]
    for argv in (["git", *ident, "add", ".ai", "QUESTION.md"], ["git", *ident, "commit", "-qm", "smoke"]):
        r = run_process(argv, cwd=proj, timeout=30)
        if r.returncode != 0:
            raise OrgError(f"{' '.join(argv[-3:])} failed: {r.stderr.strip()}")
    ctx["rev"], ctx["wrk"] = terminal_name(proj, "technical-reviewer"), terminal_name(proj, "backend-worker")
    ctx["names"] += [ctx["rev"], ctx["wrk"]]
    ctx["worktree"] = worktree_info(proj, {"id": "backend-worker"})[0]


def _check(report: dict, name: str, fn) -> None:
    try:
        report[name] = {"pass": True, "detail": fn()}
    except Exception as exc:  # a failing check must never skip cleanup or later checks
        report[name] = {"pass": False, "error": f"{type(exc).__name__}: {exc}"}


def _run_checks(ctx: dict, report: dict, keep: bool) -> None:
    proj, tmp = ctx["proj"], ctx["tmp"]
    out, done = tmp / "up1.out", tmp / "up1.done"
    py = f'"{sys.executable}"'
    wrapper = _script(tmp / "bin" / "pm", [
        _set("AGENTORG_HOME", str(ctx["home"])),
        f'{py} -m agentorg team up --apply --path "{proj}" > "{out}" 2>&1',
        f'echo done > "{done}"',
        f'{py} -c "import time; time.sleep(900)"'])
    state = {}

    def up_in_pm():
        r = run_process(["hc", "run", "--bg", "--no-parent", "--name", ctx["pm_name"], "--cwd", str(proj), wrapper], timeout=45)
        _need(r.returncode == 0, f"hc run PM failed: {(r.stderr or r.stdout).strip()}")
        _need(_wait(done.exists, 150), "team up did not finish in the PM terminal")
        state["pm_id"] = _hc_get(ctx["pm_name"])["address"]
        rows = _json_out(out.read_text(encoding="utf-8", errors="replace"))["roles"]
        _need([x["action"] for x in rows] == ["launched", "launched"], f"unexpected actions: {[x['action'] for x in rows]}")
        return {"pm_terminal": state["pm_id"], "actions": {x["role"]: x["action"] for x in rows}}

    _check(report, "team_up_in_pm_terminal", up_in_pm)
    _need_pm = lambda: _need("pm_id" in state, "team up check failed; PM terminal unknown")

    def reviewer_parent():
        _need_pm()
        parent = _hc_get(ctx["rev"]).get("parent")
        _need(parent == state["pm_id"], f"reviewer parent {parent!r} != PM {state['pm_id']!r}")
        return parent

    def worker_parent():
        _need_pm()
        parent, rev_id = _hc_get(ctx["wrk"]).get("parent"), _hc_get(ctx["rev"])["address"]
        state["rev_id"] = rev_id
        _need(parent == rev_id, f"worker parent {parent!r} != reviewer {rev_id!r}")
        return parent

    def reviewer_prompt():
        _need_pm()
        rid = state.get("rev_id") or _hc_get(ctx["rev"])["address"]
        f = ctx["fake"] / (rid + ".json")
        _need(_wait(f.exists, 20), "reviewer fake agent never recorded its launch")
        prompt = json.loads(f.read_text(encoding="utf-8"))["prompt"]
        _need(f"hc send {state['pm_id']}" in prompt, "reviewer prompt lacks `hc send <pm id>`")
        return "prompt addresses the PM terminal"

    def worker_no_daemon():
        _need_pm()
        wid = _hc_get(ctx["wrk"])["address"]
        f = ctx["fake"] / (wid + ".json")
        _need(_wait(f.exists, 20), "worker fake agent never recorded its launch")
        argv = json.loads(f.read_text(encoding="utf-8"))["argv"]
        _need("--no-daemon" in argv, f"codex worker argv lacks --no-daemon: {argv}")
        return argv

    def second_up():
        rows = _json_out(_agentorg(ctx, "team", "up", "--apply", "--path", str(proj)))["roles"]
        _need(all(x["action"] == "reused" for x in rows), f"not reused: {[x['action'] for x in rows]}")
        return [x["action"] for x in rows]

    def send():
        token = "smoke-" + secrets.token_hex(4)
        _agentorg(ctx, "team", "send", "backend-worker", token, "--path", str(proj))
        read = lambda: f"GOT: {token}" in run_process(["hc", "read", ctx["wrk"], "--lines", "100"], timeout=20).stdout
        _need(_wait(read, 20), "worker terminal never showed GOT: <token>")
        return token

    def status():
        data = _json_out(_agentorg(ctx, "team", "status", "--path", str(proj)))
        _need(data["status"] and all(x["live"] and "error" not in x for x in data["status"]), f"not all live: {data['status']}")
        _need(data["inbox_pending"] == 0, "inbox_pending != 0")
        _need(data["blocked"] == [], f"blocked: {data['blocked']}")
        return {x["role"]: x["live"] for x in data["status"]}

    def reconcile():
        _need_pm()
        _agentorg(ctx, "team", "reconcile", "--path", str(proj))
        rt = read_json(proj / ".ai" / "RUNTIME.json")
        _need(rt.get("pm_terminal") == state["pm_id"], f"pm_terminal lost: {rt.get('pm_terminal')!r}")
        missing = [r for r, t in rt["terminals"].items() if not t.get("cwd") or t.get("live") is not True]
        _need(not missing, f"cwd/live missing for {missing}")
        return {"pm_terminal": rt["pm_terminal"], "roles": sorted(rt["terminals"])}

    def down():
        rows = _json_out(_agentorg(ctx, "team", "down", "--apply", "--remove-worktrees", "--path", str(proj)))["roles"]
        _need([x["action"] for x in rows] == ["stopped", "stopped"], f"actions: {[x['action'] for x in rows]}")
        wt = next(x for x in rows if x["role"] == "backend-worker").get("worktree")
        _need(wt == "removed", f"worktree: {wt}")
        for name in (ctx["rev"], ctx["wrk"]):
            r = run_process(["hc", "get", name, "--json"], timeout=20)
            _need(r.returncode != 0 or json.loads(r.stdout).get("state") != "live", f"{name} still live")
        return {x["role"]: x["action"] for x in rows}

    steps = [("reviewer_parent_is_pm", reviewer_parent), ("worker_parent_is_reviewer", worker_parent),
             ("reviewer_prompt_has_pm_address", reviewer_prompt), ("codex_worker_has_no_daemon", worker_no_daemon), ("second_up_all_reused", second_up),
             ("team_send_reaches_worker", send), ("team_status_all_live", status),
             ("reconcile_keeps_cwd_and_pm", reconcile)]
    if not keep:
        steps.append(("team_down", down))
    for name, fn in steps:
        _check(report, name, fn)


def _cleanup(ctx: dict) -> dict:
    problems = []
    for name in ctx["names"]:
        try:
            kill_and_remove(name)
        except OrgError as exc:
            problems.append(f"{name}: {exc}")
    wt = ctx.get("worktree")
    if wt and Path(wt).exists() and ctx.get("proj"):
        run_process(["git", "worktree", "remove", "--force", str(wt)], cwd=ctx["proj"], timeout=60)
    def force(func, path, *_):  # read-only .git objects on Windows
        os.chmod(path, stat.S_IWRITE)
        func(path)

    try:
        shutil.rmtree(ctx["tmp"], **({"onexc": force} if sys.version_info >= (3, 12) else {"onerror": force}))
    except OSError as exc:
        problems.append(f"rmtree: {exc}")
    if Path(ctx["tmp"]).exists():
        problems.append(f"temp dir not removed: {ctx['tmp']}")
    return {"ok": not problems, "problems": problems}


def _require_installed_package() -> None:
    """`hc run` does not inherit PYTHONPATH, so agents are launched through the installed package: it must be this one."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = run_process([sys.executable, "-c", "import agentorg; print(agentorg.__file__)"], cwd=tempfile.gettempdir(), env=env, timeout=30)
    found = Path(r.stdout.strip()).resolve().parent if r.returncode == 0 and r.stdout.strip() else None
    if found != Path(__file__).resolve().parent:
        raise OrgError(f"team smoke must run from an installed agentorg (pip install .); the installed one is {found}")


def run_smoke(keep: bool = False) -> dict:
    hc_ready()
    _require_installed_package()
    ctx = {"tmp": Path(tempfile.mkdtemp(prefix="agentorg-smoke-")).resolve(), "names": []}
    report = {"ok": False, "checks": {}}
    try:
        _setup(ctx)
        _run_checks(ctx, report["checks"], keep)
        report["ok"] = bool(report["checks"]) and all(c["pass"] for c in report["checks"].values())
    finally:
        if keep:
            report["kept"] = {"project": str(ctx["tmp"]), "terminals": ctx["names"]}
        else:
            report["cleanup"] = _cleanup(ctx)
            report["ok"] = report["ok"] and report["cleanup"]["ok"]
    return report
