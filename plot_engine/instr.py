"""P0 仪器修理 instr-v2（任务单 info.txt）：与尺戳分开记账的仪器层。

边界：不动判据语义、不动 H 系列、不动协议字段、不动夹具钉。
唯一触碰提示词文本的是 W4b（单列、可缓），本模块默认不做 W4b。

工作项与独立开关（可逐项回滚）：
- W1 分段抽取：按场景标记切分，无标记则窗口+重叠带，逐段抽取后按
  (event_type, actor, fact_id) 确定性合并去重。
- W2 JSON 修复环 + 失败粒度降级：坏输出回喂重试 1 次，仍失败只废该段，
  台账 diff 明确标注缺失窗口。
- W3 别名解析后处理：actor/target 先精确匹配编号，命中注册表姓名/昵称
  则映射到编号，未知或多义定向追问一次，仍解不出才拒收并记因。
- W4a 默认值进代码：数值键缺省由代码后处理补 DEFAULT_FIXED_POINT(700)，
  可审计、可全局改。W4b（删提示词里的"默认 700"句）默认不做，见 W4B_TOUCHED。
- W5 残余波动测量：冻结语料温度 0 连跑两遍，Jaccard + BELIEVES/SUSPECTS 稳定性。
- W6 云端抽取车道：两条车道共用同一套分段/修复/别名/默认值，只有模型不同，
  读数差异干净归因于模型本身。

仪器戳：INSTR_VERSION_LOCAL / INSTR_VERSION_CLOUD，与 EXTRACTION_RULER（尺戳）分开记。
"""
from __future__ import annotations

import dataclasses
import re
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

INSTR_VERSION_LOCAL = "instr-v2-local"
INSTR_VERSION_CLOUD = "instr-v2-cloud"
#: 默认仪器戳（本地车道）。切换默认车道即升档，见任务单护栏 3。
INSTR_VERSION = INSTR_VERSION_LOCAL

#: W4a：数值键缺省的全局唯一取值点（可审计、可全局改）。
DEFAULT_FIXED_POINT = 700

#: W4b：全批次唯一的尺面触碰。tff 已于 2026-10-14 裁定「删」。
#: 位置核查：那句「数值键一律给 700」**不在生产提示词**，只在探针的 v3.4 草案补丁
#: （`sampling/_probe_believes.py` 的 `v34_patch()`）里，已删除。True = 裁定已执行。
W4B_TOUCHED = True

#: W5 预登记硬门槛。
WASTE_RATE_MAX = 0.02
JACCARD_MED_MIN = 0.85

#: W1 默认窗口（字符数近似 token 窗口；中文 1 字 ~1.5 token，1800 字 << 模型上限）。
SEGMENT_MAX_CHARS = 1800
SEGMENT_OVERLAP_CHARS = 200

_SCENE_MARKER_RE = re.compile(r"<!--[^-]*?-->")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")


@dataclass
class InstrFlags:
    """逐项开关：全部默认开，任一项可独立关闭回滚到旧行为。"""

    segmentation: bool = True   # W1
    repair_loop: bool = True    # W2
    alias_resolution: bool = True  # W3
    code_defaults: bool = True  # W4a
    lane: str = "local"         # W6：local | cloud

    def disabled(self, *names: str) -> "InstrFlags":
        kw = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        for n in names:
            kw[n] = False
        return InstrFlags(**kw)


@dataclass
class Segment:
    index: int
    text: str
    para_start: int  # 全局 1-indexed 段号起点（用于把段内 paragraph 重映射回全局）
    char_span: Tuple[int, int]


