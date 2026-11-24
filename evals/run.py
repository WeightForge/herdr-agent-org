#!/usr/bin/env python3
"""Skill evals: deterministic regex grading of what an agent says it would do next. No LLM judge, no execution.

    python evals/run.py --agent-cmd "agy --model gemini-4-hydrogen-medium --mode plan -p"

The prompt is appended to the command as one argv item. Only the fenced code block of the reply is graded.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agentorg import config, runtime  # noqa: E402

SKILLS = ROOT / "src" / "agentorg" / "data" / "skills"
PROTOCOL = ROOT / "src" / "agentorg" / "data" / "PROTOCOL.md"
TASK = ("Reply with the exact messages and commands you would send next, in order, inside ONE fenced code block, "
        "one per line, each as `RUN: <command>` or `SEND <target>: <message>` or `WRITE <path>: <content>`. "
        "Finish the block with the line `END TURN` if you would then stop and wait to be woken. Only that block is graded. Do not execute anything, call tools or touch files; this is an offline exercise.")


def actions(reply: str) -> str:
    blocks = re.findall(r"```[^\n]*\n(.*?)```", reply, flags=re.S)
    return "\n".join(blocks) if blocks else reply


def grade(reply: str, scenario: dict, subs: dict | None = None) -> dict:
    subs = subs or {}

    def fill(rx):
        for key, value in subs.items():
            rx = rx.replace(key, re.escape(value))
        return rx

    text = actions(reply)
    missing = [rx for rx in scenario.get("must_match", []) if not re.search(fill(rx), text)]
    forbidden = [rx for rx in scenario.get("must_not_match", []) if re.search(fill(rx), text)]
    return {"pass": not missing and not forbidden, "missing": missing, "forbidden": forbidden}


def load_scenarios(only=None):
    items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((Path(__file__).parent / "scenarios").glob("*.json"))]
    return [s for s in items if not only or s["name"] in only]


def project_context(tmp: Path):
    """A throwaway engineering project so reviewer/worker prompts are the real launch prompts."""
    proj = tmp / "demo"
    (proj / ".ai").mkdir(parents=True)
    doc = config.template_document("engineering")
    doc["project_id"] = "demo"
    config.write_json(config.project_file(proj), doc)
    subs = {"@PM@": "t1", "@REVIEWER@": runtime.terminal_name(proj, "technical-reviewer"),
            "@WORKER@": runtime.terminal_name(proj, "backend-worker")}
    return proj, doc, subs


def build_prompt(scenario: dict, proj: Path, doc: dict, subs: dict) -> str:
    if scenario["role"] == "pm":
        role = "You are the PM (project manager) agent for project demo. The human owner is the only authority for merge, release and deploy."
    else:
        role = runtime.make_agent_prompt(proj, config.resolve_role(doc, scenario["role_id"]), subs["@PM@"])
    skills = "\n\n".join((SKILLS / s / "SKILL.md").read_text(encoding="utf-8") for s in scenario["skills"])
    situation = scenario["situation"]
    for key, value in subs.items():
        situation = situation.replace(key, value)
    # The agent cannot read files in this offline exercise, so the protocol its prompt points to is inlined.
    protocol = PROTOCOL.read_text(encoding="utf-8")
    return f"=== YOUR ROLE ===\n{role}\n\n=== .ai/PROTOCOL.md ===\n{protocol}\n\n=== LOADED SKILLS ===\n{skills}\n\n=== SITUATION ===\n{situation}\n\n=== TASK ===\n{TASK}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent-cmd", required=True, help="command prefix; the prompt is appended as the last argument")
    ap.add_argument("--only", nargs="*", help="scenario names to run")
    ap.add_argument("--timeout", type=int, default=420)
    ns = ap.parse_args(argv)
    prefix = [a.strip('"') for a in shlex.split(ns.agent_cmd, posix=os.name != "nt")]
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        proj, doc, subs = project_context(Path(tmp))
        for scenario in load_scenarios(ns.only):
            prompt = build_prompt(scenario, proj, doc, subs)
            try:
                run = subprocess.run(prefix + [prompt], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=ns.timeout, stdin=subprocess.DEVNULL)
                reply = run.stdout
                result = grade(reply, scenario, subs) if run.returncode == 0 and reply.strip() else \
                    {"pass": False, "missing": [], "forbidden": [], "error": f"rc={run.returncode} {run.stderr.strip()[-200:]}"}
            except (OSError, subprocess.TimeoutExpired) as exc:
                reply, result = "", {"pass": False, "missing": [], "forbidden": [], "error": f"{type(exc).__name__}: {exc}"}
            results.append({"scenario": scenario["name"], **result, "reply": reply})
    for r in results:
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['scenario']}" + ("" if r["pass"] else f"  missing={r['missing']} forbidden={r['forbidden']} {r.get('error', '')}"))
    passed = sum(r["pass"] for r in results)
    print(f"\n{passed}/{len(results)} passed")
    print(json.dumps({"passed": passed, "total": len(results), "results": results}, indent=2))
    return 0 if results and passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
