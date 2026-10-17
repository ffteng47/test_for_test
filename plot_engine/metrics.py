"""从逐章快照读回 §7 的两条判据线：干净口径 E2 与人工处置率（`c6615d5` 的定义，逐字不改）。

判据文本冻结在 `docs/phase0-v3-three-arm-results.md` §7；这里只做**读数**。
之所以要住在仓库里：Phase 0 的同类脚本落在仓库外临时目录，机器一清就没了，
而 dump 是唯一能重读的原始记录（08 §3 的报告表不许加字段）。
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Dict, List

_ROUNDS_RE = re.compile(r"rounds=(\d+)")
_STATUS_RE = re.compile(r"status=(\w+)")
_ACTION_RE = re.compile(r"action=(\w+)")
_REWRITE = {"rewrite_scene", "rewrite_chapter", "patch_write"}


@dataclasses.dataclass
class ChapterRead:
    chapter_no: int
    trace_status: str
    rounds: int
    actions: List[str]
    draft_equals_round0: bool

    @property
    def bucket(self) -> str:
        """首轮 / 真 rewrite 救回 / renegotiate-only / 处置。"""
        if self.trace_status != "OK":
            return "disposition"
        if self.rounds == 0:
            return "first_pass"
        if any(a in _REWRITE for a in self.actions):
            return "rewrite_rescued"
        return "renegotiate_only"      # 含 Draft≡Round 0 的「删空判据后照写」


def read_dump(dump_dir) -> List[ChapterRead]:
    out: List[ChapterRead] = []
    for path in sorted(Path(dump_dir).glob("ch*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        head = "\n".join(lines[:4])
        status = next((ln.split("=", 1)[1] for ln in lines[:3]
                       if ln.startswith("trace_status=")),
                      _STATUS_RE.search(lines[0]).group(1))
        rounds = int(_ROUNDS_RE.search(head).group(1)) if _ROUNDS_RE.search(head) else 0
        actions = _ACTION_RE.findall("\n".join(_revision_section(lines)))
        out.append(ChapterRead(chapter_no=int(re.search(r"(\d+)", path.stem).group(1)),
                               trace_status=status, rounds=rounds, actions=actions,
                               draft_equals_round0=_draft_equals_round0(lines)))
    return out


def _revision_section(lines: List[str]) -> List[str]:
    inside = False
    for line in lines:
        if line.startswith("## "):
            if line.strip() == "## Revision":
                inside = True
                continue
            if inside:
                return
        elif inside and line.startswith("- round "):
            yield line


def _section_body(lines: List[str], title: str) -> List[str]:
    body: List[str] = []
    capture = False
    for line in lines:
        if line.startswith("## "):
            if capture:
                return body
            capture = line.startswith(f"## {title}")
            continue
        if capture:
            body.append(line)
    return body


def _draft_equals_round0(lines: List[str]) -> bool:
    r0 = _section_body(lines, "Round 0")
    return bool(r0) and r0 == _section_body(lines, "Draft")


@dataclasses.dataclass
class DumpMetrics:
    reads: List[ChapterRead]
    dispositions: Dict[str, int]

    @property
    def generated(self) -> int:
        return len(self.reads)

    def count(self, bucket: str) -> int:
        return sum(1 for r in self.reads if r.bucket == bucket)

    @property
    def clean_e2(self) -> float:
        """（首轮 + 真 rewrite 救回）/ 生成章；renegotiate-only 进分母不进分子。"""
        if not self.generated:
            return 0.0
        return (self.count("first_pass") + self.count("rewrite_rescued")) / self.generated

    @property
    def disposition_rate(self) -> float:
        """（判死 + FAIL + NEEDS_HUMAN + 其余非 OK 终态）/ 生成章 = 1 − 名义提交率。"""
        if not self.generated:
            return 0.0
        return self.count("disposition") / self.generated

    def render(self) -> str:
        committed = self.generated - self.count("disposition")
        rows = [f"生成 {self.generated}｜首轮 {self.count('first_pass')}｜"
                f"rewrite 救回 {self.count('rewrite_rescued')}｜"
                f"renegotiate-only {self.count('renegotiate_only')}｜"
                f"处置 {self.count('disposition')}"]
        if self.dispositions:
            rows.append("处置构成：" + " ".join(f"{k}={v}" for k, v in sorted(self.dispositions.items())))
        rows.append(f"干净口径 E2 = {self.clean_e2:.1%}")
        rate = self.disposition_rate
        if committed:
            rows.append(f"人工处置率 = {rate:.1%}（分母=生成章）"
                        f" / {self.count('disposition') / committed:.1%}（分母=提交章）")
        else:
            rows.append(f"人工处置率 = {rate:.1%}（分母=生成章；提交章 0）")
        return "\n".join(rows)


def metrics_from_dump(dump_dir) -> DumpMetrics:
    reads = read_dump(dump_dir)
    dispositions: Dict[str, int] = {}
    for r in reads:
        if r.bucket == "disposition":
            dispositions[r.trace_status] = dispositions.get(r.trace_status, 0) + 1
    return DumpMetrics(reads=reads, dispositions=dispositions)


# ---- 爽点工程读数表（R8 #2 全-A 拍板 2026-10-17：纯派生、离线、只读；
#      零尺零契约零门禁，不进任何判据——tension_actual/turning_points_hit 落账是二期 epoch_2 债）----

_BEAT_ORDER = ("setup", "pressure", "turn", "release", "foreshadow")


def r3r6_flags(curve: List[int], tp_chapters: List[int]) -> List[str]:
    """R3'~R6' 伪定量观察行（04:77-80 逐条复算，只进报表、不进闸）。"""
    flags: List[str] = []
    flat = [abs(curve[i + 1] - curve[i]) < 50 for i in range(len(curve) - 1)]
    start = 0
    for i in range(len(flat) + 1):
        if i < len(flat) and flat[i]:
            continue
        if i - start >= 2:                                   # ≥2 个平步 = 连续 ≥3 章差<50
            flags.append(f"R3'@ch{start + 1}-{i + 1}（连续差<50，疑似注水）")
        start = i + 1                                        # 平步断在不相等的那一步，下一窗从其后起
    start = 0
    for i in range(1, len(curve) + 1):
        if i < len(curve) and curve[i] > curve[i - 1]:
            continue
        if i - start >= 5:
            flags.append(f"R4'@ch{start + 1}-{i}（连续≥5章单调升，疑似疲劳）")
        start = i
    for w in range(0, len(curve), 10):
        win = curve[w:w + 10]
        if win and max(win) < 800:
            flags.append(f"R5'@ch{w + 1}-{w + len(win)}（窗内无≥800峰）")
    for c in tp_chapters:
        if 1 <= c <= len(curve) and curve[c - 1] < 700:
            flags.append(f"R6'@ch{c}（转折章张力{curve[c - 1]}<700）")
    return flags


def thrill_table(dump_dir, fixture: str = "experiment_10ch") -> str:
    """逐章六项派生读数 + 卷级聚合。规划面全部从夹具 derive 确定性复算
    （replay 归档 state/event.db 重建 pre-state），replay 不可得的章记「-」——没测≠全好。"""
    import importlib
    from pathlib import Path

    from plot_engine.markup import parse_markup
    from plot_engine.replay import replay_to_chapter
    from plot_engine.validator import _hook_ok

    fx = importlib.import_module(f"plot_engine.tests.fixtures.{fixture}")
    d = Path(dump_dir)
    files = sorted(d.glob("ch*.md"))
    if not files:
        return f"（{d} 无章 dump）"
    total = max(int(Path(p).stem[2:]) for p in files)
    arc = fx.build_arc(chapters=total)
    story = fx.make_config(total).story_id
    state_dir = d / "state"
    store = log = reducer = None
    if (state_dir / "state.db").exists() and (state_dir / "event.db").exists():
        from plot_engine.eventlog import EventLog
        from plot_engine.reducer import Reducer
        from plot_engine.store import StateStore
        store, log, reducer = StateStore(str(state_dir / "state.db")), \
            EventLog(str(state_dir / "event.db")), Reducer()

    rows, hits, judgeable, strengths, dev = [], 0, 0, [], []
    for p in files:
        ch = int(p.stem[2:])
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        draft = "\n".join(_section_body(lines, "Draft"))
        hard = sorted(set(re.findall(r"HARD ([\w.]+)", "\n".join(_section_body(lines, "Findings")))))
        contract = plan = None
        if store is not None:
            try:
                pre = replay_to_chapter(store, log, reducer, story, ch - 1)
                contract = fx.contract_for(arc, ch, pre)
                plan = fx.plan_for(contract, pre)
            except Exception:
                contract = plan = None
        markup = parse_markup(draft)
        st = markup.hooks[0].strength if len(markup.hooks) == 1 else None
        hook = "-" if contract is None else ("✓" if _hook_ok(markup, contract) else "✗")
        if contract is not None:
            judgeable += 1
            hits += hook == "✓"
            if st is not None:
                strengths.append(st)
            dev.append(abs(contract.tension_target - arc.tension_curve[ch - 1]))
        beats = scene_t = "-"
        if plan is not None:
            cnt: Dict[str, int] = {}
            for sc in plan.scenes:
                for b in sc.beats:
                    cnt[b.beat_type] = cnt.get(b.beat_type, 0) + 1
            beats = "/".join(str(cnt.get(k, 0)) for k in _BEAT_ORDER)
            scene_t = "/".join(str(sc.tension) for sc in plan.scenes)
        tp = ",".join(t.type for t in arc.turning_points if t.chapter == ch) or "-"
        rows.append(f"| ch{ch} | {arc.tension_curve[ch - 1]} | "
                    f"{contract.tension_target if contract else '-'} | {scene_t} | {beats} | "
                    f"{hook} | {st if st is not None else '-'} | {tp} | {' '.join(hard) or '-'} |")
    agg = [f"钩命中率（H5.5 同谓词）= {hits}/{judgeable}（可判章；replay 不可得的章记「-」未计入）",
           f"strength 观察列（不比达标）：{sorted(strengths) or '无'}",
           f"规划↔契约偏差 |Δ| 均值：{sum(dev) / len(dev):.1f}" if dev else "规划↔契约偏差：无可对章",
           "伪定量观察行（R3'-R6'）：" + (" ".join(r3r6_flags(arc.tension_curve,
                                                             [t.chapter for t in arc.turning_points])) or "无")]
    head = ("| 章 | 曲线规划 | 契约目标 | 场景张力 | beat五桶(set/press/turn/rel/for) | 钩 | strength | 转折规划 | 硬项 |\n"
            "|---|---|---|---|---|---|---|---|---|")
    return "\n".join([f"爽点工程读数表（{d.name}｜夹具={fixture}｜纯派生离线，不进闸）",
                      head, *rows, "", *agg])


# ---- 读者已知阅读卡（WP-F B2 #105，2026-10-17：纯派生、离线、只读，不进判据）----

_READER_ZH = {"knows": "已知", "hinted": "示意", "deceived": "误导", "unaware": "未感知"}


def render_reader_card(state, story_id: str) -> str:
    """把 reader_ledger 投影成阅读卡；不在账的 fact 一律标「未感知」——没记≠知道。"""
    led = {e.fact_id: e for e in state.reader_ledger}
    rows, cnt = [], {}
    for f in sorted(state.facts.values(), key=lambda f: f.fact_id):
        e = led.get(f.fact_id)
        st = e.reader_state if e else "unaware"
        cnt[st] = cnt.get(st, 0) + 1
        rows.append(f"| {f.fact_id} | {_READER_ZH[st]} | "
                    f"{e.reader_strength if e else '-'} | "
                    f"{f'{e.established_at_chapter}→{e.last_updated_chapter}' if e else '-'} | "
                    f"{f.reveal_stage} | {f.proposition} |")
    agg = " ".join(f"{_READER_ZH[k]}={cnt[k]}" for k in ("knows", "hinted", "deceived", "unaware") if cnt.get(k))
    head = ("| fact | 读者态 | 强度(×1000) | 建立→更新章 | reveal_stage | 命题 |\n|---|---|---|---|---|---|")
    return "\n".join([f"读者已知阅读卡（story={story_id}｜截至 ch{state.chapter_no}｜纯派生只读，不进闸）",
                      head, *rows, "", f"分布：{agg or '无'}｜账外 fact 记「未感知」（reader_ledger 无条目）"])


def reader_card(dump_dir, chapter: int = 0, story_id: str = "s1") -> str:
    """从归档 state/ 重建截至章 N 的状态（0=终态快照）；replay 不可得直接抛（读数不兜假账）。"""
    d = Path(dump_dir) / "state"
    from plot_engine.eventlog import EventLog
    from plot_engine.reducer import Reducer
    from plot_engine.replay import replay_to_chapter
    from plot_engine.store import StateStore
    store, log, reducer = StateStore(str(d / "state.db")), EventLog(str(d / "event.db")), Reducer()
    if chapter:
        return render_reader_card(replay_to_chapter(store, log, reducer, story_id, chapter), story_id)
    return render_reader_card(store.load_latest(story_id).state, story_id)


if __name__ == "__main__":
    import sys

    print(metrics_from_dump(sys.argv[1]).render())