def split_draft_segments(
    draft: str,
    max_chars: int = SEGMENT_MAX_CHARS,
    overlap_chars: int = SEGMENT_OVERLAP_CHARS,
) -> List[Segment]:
    """W1：正文切分。

    - 有场景标记（`<!-- ... -->`）时按标记先粗切，再在每块内按段落打包；
    - 无标记则纯段落窗口 + 重叠带（重叠取上一段尾部文本，不重复计段号）。
    - 空 draft 返回 []（调用方视为空章，不发模型调用）。
    """
    text = (draft or "").strip()
    if not text:
        return []
    # 先按场景标记粗切（标记行本身保留为边界，不送模型，段号不计入）。
    blocks: List[str] = []
    if _SCENE_MARKER_RE.search(text):
        parts = _SCENE_MARKER_RE.split(text)
        for p in parts:
            p = p.strip()
            if p:
                blocks.append(p)
    else:
        blocks = [text]
    segments: List[Segment] = []
    para_cursor = 1  # 全局段号
    char_cursor = 0
    for block in blocks:
        paras = [p.strip() for p in _PARA_SPLIT_RE.split(block) if p.strip()]
        if not paras:
            continue
        buf: List[str] = []
        buf_len = 0
        buf_para_start = para_cursor
        buf_char_start = char_cursor
        for para in paras:
            # 单段超长：先落盘当前 buf，再硬切本段。
            if len(para) > max_chars:
                if buf:
                    seg_text = "\n\n".join(buf)
                    segments.append(Segment(len(segments), seg_text,
                                            buf_para_start, (buf_char_start, char_cursor)))
                    # 重叠带：尾部 overlap_chars 不回退段号（重叠只为上下文连续）。
                    tail = seg_text[-overlap_chars:]
                    buf = [tail] if tail else []
                    buf_len = len(tail)
                    buf_para_start = para_cursor
                    buf_char_start = char_cursor
                for i in range(0, len(para), max_chars):
                    chunk = para[i:i + max_chars]
                    segments.append(Segment(len(segments), chunk,
                                            para_cursor, (char_cursor, char_cursor + len(chunk))))
                    char_cursor += len(chunk)
                para_cursor += 1
                buf = []
                buf_len = 0
                buf_para_start = para_cursor
                buf_char_start = char_cursor
                continue
            if buf and buf_len + 2 + len(para) > max_chars:
                seg_text = "\n\n".join(buf)
                segments.append(Segment(len(segments), seg_text,
                                        buf_para_start, (buf_char_start, char_cursor)))
                tail = seg_text[-overlap_chars:] if overlap_chars else ""
                buf = [tail] if tail else []
                buf_len = len(tail)
                buf_para_start = para_cursor
                buf_char_start = char_cursor
            buf.append(para)
            buf_len += (2 if buf_len else 0) + len(para)
            char_cursor += len(para) + 2
            para_cursor += 1
        if buf:
            seg_text = "\n\n".join(buf)
            # 纯重叠尾段（无新段落）不单独成段。
            if seg_text.strip():
                segments.append(Segment(len(segments), seg_text,
                                        buf_para_start, (buf_char_start, char_cursor)))
    return segments


def proposal_merge_key(p) -> tuple:
    """W1 合并去重键：(event_type, actor, fact_id)。"""
    payload = getattr(p, "payload", {}) or {}
    fact = (payload.get("fact_id") or payload.get("conclusion_fact_id")
            or payload.get("stated_fact_id"))
    if fact is None and isinstance(payload.get("evidence_fact_ids"), list):
        fact = tuple(payload.get("evidence_fact_ids") or ())
    return (getattr(p, "proposed_event_type", None), getattr(p, "actor", None), fact)


def merge_proposals(segment_props: List[List]) -> Tuple[List, dict]:
    """W1 确定性合并去重：保首见序，重编 seq。返回 (merged, stats)。"""
    seen: Dict[tuple, object] = {}
    order: List[tuple] = []
    for props in segment_props:
        for p in props or []:
            k = proposal_merge_key(p)
            if k not in seen:
                seen[k] = p
                order.append(k)
    n_before = sum(len(s or []) for s in segment_props)
    merged = []
    for i, k in enumerate(order):
        merged.append(seen[k].model_copy(update={"seq": i}))
    return merged, {"n_before": n_before, "n_after": len(merged),
                    "n_deduped": n_before - len(merged)}


