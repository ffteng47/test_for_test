# 探针（一次性，不进正式尺）：同一批真实章正文，v3.3 判据 vs v3.4 草案各抽一遍，比 BELIEVES 检出与坏料归因。
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path("plot_engine/tests/fixtures").resolve()))
from plot_engine.llm import LlmClient
from plot_engine.llm_extract import extract_prompt, parse_proposals
from plot_engine.live import build_client
import experiment_10ch as fx


def draft_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## Draft\n(.*?)(?=^## )", text, re.S | re.M)
    return m.group(1).strip()


def v34_patch(messages):
    rules = messages[0]["content"].split("\n")
    out = []
    for line in rules:
        if line.startswith("类型按「该事实如何进入人物内心」选"):
            out.append(
                "类型按「该事实如何进入人物内心」选：OBSERVES=在场亲眼注意到；READS=读到写着的文字；"
                "IS_TOLD=被人当面告知；INFERS=本段里有证据→结论的推理动作（由已知证据推出）；"
                "BELIEVES=人物把某事实当作真来内心确认／坚信／心里认定（相信、认定、确信、知道真相是…），"
                "不需要本段给出新证据；SUSPECTS=起疑并把嫌疑指向某人/某事（会不会是、莫非、有嫌疑）；"
                "DOUBTS=明确怀疑或否定此前相信的事。内心确认与推理并存时两个都输出。")
        elif line.startswith("payload 必须给全这些键"):
            out.append(line)
            # W4b 裁定（tff，2026-10-14）：v3.4 草案曾在此追加一句数值键一律填某定值的指令，
            # 该指令令读数里的 700 分不清是模型真判断还是抄默认，构成双盲区，已删。
            # 缺省改由代码补并记 defaulted_fixed_point 账（生产面本就不写默认值）。
        else:
            out.append(line)
    return [{"role": "system", "content": "\n".join(out)}, messages[1]]


router_cfg = json.load(open("router_q25_14b.json", encoding="utf-8"))
client = build_client({r: dict(v, max_tokens=v.get("max_tokens", 1200)) for r, v in router_cfg.items()
                       if isinstance(v, dict)})
cfg = fx.make_config(10)
src = fx.build_source(None, cfg.arc_contract)

CASES = [("v4c1/ch09", 9), ("v4c2/ch09", 9), ("v4c3/ch02", 2)]
for run_ch, ch in CASES:
    draft = draft_of(Path(f"sampling/{run_ch}.md"))
    contract = src(ch, cfg.initial_state).contract
    base = extract_prompt(draft, None, contract, cfg.initial_state)
    for variant, msgs in (("v3.3", base), ("v3.4", v34_patch(base))):
        text, usage = client.complete("extract", msgs)
        props, bad = parse_proposals(text, ch, cfg.initial_state)
        types = {}
        for p in props:
            types[p.proposed_event_type] = types.get(p.proposed_event_type, 0) + 1
        badr = {}
        for b in bad:
            badr[b["reason"]] = badr.get(b["reason"], 0) + 1
        print(f"{run_ch} {variant}: 产出{len(props)} {types} | 坏料{badr}")
