"""Stand-in agent for `agentorg team smoke`: echoes what it was launched with, then every stdin line."""
import json
import os
import sys


def main() -> None:
    argv, tid = sys.argv[1:], os.environ.get("HC_TERMINAL_ID", "")
    prompt = argv[-1] if argv else ""
    print("FAKE AGENT START", flush=True)
    print("ARGV:", json.dumps(argv[:-1]), flush=True)
    print("PROMPT:", prompt, flush=True)
    print("HC_TERMINAL_ID:", tid, flush=True)
    out_dir = os.environ.get("AGENTORG_FAKE_DIR")
    if out_dir and tid:
        with open(os.path.join(out_dir, tid + ".json"), "w", encoding="utf-8") as handle:
            json.dump({"argv": argv[:-1], "prompt": prompt, "terminal": tid}, handle)
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        print("GOT:", line.rstrip("\r\n"), flush=True)


if __name__ == "__main__":
    main()