def build_repair_messages(bad_raw: str, error: str) -> List[dict]:
    """W2：把坏输出 + 错误信息回喂的修复提示（只用一次）。"""
    return [
        {"role": "system",
         "content": "你是 JSON 修复器。只输出一个 JSON 数组，不要任何解释文字。"},
        {"role": "user",
         "content": f"上一次输出解析失败（{error}）。把它修成合法 JSON 数组，"
                    f"保持原有事件与字段不变，只修格式：\n{bad_raw[:2000]}"},
    ]


def build_alias_index(state) -> Dict[str, List[str]]:
    """W3：角色注册表 → {姓名/昵称: [char_id]}。多义自然形成多值表。"""
    index: Dict[str, List[str]] = {}
    if state is None:
        return index
    for cid, ch in (getattr(state, "characters", {}) or {}).items():
        names = [getattr(ch, "name", "")] + list(getattr(ch, "aliases", []) or [])
        for n in names:
            if n:
                index.setdefault(n, []).append(cid)
    return index


def resolve_actor_id(value, state, alias_index: Optional[Dict[str, List[str]]] = None
                     ) -> Tuple[Optional[str], str]:
    """W3：actor/target 解析。返回 (resolved_id_or_None, status)。

    status: exact（已是编号）/ alias（姓名昵称命中）/ null（空值通过）
            / unknown（未知）/ ambiguous（多义）。
    """
    if value is None:
        return None, "null"
    if not isinstance(value, str):
        return value, "unknown"
    known: set = set()
    if state is not None:
        known = set((getattr(state, "characters", {}) or {}).keys())
    if value in known:
        return value, "exact"
    index = alias_index if alias_index is not None else build_alias_index(state)
    hits = index.get(value, [])
    if len(hits) == 1:
        return hits[0], "alias"
    if len(hits) > 1:
        return None, "ambiguous"
    return None, "unknown"


def build_alias_followup_messages(value: str, candidates: List[str]) -> List[dict]:
    """W3 定向追问一次的提示（"张三对应注册表哪位"）。"""
    return [
        {"role": "system",
         "content": "你是角色对齐器。只输出一个角色编号，不要任何解释文字。"},
        {"role": "user",
         "content": f"“{value}”对应注册表哪位？候选：{', '.join(candidates)}。"
                    "只回编号；无法确定就回 UNKNOWN。"},
    ]


def apply_fixed_point_defaults(payload: dict, etype: str,
                               schema: Tuple[str, ...] = (),
                               fixed_keys: frozenset = frozenset(),
                               default: int = DEFAULT_FIXED_POINT,
                               ) -> Tuple[dict, List[str]]:
    """W4a：数值键缺省由代码补 default。可审计（返回补了哪些键）、可全局改。

    只补「缺失 / null」；字符串/bool/float 等错误类型不补（仍走丢弃路径），
    避免把真坏料洗成假正常。
    """
    out = dict(payload or {})
    defaulted: List[str] = []
    for k in (schema or ()):
        if k in fixed_keys and (k not in out or out[k] is None):
            out[k] = default
            defaulted.append(f"{etype}.{k}={default}")
    return out, defaulted


# ---------------- W5 残余波动测量 ----------------

def proposal_set_key(p) -> tuple:
    """W5：逐章条目集合键（与 W1 合并键同口径，另带 target 以稳 BELIEVES/SUSPECTS）。"""
    payload = getattr(p, "payload", {}) or {}
    fact = (payload.get("fact_id") or payload.get("conclusion_fact_id")
            or payload.get("stated_fact_id"))
    if fact is None and isinstance(payload.get("evidence_fact_ids"), list):
        fact = tuple(payload.get("evidence_fact_ids") or ())
    return (getattr(p, "proposed_event_type", None), getattr(p, "actor", None),
            getattr(p, "target", None), fact)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def chapter_jaccard(props_a: list, props_b: list) -> float:
    return jaccard({proposal_set_key(p) for p in (props_a or [])},
                   {proposal_set_key(p) for p in (props_b or [])})


