"""Release-drift guard: plugin manifests, the uvx pin in skills and __version__ must agree."""
import json
import re
import unittest
from pathlib import Path

import agentorg

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "agentorg" / "data"
PIN = "git+https://github.com/WeightForge/herdr-agent-org@v"


class PluginVersionTests(unittest.TestCase):
    def test_manifests_agree(self):
        v = agentorg.__version__
        for p in (".claude-plugin", ".codex-plugin", ".antigravity-plugin"):
            m = json.loads((DATA / p / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual((m["name"], m["version"]), ("agent-org", v), p)
        mp = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual([x["version"] for x in mp["plugins"]], [v])
        self.assertIn(f'version = "{v}"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_marketplaces_point_at_plugin_root(self):
        mp = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        cx = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        for src in (mp["plugins"][0]["source"], cx["plugins"][0]["source"]["path"]):
            self.assertTrue((ROOT / src / ".claude-plugin" / "plugin.json").is_file(), src)

    def test_skills_pin_matches_version(self):
        skills = sorted((DATA / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(skills), 4)
        for f in skills:
            pins = re.findall(re.escape(PIN) + r"([0-9][^ `]*)", f.read_text(encoding="utf-8"))
            self.assertEqual(pins, [agentorg.__version__], f.parent.name)


if __name__ == "__main__":
    unittest.main()
