"""§7.2 反事实回放：现有 draft × 修好的抽取提示 = 「这个洞值几个百分点」。

零采样成本：Writer 一步不跑，draft 取自 dump 的 `## Draft`（正文一字不改）；State 由
EventLog replay 到本章开工前，契约对那份 State 重新派生；判定只走 `reduce_commit`
（Stage 1+2，无副作用），一条 event 也不落盘。冻结面（`llm_extract.extract_prompt`）
一个字节没动——动它的代价是 T8/v3 的全部历史读数作废。

产出不是新基线，只是「洞的价格标签」：翻绿章数按**一阶**算，被翻绿的上游章一旦真提交，
后续章的 State 会变，那是二阶后效，这里不模拟（与 `docs/phase1-merged-plan-final.md` §6
里 T2 换算同一条局限，一并写进报告）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from plot_engine.eventlog import EventLog
from plot_engine.llm import LlmClient
from plot_engine.llm_extract import (extract_prompt, parse_proposals, _strip_markup)
from plot_engine.metrics import _section_body, metrics_from_dump
from plot_engine.models.proposal import EventProposal
from plot_engine.reduce import reduce_commit
from plot_engine.reducer import Reducer
from plot_engine.replay import replay_to_chapter
from plot_engine.store import StateStore

# 两张脸（docs/phase1-merged-plan-final.md §7.1）：类型漏抽 + target 挂错。都在提示词上。
_PROMPT_ADDITIONS = [
    "",
    "事件类型判别（本通道最容易抽错的两组，逐条对照）：",
    "1. 正文由已知的事推出新结论——出现「他想 / 意识到 / 明白了 / 显然 / 看来 / 也就是说 / 这说明」"
    "并跟着一句结论 → 必须单独给一条 INFERS，不要把整段压成 OBSERVES。"
    "INFERS 的 conclusion_fact_id = 他新推出的那条结论，evidence_fact_ids = 他据以推理的已知事实。",
    "2. 角色内心确认或明确起疑——「他确信 / 他认定 / 他觉得不对 / 他怀疑」→ BELIEVES / SUSPECTS，"
    "不是 OBSERVES，也不是 FACT_CONTRADICTED（后者只在正文写出某事实被证伪时用）。",
    "fact_id 归属：一条事件的 payload 只指向**该角色由此获得或改变的那条事实**，"
    "不是他顺带看到的另一条；同一段里有多条事实时，按上面的规则分开各给一条事件。",
]


def improved_extract_prompt(draft: str, scene_plan, contract, state) -> List[dict]:
    """冻结提示 + 两张脸的判别段；其余（不给答案键、段号、词表）逐字沿用。"""
    messages = extract_prompt(draft, scene_plan, contract, state)
    messages[0]["content"] += "\n" + "\n".join(_PROMPT_ADDITIONS)
    return messages


def improved_channel(client: LlmClient, *, max_items: int = 24):
    """与 `make_llm_channel` 同一条解析路径，只有提示词换了——差异才归得清。"""
    def channel(draft, scene_plan, contract, state) -> List[EventProposal]:
        text, usage = client.complete("extract", improved_extract_prompt(
            _strip_markup(draft), scene_plan, contract, state))
        channel.total_tokens += usage.total
        props, bad = parse_proposals(text, getattr(contract, "chapter_no", 0), state)
        if len(props) > max_items:
            bad.append({"reason": "over_cap", "item": len(props)})
            props = props[:max_items]
        channel.malformed.extend(bad)
        channel.produced += len(props)
        return props

    channel.total_tokens = 0
    channel.produced = 0
    channel.malformed: List[dict] = []
    return channel


def dump_draft(path: Path) -> str:
    return "\n".join(_section_body(path.read_text(encoding="utf-8").splitlines(),
                                   "Draft")).strip()


def dump_hard(path: Path) -> List[str]:
    """`## Findings` 里落盘的 HARD 行（原判据读数），形如 `H5.1: 必需事件 …`。"""
    return [ln[len("- HARD "):] for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.startswith("- HARD ")]


def replay_chapter(store: StateStore, log: EventLog, story_id: str, chapter: int,
                   contract, draft: str, channel) -> List[str]:
    """同一份 draft、同一份契约，只换抽取通道：返回反事实 HARD（空 = 本章会提交）。"""
    state = replay_to_chapter(store, log, Reducer(), story_id, chapter - 1)
    props = channel(draft, None, contract, state)
    rb = reduce_commit(state, props, contract, draft, state.epoch,
                       committed_event_ids=frozenset(
                           e.event_id for e in log.read_story(story_id)))
    after = [f"{f.rule_id} {f.message}" for f in rb.validation.hard_violations]
    after += [f"CONSISTENCY {f['code']}" for f in rb.consistency
              if f["severity"] == "hard"]
    return after


def required_types(path: Path) -> List[str]:
    """dump 第 4 行的 `required_events=[...]`：判「这章的残差属不属于抽取洞」的唯一依据。"""
    import ast

    for ln in path.read_text(encoding="utf-8").splitlines()[:4]:
        if "required_events=" in ln:
            return list(ast.literal_eval(ln.split("required_events=", 1)[1].split("]", 1)[0] + "]"))
    return []


_BLIND = ("INFERS", "BELIEVES", "DOUBTS", "SUSPECTS")   # §7.1 认定的洞涉类型


def attribute_flip(row: dict, req_types: List[str], before: List[str]) -> str:
    """翻绿 ≠ 洞补上了：新通道可能只是**抽得少了**。

    实测两种非洞翻绿：① 原残差是 dead actor（H1.1/I7），新通道不再给死人派事件 ⇒ 章自然绿；
    ② ARC 章原判死时 `## Findings` 是空的，翻绿原因只能从 required_events 读。
    分不清就把两种数并列给，别把「少抽」的价格写成「洞」的价格。
    """
    if row["verdict"] != "FLIP":
        return ""
    if any(t in _BLIND for t in req_types):
        return "洞"
    if any(code in line for line in before for code in ("H1.1", "I7")):
        return "非洞:少抽"
    return "非洞:未知"


def run(state_dir: Path, dump_dir: Path, chapters: List[int], model_config: dict,
        *, client: Optional[LlmClient] = None) -> Dict[str, object]:
    """逐章反事实：`chapters` 给章号，其余全从盘上那条链读回。"""
    from plot_engine.live import build_client, check_reachable
    from plot_engine.tests.fixtures import experiment_10ch as fx

    client = client or build_client(model_config)
    ok, msg = check_reachable(client)
    if not ok:
        return {"error": msg}

    cfg = fx.make_config(10)
    store = StateStore(str(state_dir / "state.db"))
    log = EventLog(str(state_dir / "event.db"))
    channel = improved_channel(client)

    rows = []
    for ch in chapters:
        path = dump_dir / f"ch{ch:02d}.md"
        draft = dump_draft(path)
        if not draft:
            rows.append({"chapter": ch, "before": ["（无 Draft：契约开工前判死）"],
                         "after": [], "verdict": "NO_DRAFT"})
            continue
        state = replay_to_chapter(store, log, Reducer(), cfg.story_id, ch - 1)
        contract = fx.contract_for(cfg.arc_contract, ch, state)
        after = replay_chapter(store, log, cfg.story_id, ch, contract, draft, channel)
        before = dump_hard(path)
        # 回放的对象**全是**处置章，所以「反事实全绿」本身就是翻绿，与原判据有没有落盘无关
        # （ARC_CONFLICT 章在 validate 之前判死，`## Findings` 是空的——把它读成 PASS_ALREADY
        # 会把该记的一章漏掉）。
        row = {"chapter": ch, "before": before, "after": after,
               "verdict": "FLIP" if not after else "STILL"}
        row["attribution"] = attribute_flip(row, required_types(path), before)
        rows.append(row)

    return {"rows": rows, "tokens": channel.total_tokens,
            "produced": channel.produced, "malformed": channel.malformed,
            "chain_tail": store.load_latest(cfg.story_id).state.chapter_no,
            "note": msg}


def price_run(state_dir: Path, dump_dir: Path, model_config: dict, *,
              client: Optional[LlmClient] = None) -> Tuple[List[dict], str]:
    """一个 run 目录 → 处置章回放 + **分口径**定价。没有头条数。

    三条纪律，每条都对应这轮实测里真实存在的自欺：
    1. 翻绿分「洞」与「非洞:少抽」两栏——把后者算进洞价就是把提示词写保守了当成缺陷修复。
    2. 链尾章不在 dump 的 OK 集合里 ⇒ 这条链被事后救援写过（`--rescue` 提交的章），
       它之后的章 pre-state 含人工 ⇒ 整章剔出数，不靠约定剔。
    3. 重议过的章（`contract_version`≥2）契约无法从 dump 重建，回放一律用 version-1 原契约；
       `renegotiate_contract` 只删 required_events ⇒ v1 更严 ⇒ 「洞」那一栏是**下界**。
    单次读数：同 draft 在 temp 0.2 下两次判过不同结果，逐章要重复取多数才算数（§7.3 golden test）。
    """
    from plot_engine.tests.fixtures import experiment_10ch as fx

    metrics = metrics_from_dump(dump_dir)
    disposed = [r.chapter_no for r in metrics.reads if r.bucket == "disposition"]
    result = run(state_dir, dump_dir, disposed, model_config, client=client)
    if "error" in result:
        return [], result["error"]

    rows = result["rows"]
    committed = {r.chapter_no for r in metrics.reads if r.trace_status == "OK"}
    tail = result.get("chain_tail")
    human_at = tail if isinstance(tail, int) and tail and tail not in committed else None
    comparable = [r for r in rows
                  if human_at is None or r["chapter"] <= human_at]
    holes = [r for r in comparable if r["attribution"] == "洞"]
    others = [r for r in comparable if r["verdict"] == "FLIP" and r["attribution"] != "洞"]

    generated = metrics.generated
    numerator = metrics.count("first_pass") + metrics.count("rewrite_rescued")
    share = f"{numerator / generated:.1%}" if generated else "0%"
    lines = [f"处置 {len(disposed)} 章｜可比 {len(comparable)} 章"
             + (f"（链尾第 {human_at} 章是事后救援提交，其后 {len(rows) - len(comparable)} 章剔出）"
                if human_at else ""),
             f"干净 E2 现值 {share}",
             f"洞价（下界，只算 required_events 含 INFERS/BELIEVES/DOUBTS/SUSPECTS 的翻绿）："
             f"+{len(holes)} 章 → {(numerator + len(holes)) / generated:.1%}"
             if generated else "洞价：无生成章",
             f"非洞翻绿（少抽/未知，**不进**上面的数）：{len(others)} 章"
             f"｜重议章用 v1 原契约，故为下界"]
    return comparable, "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="python -m plot_engine.counterfactual",
                                 description="§7.2 抽取洞的反事实定价（只读，不落盘）")
    ap.add_argument("run_dir", help="采样目录，含 state/ 与 dump/")
    ap.add_argument("--chapters", default=None, help="逗号分隔章号；缺省=全部处置章")
    ap.add_argument("--model-config", metavar="JSON", required=True)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)

    config = json.loads(ns.model_config) if ns.model_config.lstrip().startswith("{") \
        else json.loads(Path(ns.model_config.lstrip("@")).read_text(encoding="utf-8"))
    root = Path(ns.run_dir)
    if ns.chapters:
        chapters = [int(x) for x in re.split(r"[,\s]+", ns.chapters.strip()) if x]
        result = run(root / "state", root / "dump", chapters, config)
        print(json.dumps(result, ensure_ascii=False, indent=2) if ns.json else _render(result))
    else:
        from plot_engine.live import build_client, check_reachable
        client = build_client(config)
        rows, summary = price_run(root / "state", root / "dump", config, client=client)
        print(summary)
        print(_render({"rows": rows}))
    return 0


def _render(result: Dict[str, object]) -> str:
    lines = []
    for r in result.get("rows", []):
        tag = f"[{r['attribution']}]" if r.get("attribution") else ""
        lines.append(f"ch{r['chapter']:02d} {r['verdict']}{tag}"
                     + (f"｜原判据 {'; '.join(r['before']) or '—'}"
                        f"｜反事实 {'; '.join(r['after']) or '全绿'}"))
    if result.get("tokens") is not None:
        lines.append(f"tokens={result['tokens']} 产出提案={result['produced']} "
                     f"坏料={len(result['malformed'])}")
    return "\n".join(lines) or "（无处置章可回放）"


if __name__ == "__main__":
    raise SystemExit(main())