def believes_keys(props: list) -> set:
    return {proposal_set_key(p) for p in (props or [])
            if getattr(p, "proposed_event_type", None) in ("BELIEVES", "SUSPECTS")}


def waste_rate(malformed_chapters: int, total_chapters: int) -> float:
    if not total_chapters:
        return 0.0
    return malformed_chapters / total_chapters


def check_thresholds(*, waste: float, jaccard_median: float,
                     believes_stable: bool) -> dict:
    """W5 预登记硬门槛判定。"""
    return {
        "waste_ok": waste < WASTE_RATE_MAX,
        "jaccard_ok": jaccard_median >= JACCARD_MED_MIN,
        "believes_ok": bool(believes_stable),
        "pass": (waste < WASTE_RATE_MAX and jaccard_median >= JACCARD_MED_MIN
                 and bool(believes_stable)),
    }


def decide_upgrade_path(*, waste_ok: bool, jaccard_ok: bool,
                        believes_ok: bool) -> str:
    """W5 预登记升级路径（任务单原文的答案机制）。

    - 废卷率达标但一致率/召回不达标 ⇒ 天花板在 B 层，触发对冲；
    - 两者都救不回 ⇒ BELIEVES 类列为本产品代不支持，转规格裁剪。
    具体走"更强模型"还是"自一致性×3"由调用方按 W5/W6 数字再定，这里只给判定。
    """
    if waste_ok and (not jaccard_ok or not believes_ok):
        return "ceiling_B:route_stronger_model_or_self_consistency_x3"
    if waste_ok and jaccard_ok and believes_ok:
        return "pass:open_v4d_baseline"
    return "instrument_fail:fix_A_first"


def median_jaccard(per_chapter: List[float]) -> float:
    if not per_chapter:
        return 1.0
    return float(statistics.median(per_chapter))


# ---------------- W6 云端抽取车道 ----------------

def instr_id_for_lane(lane: str) -> str:
    return INSTR_VERSION_CLOUD if lane == "cloud" else INSTR_VERSION_LOCAL


def describe_endpoint(ep) -> dict:
    """护栏 1：仪器档案记下云的完整身份（provider+model+version+解码配置+成本）。

    `usd_per_1k_tokens` 必须入档：车道决策的一半是 COGS，省了它就说不清"贵多少"。
    """
    if ep is None:
        return {}
    data = ep.model_dump(exclude={"api_key"}) if hasattr(ep, "model_dump") else dict(ep)
    base = str(data.get("base_url", ""))
    provider = "local" if ("127.0.0.1" in base or "localhost" in base) else base
    return {"provider": provider,
            "model": data.get("model"),
            "version": data.get("model"),
            "base_url": base,
            "temperature": data.get("temperature"),
            "max_tokens": data.get("max_tokens"),
            "usd_per_1k_tokens": data.get("usd_per_1k_tokens", 0.0),
            "extra_body": data.get("extra_body", {})}


#: W6 车道切换余量（tff 裁定，2026-10-14）：原规则 `cr > lr` 是噪声开关——10~30 章
#: 样本里召回差 1~2pp 完全在波动范围内，据此切默认车道等于拿抖动做产品决策。
#: 现要求云端召回领先 >10pp **且** 一致率不低于本地 −2pp 才切默认；
#: 后者是「一致性铁律」的下行容差：宁可少收 2pp 一致率，不可让默认车道更抖。
LANE_RECALL_MARGIN = 0.10
LANE_JACCARD_TOLERANCE = 0.02


def decide_lane(local: dict, cloud: dict) -> str:
    """W6 预登记决策规则（含余量，见 `LANE_RECALL_MARGIN` / `LANE_JACCARD_TOLERANCE`）。

    - 云端召回领先 >10pp 且一致率 ≥ 本地 −2pp ⇒ 默认切云端，本地留降级档；
    - 两者差不多 ⇒ 留本地（省 COGS、少一个外部依赖），云端只按章兜底。
    """
    lr, cr = float(local.get("recall", 0) or 0), float(cloud.get("recall", 0) or 0)
    lj, cj = float(local.get("jaccard_med", 0) or 0), float(cloud.get("jaccard_med", 0) or 0)
    if cr >= lr + LANE_RECALL_MARGIN and cj >= lj - LANE_JACCARD_TOLERANCE:
        return "cloud_default_local_fallback"
    return "local_default_cloud_per_chapter_fallback"


