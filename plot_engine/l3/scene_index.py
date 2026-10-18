"""场景索引（第一层，纯派生）：章正文 → 场景帧序列。

派生方式=确定性规则（地点名词表+实体白名单+到达/离开触发词），LLM 增强版留旁路车道。
v042 校准件移交：送检面注释剥离（ch26-B 实证注释行可被引用）、到达/离开触发词表、
「准备离开」意图≠离开（ch20 #22 人核误报教训）、章首场景豁免（丁批 A 族口径）。
"""
from __future__ import annotations

import re
from typing import List, Sequence

from plot_engine.l3.models import SceneFrame

# ---- 词表（尺面戳 l3-v0.2.3：变更=读数变更，须带戳） ----
DEFAULT_ENTITIES = ["张三", "王五", "李四", "赵六"]
DEFAULT_LOCATIONS = ["藏宝阁", "书房", "后院", "山下", "门主府", "掌门府",
                     "走廊", "阁楼", "住处"]
TIME_MARKERS = ["次日", "第二天", "翌日", "入夜", "夜幕降临", "清晨", "天亮",
                "晌午", "黄昏"]

# 到达叙述（v042 ARRIVAL_RE 同源 + 返回类；v2.2：门窗跨距 8→12 并收「踏进」
# ——ch35 L6「木门在张三的推力下缓缓打开」=误报级到达漏认；v2.3 F3：补「前来/赶来/过来」
# ——ch26 L6「赵六匆匆前来」=到达叙述未入词表，稽核 l3-v022-audit §F3）。
ARRIVE_RE = re.compile(
    r"(门[^。]{0,12}(推开|打开|敲响|开了))|((推开|打开|敲响)[^。]{0,8}门)"
    r"|(走了?进来|踏入|踏进|迈进|推门|破门|闯入|出现在门口|步入|来到|返回|回到"
    r"|前来|赶来|过来)")
# v2.2：倒装到达句式主语=后置名（ch48 L16「门被推开，进来的是王五」——_subject_near
# 回看窗抓不到后置主语，会把张三错认成到达者，王五反被悬置成 A 嫌疑）。
ARRIVE_NAME_RE = re.compile(r"(进来的是|走进来的是|推门进来的是)(张三|王五|李四|赵六)")
# 硬离开（完成态）；意图词（准备/打算/决定前往）不算——ch20 #22 教训
DEPART_RE = re.compile(r"(转身离开|离开了?|离去|先走了|告辞|告别|出门|下山|赶往|奔赴)")
# 意图窗：DEPART 命中点落在意图词跨距内=不计（"准备离开"≠离开，ch20 #22 误报教训）
DEPART_INTENT_RE = re.compile(r"(准备离开|打算离开|想要离开|决定离开|计划离开|准备前往|打算前往|决定前往)")
# v2.3 F1 否定守卫（稽核 ch40 L2「然而他并未离开藏宝阁一步」被计为离开）：
# 离开触发词前 3 字窗内是否定副词=没离开，不计 departed。
DEPART_NEG_RE = re.compile(r"(并未|没有|从未|不曾|未曾|未)\s*$")

_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
# 抽取层 v2 修复①：剥离引号内台词内容——「台词提及行不造在场场景帧」。
# 角色嘴里提到某人/某地（如 ch50「李四那晚却在山下与外客饮酒」）≠ 叙述层真在场/真切换地点。
_QUOTED_RE = re.compile(r"[「『“‘].*?[」』”’]", re.S)
# v2.1 修复①姊妹面：叙述行「去找X/去寻X/询问X」=移动意图的目标提及，被找者不在现场
# （ch27-A「王五则去找李四询问」=去找型造帧，与台词提及同族、行级语用未分）。
_SEEK_TARGET_RE = re.compile(r"(去找|去寻|去找寻|询问)[^，。；]{0,4}(张三|王五|李四|赵六)")
# v2.2 修复①（tff 真人终审：A 族宿主独报 27 条全误=同一病根）：含回忆/传闻/追述触发词的
# 行整行不产在场——生成体一行一思，回忆辖域随冒号与后续子句蔓延（「他想起…：李四最近…」），
# 小句级剥不净（试点实证）；行级误杀经验者的代价由其邻行真实在场行补偿（锚①同款行不受影响）。
# v2①堵引号台词、v2.1①堵去找X，v2.2 堵叙述转述层。
# v2.3 F4 补指认转述（稽核 l3-v022-audit：ch15 L10「他发现了新的线索，那就是李四在山下与一个
# 陌生人会饮」=无触发词的转述漏网）；F1 把本闸作用域从在场扩到到达/离开（回忆里的「自己离开时」
# 不算离开）。
_MENTION_TRIG_RE = re.compile(
    r"想起|回忆|记起|记得|听说|听到|想到|心想|心中|念头|直觉|预感|怀疑|推测|猜测|揣测|觉得|知道"
    r"|意识到|明白|得知|所说|笔迹|字迹|模仿|提及|提到|认为|决定|打算|那晚|那夜|那天|那日|昨夜|昨晚"
    r"|曾经|当年|往事|旧事|行踪|脑海|那就是|这便是")


def _line_scope(line: str) -> str:
    """在场只认无回忆/传闻/转述触发词的行。"""
    return "" if _MENTION_TRIG_RE.search(line) else line


_CLAUSE_RE = re.compile(r"[^。！？，；]+")


