import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path("plot_engine/tests/fixtures").resolve()))
from _probe_believes2 import draft_of, client, cfg, src, parse_proposals, extract_prompt


def v34b_patch(messages):
    rules = messages[0]["content"].split("\n")
    out = []
    for line in rules:
        if line.startswith("类型按「该事实如何进入人物内心」选"):
            out.append(
                "类型按「该事实如何进入人物内心」选：OBSERVES=在场亲眼注意到；READS=读到写着的文字；"
                "IS_TOLD=被人当面告知；INFERS=本段里有证据→结论的推理动作；"
                "BELIEVES=人物把某事实当作真来内心确认／坚信／心里认定（相信、认定、确信、知道真相是…），"
                "不需要本段给出新证据；SUSPECTS=起疑并把嫌疑指向某人/某事（会不会是、莫非、有嫌疑）；"
                "DOUBTS=明确怀疑或否定此前相信的事。内心确认与推理并存时两个都输出。")
        else:
            out.append(line)
    return [{"role": "system", "content": "\n".join(out)}, messages[1]]


for run_ch, ch in [("v4c1/ch02", 2), ("v4c2/ch03", 3), ("v4c2/ch07", 7), ("v4c2/ch09", 9)]:
    for variant in ("v3.3", "v3.4b"):
        draft = draft_of(Path(f"sampling/{run_ch}.md"))
        msgs = extract_prompt(draft, None, src(ch, cfg.initial_state).contract, cfg.initial_state)
        if variant == "v3.4b":
            msgs = v34b_patch(msgs)
        text, _ = client.complete("extract", msgs)
        props, bad = parse_proposals(text, ch, cfg.initial_state)
        types = {}
        for p in props:
            types[p.proposed_event_type] = types.get(p.proposed_event_type, 0) + 1
        print(f"{run_ch} {variant}: 产出{len(props)} {types} | 坏料{len(bad)} finish={client.calls[-1].finish}", flush=True)
