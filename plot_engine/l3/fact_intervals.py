"""有效区间事实视图（第一层，纯派生）：章正文 → 认识论分层陈述 → 跨章区间投影。

C 族结构化抽取=把"找对子"从模型手里拿走（丁批归因鉴别实验本体）：
- 陈述抽取=确定性模式（数量/保管两 predicate 白名单=尺面戳 l3-v0.2.2，值守 v2.2 退役）；
- 认识论分层（丁批 C 族口径）：narrator=叙述者事实 / dialogue=角色台词 / speculation=角色猜测；
- 区间投影（InkOS applyFactOps 互证）：只有 narrator 陈述建权威区间，expire 不删行；
  dialogue/speculation 是 claim，不顶替权威事实（角色可以说谎，世界状态不被台词改写）。
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from plot_engine.l3.models import IntervalFact, Statement
from plot_engine.l3.scene_index import DEFAULT_ENTITIES, strip_comments

_NUM = {"一": "1", "二": "2", "两": "2", "三": "3", "四": "4", "几": "?"}

# v2 修复③「代称不抽数」：key_count 仍认总数（含合法裸形「钥匙…N把」），但逐指代称
# （另一把/这把）与丢失语境（失踪了一把钥匙）不算总数断言，匹配后按数词前窗过滤。
_COUNT_TOPIC_RE = re.compile(r"钥匙[^。，]{0,10}?([一二两三四几])把")
_COUNT_KEY_RE = re.compile(r"([一二两三四几])把钥匙")
_COUNT_DEIXIS = "另这那每各其"          # 紧跟数词前=逐指代称，非总数
_COUNT_LOSS_RE = re.compile(r"(消失|失踪|丢失|丢了|少|偷|被拿走)了?\s*$")
_CUSTODY_VERB = re.compile(r"(保管|持有|掌握|拿着|在[^。]{0,4}手里|随身携带)")
# v2.2②（tff 终审拍板）：night_watch 谓词退役——全库真人终审零条真（值守配对全为
# 问句/回忆/混主体工件），陈述源就此摘除，C 域白名单=key_count/key_custody 两条。
_SPEECH_RE = re.compile(r"(说|道|问|答|低声|笑道|喊道|开口|回道|答道|问道)")
_SPEC_RE = re.compile(r"(觉得|感觉|似乎|好像|心中|暗想|琢磨|怀疑|隐约|猜测|想来)")
# v2 修复④「陈述时点字段」：事后/回忆语境（非当晚在场）；v2.1③ 补白日在场词
# （ch45 L17「阳光透过窗户…并肩站在门口」=次日白日在场被当值守配对，词表缺口）。
_AFTERMATH_RE = re.compile(r"(事后|后来|之前|先前|早前|上次|当初|曾经|回忆|想起|记得|那晚|昨晚|那天"
                           r"|阳光|白日|白天|清晨|早晨|上午|中午|午后)")


def _epistemic(line: str) -> str:
    """猜测 > 台词 > 叙述者（台词里的心理活动仍是猜测）。"""
    if _SPEC_RE.search(line):
        return "speculation"
    if _SPEECH_RE.search(line) or ("“" in line and "”" in line) or ("「" in line and "」" in line):
        return "dialogue"
    return "narrator"


def _tense(line: str) -> str:
    return "aftermath" if _AFTERMATH_RE.search(line) else "on_scene"


def _names_in(line: str, entities: Sequence[str]) -> List[str]:
    return sorted({e for e in entities if e in line})


def _count_value(ln: str) -> Optional[str]:
    """key_count 规范化取值；逐指代称/丢失语境不抽数（v2 修复③）。"""
    for m in _COUNT_TOPIC_RE.finditer(ln):
        if ln[max(0, m.start(1) - 1):m.start(1)] not in _COUNT_DEIXIS \
                and not _COUNT_LOSS_RE.search(ln[:m.start(1)][-4:]):
            return _NUM[m.group(1)]
    for m in _COUNT_KEY_RE.finditer(ln):
        if ln[max(0, m.start(1) - 1):m.start(1)] not in _COUNT_DEIXIS \
                and not _COUNT_LOSS_RE.search(ln[:m.start(1)][-4:]):
            return _NUM[m.group(1)]
    return None


def extract_statements(chapter: int, body: Sequence[str],
                       entities: Sequence[str] = DEFAULT_ENTITIES) -> List[Statement]:
    """逐行抽取 C 域陈述（行号=剥注释后送检行号）。"""
    lines, _map = strip_comments(body)
    out: List[Statement] = []
    for i, ln in enumerate(lines, 1):
        if "钥匙" not in ln:
            continue
        ep = _epistemic(ln)
        tn = _tense(ln)
        n = _count_value(ln)
        if n:
            out.append(Statement(chapter=chapter, predicate="key_count",
                                 value=f"{n}把", raw=ln.strip()[:60],
                                 line_start=i, line_end=i, epistemic=ep, tense=tn))
        if "钥匙" in ln and _CUSTODY_VERB.search(ln):
            names = _names_in(ln, entities)
            extra = [w for w in ("长老", "阁主", "守阁人", "守夜人", "门主", "宗主", "高层") if w in ln]
            if names or extra:
                out.append(Statement(chapter=chapter, predicate="key_custody",
                                     value="+".join(names + extra), raw=ln.strip()[:60],
                                     line_start=i, line_end=i, epistemic=ep, tense=tn))
    return out


def project_intervals(statements: Sequence[Statement],
                      subject: str = "钥匙") -> List[IntervalFact]:
    """narrator 陈述 → 跨章权威区间（被同 predicate 新取值顶替=上一章失效，expire 不删行）。"""
    auth = [s for s in statements if s.epistemic == "narrator"]
    auth.sort(key=lambda s: (s.chapter, s.line_start))
    intervals: List[IntervalFact] = []
    open_of: Dict[str, IntervalFact] = {}
    for s in auth:
        prev: Optional[IntervalFact] = open_of.get(s.predicate)
        if prev and prev.object != s.value:
            prev.valid_until = max(prev.valid_from, s.chapter - 1)
        if prev is None or prev.object != s.value:
            nf = IntervalFact(subject=subject, predicate=s.predicate, object=s.value,
                              valid_from=s.chapter, source_chapter=s.chapter,
                              evidence_ref=f"ch{s.chapter:02d}:{s.line_start}-{s.line_end}")
            intervals.append(nf)
            open_of[s.predicate] = nf
    return intervals


def epistemic_pair(a: Statement, b: Statement) -> Tuple[str, bool]:
    """配对认识论标签 + 是否同说话人（dialogue_dialogue_cross 供判分层降权）。"""
    tag = f"{a.epistemic}_{b.epistemic}" if a.epistemic <= b.epistemic else f"{b.epistemic}_{a.epistemic}"
    return tag, False