def _action_scope(line: str) -> str:
    """到达/离开只认「非回忆小句」：同一小句（。，！？为界）内有触发词=该动作是被转述的动作，
    整小句作废（填空洞、并以句号切断门窗跨距，防跨小句误配）。
    v2.3 F1（稽核 ch40 L17「他记得自己离开时…」）——但不能用在场那套整行拒绝：ch50 锚②实证
    真离开行常带地板级触发词（L30「…觉得…便转身离开藏宝阁」），整行拒绝会杀掉 tff 亲拍的真锚。"""
    out = list(line)
    for m in _CLAUSE_RE.finditer(line):
        if _MENTION_TRIG_RE.search(m.group()):
            for i in range(m.start(), m.end()):
                out[i] = "。"
    return "".join(out)


def _narration(line: str) -> str:
    """去掉引号内台词后的叙述部分（在场/地点判定只认叙述行）。"""
    return _QUOTED_RE.sub("", line)


def strip_comments(body: Sequence[str]) -> List[str]:
    """剥离注释行（送检面卫生：ch26-B 实证模型可引用 `<!-- hook -->` 行当证据）。

    返回 (干净行列表, 原行号映射)。原行号映射保证证据区间仍对回原稿。
    """
    kept, lineno = [], []
    for i, ln in enumerate(body, 1):
        if _COMMENT_RE.match(ln) or not ln.strip():
            continue
        kept.append(ln)
        lineno.append(i)
    return kept, lineno


def _subject_near(line: str, span: tuple, entities: Sequence[str],
                  fallback: str = "") -> str:
    """触发词前 14 字窗内最近的实体名；唯一提及直接归属；
    零提及（"他转身离开"式代词行）回落叙事主语连续性=上一具名实体。"""
    mentioned = [e for e in entities if e in line]
    if len(mentioned) == 1:
        return mentioned[0]
    head = line[max(0, span[0] - 14):span[0]]
    # v2.3 F3 附带：命中窗内取「离触发词最近」的实体，不取名单序首个
    # （ch26 L6「…王五抬头望去，只见赵六匆匆前来」=名单序把到达错记成王五，赵六仍成 A 嫌疑）。
    nearest, pos = "", -1
    for e in entities:
        p_ = head.rfind(e)
        if p_ > pos:
            nearest, pos = e, p_
    if nearest:
        return nearest
    return mentioned[0] if mentioned else fallback


def build_scene_index(chapter: int, body: Sequence[str],
                      entities: Sequence[str] = DEFAULT_ENTITIES,
                      locations: Sequence[str] = DEFAULT_LOCATIONS) -> List[SceneFrame]:
    """行列表 → 场景帧。行号=剥注释后的送检行号（与原稿映射由 strip_comments 给出）。"""
    lines, _map = strip_comments(body)
    frames: List[SceneFrame] = []
    cur_loc, cur_start = "-", 1

    def _loc_of(ln: str) -> str:
        for loc in locations:
            if loc in ln:
                return loc
        return ""

    for i, ln in enumerate(lines, 1):
        narr = _narration(ln)
        hit = _loc_of(narr)
        if i == 1:
            cur_loc = hit or "-"  # 首行初始化，不产幽灵空帧（章首豁免的命根）
        is_new = False
        if hit and hit != cur_loc:
            is_new = True
        elif any(t in narr for t in TIME_MARKERS) and frames and i > cur_start:
            is_new = True  # 时间标记开新场（地点沿用）
        if is_new:
            frames.append(SceneFrame(chapter=chapter, scene_seq=len(frames),
                                     location_text=cur_loc,
                                     line_start=cur_start, line_end=i - 1))
            cur_loc, cur_start = hit or cur_loc, i
    if lines:
        frames.append(SceneFrame(chapter=chapter, scene_seq=len(frames),
                                 location_text=cur_loc,
                                 line_start=cur_start, line_end=len(lines)))

    last_entity = ""
    for fr in frames:
        seg = list(enumerate(lines[fr.line_start - 1:fr.line_end], fr.line_start))
        present_line: dict = {}
        for g, ln in seg:
            n = _line_scope(_SEEK_TARGET_RE.sub("", _narration(ln)))  # v2①/v2.1①/v2.2①/v2.3 F4
            for e in entities:
                if e in n:
                    present_line.setdefault(e, g)
        fr.present = sorted(present_line)
        fr.present_line = present_line
        arr, dep = set(), set()
        for _, ln in seg:
            sc = _action_scope(ln)  # v2.3 F1：作用域从在场扩到到达/离开（稽核=B 族输入面裸露），小句级非整行
            for m in ARRIVE_NAME_RE.finditer(sc):  # v2.2 倒装到达：后置主语直取
                arr.add(m.group(2))
            for m in ARRIVE_RE.finditer(sc):
                s = _subject_near(sc, m.span(), entities, last_entity)
                if s:
                    arr.add(s)
            intent_spans = [m.span() for m in DEPART_INTENT_RE.finditer(sc)]
            for m in DEPART_RE.finditer(sc):
                if any(a <= m.start() < b for a, b in intent_spans):
                    continue  # 意图不算离开
                if DEPART_NEG_RE.search(sc[max(0, m.start() - 3):m.start()]):
                    continue  # v2.3 F1 否定守卫：「并未离开」=没离开
                s = _subject_near(sc, m.span(), entities, last_entity)
                if s:
                    dep.add(s)
            mentioned = [e for e in entities if e in ln]
            if mentioned:
                last_entity = mentioned[0]  # 叙事主语连续性（代词行回落用）
        fr.arrived, fr.departed = sorted(arr), sorted(dep)
    return frames