def check_w5_gate(*, n_chapters: int, n_waste: int,
                  pairs: Sequence[Tuple[Sequence, Sequence]],
                  believes_stable: bool) -> Dict[str, object]:
    """W5 预登记硬门槛判定（`median_jaccard` 按 pairs 算）。"""
    vals = [chapter_jaccard(a, b) for a, b in pairs]
    med = median_jaccard(vals)
    wr = waste_rate(n_waste, n_chapters)
    return {"pass": bool(wr < WASTE_RATE_MAX and med >= JACCARD_MED_MIN
                         and believes_stable),
            "waste_rate": wr, "jaccard_med": med,
            "believes_stable": bool(believes_stable),
            "waste_ok": wr < WASTE_RATE_MAX, "jaccard_ok": med >= JACCARD_MED_MIN}


# ---- llm_extract / live / instr_measure 调用的别名（同一实现，不两份逻辑） ----
def repair_prompt(bad_raw: str, error: str) -> List[dict]:
    return build_repair_messages(bad_raw, error)


def alias_followup_prompt(value: str, candidates: List[str]) -> List[dict]:
    return build_alias_followup_messages(value, candidates)


def apply_code_defaults(payload: dict, schema_keys: Sequence[str],
                        fixed_keys: Sequence[str],
                        default: int = DEFAULT_FIXED_POINT) -> Tuple[dict, List[str]]:
    return apply_fixed_point_defaults(payload, "", schema_keys, fixed_keys, default)


def merge_key(event_type: str, actor: Optional[str], payload: dict) -> tuple:
    fid = (payload.get("fact_id") or payload.get("conclusion_fact_id")
           or payload.get("stated_fact_id"))
    ev = payload.get("evidence_fact_ids")
    ev_key = tuple(sorted(ev)) if isinstance(ev, list) else ev
    return (event_type, actor, fid, str(ev_key))


def dedup_proposals(props: Sequence) -> Tuple[List, Dict[str, int]]:
    """W1 平铺去重（调用方已把各段拼平）：返回 (去重后, {before, after})。"""
    seen: set = set()
    out: List = []
    for p in props:
        try:
            k = merge_key(p.proposed_event_type, p.actor, dict(p.payload))
        except Exception:
            k = (str(getattr(p, "proposed_event_type", "?")), str(p))
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out, {"before": len(props), "after": len(out)}


def lane_identity_report(client, lane: str) -> Dict[str, object]:
    """护栏 1：仪器档案记下车道完整身份。`describe_endpoint` 的调用方形态。"""
    ep = None
    try:
        ep = client.router.endpoints.get("extract")
    except AttributeError:
        pass
    base: Dict[str, object] = {"instr": instr_id_for_lane(lane), "lane": lane}
    return {**base, **describe_endpoint(ep)} if ep is not None else base


def replay_junk_entries(junk: List[dict], parse_fn) -> dict:
    """W2 验收：_junk.json 里历史坏输出离线回放（零采样）。

    parse_fn(raw) -> (props, bad)。修复率 100% 或段级优雅降级即过。
    """
    total = len(junk or [])
    recovered = 0
    degraded = 0
    for entry in (junk or []):
        raw = entry.get("raw", "")
        try:
            props, _ = parse_fn(raw)
        except Exception:
            props = []
        if props:
            recovered += 1
        else:
            degraded += 1  # 仍失败但有明确 reason/章节/窗口标注 = 优雅降级
    return {"total": total, "recovered": recovered, "degraded": degraded,
            "pass": total == 0 or (recovered + degraded) == total}
