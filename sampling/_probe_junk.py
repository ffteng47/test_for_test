import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path("plot_engine/tests/fixtures").resolve()))
from _probe_believes2 import draft_of, v34_patch, client, cfg, src, parse_proposals
from plot_engine.llm_extract import extract_prompt
from collections import Counter
for run_ch, ch in [("v4c2/ch03", 3), ("v4c3/ch10", 10)]:
    draft = draft_of(Path(f"sampling/{run_ch}.md"))
    msgs = v34_patch(extract_prompt(draft, None, src(ch, cfg.initial_state).contract, cfg.initial_state))
    text, _ = client.complete("extract", msgs)
    props, bad = parse_proposals(text, ch, cfg.initial_state)
    print(run_ch, "产出", len(props), "坏料", Counter(b["reason"] for b in bad), "样例", bad[:2])
