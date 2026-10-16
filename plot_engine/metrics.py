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


if __name__ == "__main__":
    import sys

    print(metrics_from_dump(sys.argv[1]).render())
