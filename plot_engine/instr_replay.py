"""W5 回放 runner——instr-fix-01 的"跑"侧（任务单 1.txt）。

`instr.py`/`instr_cli.py` 只有评分与报告侧；本模块补上读 dump 出 run JSON 的一环，
让 `instr_cli` 有东西可吃。

钉死的口径（1.txt，tff 2026-10-14 批准）：

1. **读 `## Draft` 段**：正文取自冻结 dump，不重新生成（零生成）。
   contract/state 由夹具**离线派生**（`fx.contract_for` / `fx.plan_for`）。
   ⇒ 近似必须写明：v4 夹具的 id 词表来自静态 genesis，与 v4c 当年实跑的
   **输入词表相同**；但 `knowledge_forbidden`、`reader_signals` 等契约字段按
   **当前**夹具现值取。故本 runner 的读数只在"同一 runner + 同一次冻结 commit"
   内部可比（两跑求一致率），**不与任何 E2/§ 表并列，也不与 v4c 历史读数同表**。
2. **只作仪器读数**：产出的 run JSON 供 `instr_cli` 算波动与 2×2，绝不进
   readout / metrics / E2。硬隔离：本模块**不写任何 dump 目录**。
3. **车道三戳**：落盘元数据带 尺戳(instr_cli 用) + 仪器戳(instr-v2-local/cloud)
   + 车道(local/cloud)。只标尺戳会在 2×2 时把两条车道的数混进一张表。

run JSON 契约见 `instr_cli.load_run`：
    {"chapters": {ch: [{"type","actor","target","payload","source_ref"}, ...]},
     "malformed": [{"reason","chapter"}], "tokens": int, "recall": float,
     "instr": "instr-v2-...", "ruler": "v3.5-..."}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_DRAFT_RE = re.compile(r"^## Draft\n(.*?)(?=^## )", re.S | re.M)


def draft_from_dump(path) -> str:
    """冻结 dump 里 `## Draft` 与下一个 `## ` 之间的正文（去掉 markup 交给抽取通道）。"""
    text = Path(path).read_text(encoding="utf-8")
    m = _DRAFT_RE.search(text)
    if not m:
        raise ValueError(f"{path} 里没有 ## Draft 段")
    return m.group(1).strip()


def frozen_corpus(runs: Sequence[str], chapters: Sequence[int]) -> List[Tuple[str, int, str]]:
    """[(跑法名, 章号, draft 路径)]；缺章显式报错，不静默跳过（静默=分母失真）。"""
    out = []
    for run in runs:
        for ch in chapters:
            p = REPO / "sampling" / run / f"ch{ch:02d}.md"
            if not p.exists():
                raise FileNotFoundError(f"冻结语料缺章：{p}")
            out.append((run, ch, str(p)))
    return out


def replay(lane_client, *, runs: Sequence[str], chapters: Sequence[int],
           lane: str = "local", seg_max_chars: int = 1800,
           seg_overlap: int = 200, log=print) -> Dict[str, object]:
    """把冻结语料跑一遍 instr-v2 抽取通道，出 run JSON 结构。

    `lane_client`：已建好的 LlmClient（本地/云端）。零生成——只调 extract 角色。
    """
    if str(REPO) not in sys.path:                      # 夹具在 repo 根的 sampling/ 旁
        sys.path.insert(0, str(REPO))
    from plot_engine.llm_extract import (EXTRACTION_RULER,
                                         make_segmented_llm_channel)
    from plot_engine.tests.fixtures import experiment_10ch as fx

    cfg = fx.make_config(max(chapters))
    src = fx.build_source(None, cfg.arc_contract)

    by_ch: Dict[int, list] = {}
    malformed: List[dict] = []
    total_tokens = 0
    for run, ch, path in frozen_corpus(runs, chapters):
        draft = draft_from_dump(path)
        art = src(ch, cfg.initial_state)
        ch_obj = make_segmented_llm_channel(lane_client, lane=lane,
                                            seg_max_chars=seg_max_chars,
                                            seg_overlap=seg_overlap)
        props = ch_obj(draft, None, art.contract, cfg.initial_state)
        total_tokens += ch_obj.total_tokens
        # 段内 paragraph 是段内编号；落盘时统一重映射回全局段号，便于跨段对齐
        for p in props:
            m = re.fullmatch(r"para:(\d+)#seg:(\d+)", p.source_ref or "")
            if m:
                p = p.model_copy(update={"source_ref": p.source_ref})
        by_ch.setdefault(ch, []).extend(props)
        for b in ch_obj.malformed:
            malformed.append({k: v for k, v in b.items() if k != "raw"})
        log(f"  {run} ch{ch:02d}: {len(props)} 条 | 段 {ch_obj.segments_run} "
            f"| tokens {ch_obj.total_tokens} | 坏料 {len(ch_obj.malformed)}")

    # 按**请求的章全集**落盘：跑了但 0 提案的章也要在（空集 vs 空集的 Jaccard 是 1.0，
    # 而缺章会让一致率的分母悄悄少一格——E5「累计当终值」的同族病）。
    # JSON 的 dict key 只能是字符串，instr_cli.load_run 会 int() 回来归一化。
    return {"chapters": {ch: [_prop_json(p) for p in by_ch.get(ch, [])]
                         for ch in sorted(set(by_ch) | set(chapters))},
            "malformed": malformed,
            "tokens": total_tokens,
            "recall": 0.0,
            "instr": ch_obj.instr_version,
            "ruler": EXTRACTION_RULER,
            "lane": lane,
            "runs": list(runs),
            "segment": {"max_chars": seg_max_chars, "overlap": seg_overlap}}


def _prop_json(p) -> dict:
    return {"type": p.proposed_event_type, "actor": p.actor, "target": p.target,
            "payload": dict(p.payload), "source_ref": p.source_ref}


def write_run(data: Dict[str, object], out) -> str:
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return str(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="W5 回放 runner：冻结 dump -> instr-v2 抽取 -> run JSON（零生成）")
    ap.add_argument("--runs", required=True,
                    help="逗号分隔的冻结跑法名，例 v4c1,v4c2,v4c3")
    ap.add_argument("--chapters", required=True,
                    help="逗号分隔章号，例 2,6,9")
    ap.add_argument("--out", required=True, help="run JSON 落盘路径")
    ap.add_argument("--client", required=True,
                    help='跑法配置 JSON 或 @路径，例 @router_w5_frozen.json')
    ap.add_argument("--lane", choices=["local", "cloud"], default="local")
    ap.add_argument("--seg-max-chars", type=int, default=1800)
    ap.add_argument("--seg-overlap", type=int, default=200)
    ap.add_argument("--force", action="store_true",
                    help="覆盖已存在的 --out（默认拒绝：两会话同参并跑会互相吞读数，"
                         "review.py 的 state.db 链护栏同理）")
    # `python -m` 时 argv 为 None，必须回落 sys.argv[1:]（instr_cli 同款修法，
    # 漏了就会「参数明明传了却报缺参数」——试水第一跑就是这么炸的）
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    if Path(args.out).exists() and not args.force:
        # 拒覆盖在烧 GPU 之前——两个会话同参并跑时，后写完的那个会静默吞掉先落的读数。
        sys.exit(f"拒收：{args.out} 已存在（可能是另一个会话的产物）。"
                 f"确认要覆盖加 --force，或换 --out 路径")
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from plot_engine.live import build_client

    spec = args.client
    raw = (Path(spec[1:]).read_text(encoding="utf-8-sig")
           if spec.startswith("@") else
           (Path(spec).read_text(encoding="utf-8-sig")
            if not spec.lstrip().startswith("{") else spec))
    cfg = json.loads(raw)
    # 配置里的 `_comment` 等注释键不是端点：顶层是字符串、段内是键，两种都会让
    # from_config 炸（ValueError: dictionary update sequence）。约定：下划线开头
    # 的键一律视为注释，runner 侧剥掉；不动 from_config 的既有语义。
    if isinstance(cfg, dict):
        cfg = {role: ({k: v for k, v in fields.items() if not k.startswith("_")}
                      if isinstance(fields, dict) else fields)
               for role, fields in cfg.items() if not role.startswith("_")}
    client = build_client(cfg)
    data = replay(client, runs=args.runs.split(","), chapters=[int(c) for c in
                  args.chapters.split(",")], lane=args.lane,
                  seg_max_chars=args.seg_max_chars, seg_overlap=args.seg_overlap)
    path = write_run(data, args.out)
    n = sum(len(v) for v in data["chapters"].values())
    print(f"已落档 {path}｜{len(data['chapters'])} 章 {n} 条提案｜"
          f"tokens {data['tokens']}｜仪器 {data['instr']}｜尺 {data['ruler']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
