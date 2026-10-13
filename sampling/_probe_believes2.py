# 探针 v2（一次性，不动正式尺）：扩样本的正/负对照 + malformed 归因 + 稳定性重检。
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path("plot_engine/tests/fixtures").resolve()))
from plot_engine.llm_extract import extract_prompt, parse_proposals
from plot_engine.live import build_client
import experiment_10ch as fx

_t = open(Path(__file__).parent / "_probe_believes.py", encoding="utf-8").read()
exec(_t[_t.index("def draft_of"):_t.index("router_cfg")])  # draft_of + v34_patch，不重放旧调用

client = build_client(json.load(open("router_q25_14b.json", encoding="utf-8")))
cfg = fx.make_config(10)
src = fx.build_source(None, cfg.arc_contract)


def run(run_ch: str, ch: int, variant: str):
    draft = draft_of(Path(f"sampling/{run_ch}.md"))
    contract = src(ch, cfg.initial_state).contract
    msgs = extract_prompt(draft, None, contract, cfg.initial_state)
    if variant == "v3.4":
        msgs = v34_patch(msgs)
    text, _ = client.complete("extract", msgs)
    props, bad = parse_proposals(text, ch, cfg.initial_state)
    diag = client.calls[-1]
    types = {}
    for p in props:
        types[p.proposed_event_type] = types.get(p.proposed_event_type, 0) + 1
    nails = {(m.field, m.target) for m in contract.must_change}
    anchored = {(p.proposed_event_type, p.payload.get("fact_id") or p.payload.get("conclusion_fact_id") or p.target)
                for p in props if p.proposed_event_type in ("BELIEVES", "SUSPECTS", "DOUBTS")}
    hit = sum(1 for t, f in anchored if ("belief" if t != "SUSPECTS" else "belief") in {n[0] for n in nails}
              and any(f == n[1] for n in nails))
    print(f"{run_ch} {variant}: 产出{len(props)} {types} | 坏料{len(bad)}"
          f" finish={diag.finish} 信念锚中Δ钉={hit}/{len([n for n in nails if n[0]=='belief'])}"
          f" 锚={sorted(a for _, a in anchored)}")


CASES = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
for run_ch, ch, variant in CASES:
    run(run_ch, ch, variant)
