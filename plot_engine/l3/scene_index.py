"""场景索引（第一层，纯派生）：章正文 → 场景帧序列。

派生方式=确定性规则（地点名词表+实体白名单+到达/离开触发词），LLM 增强版留旁路车道。
v042 校准件移交：送检面注释剥离（ch26-B 实证注释行可被引用）、到达/离开触发词表、
「准备离开」意图≠离开（ch20 #22 人核误报教训）、章首场景豁免（丁批 A 族口径）。
"""
from __future__ import annotations

import re
from typing import List, Sequence

from plot_engine.l3.models import SceneFrame

# ---- 词表（尺面戳 l3-v0.3.0：变更=读数变更，须带戳） ----
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
# v0.3 §7.18（tff 亲裁 ch08-B=真穿帮「位移蒸发」）：到达支拆两半。
# 位移支=主语真的从甲地移动到乙地（来到/走进/赶来…），可续接位移链、保留全消解权；
# 门窗口支=只写「门被推开/打开」，不写人怎么到的此处——上一帧把人落在别处时不构成消解。
ARRIVE_MOVE_RE = re.compile(
    r"(走了?进来|踏入|踏进|迈进|推门|破门|闯入|出现在门口|步入|来到|返回|回到"
    r"|前来|赶来|过来)")
# v2.2：倒装到达句式主语=后置名（ch48 L16「门被推开，进来的是王五」——_subject_near
# 回看窗抓不到后置主语，会把张三错认成到达者，王五反被悬置成 A 嫌疑）。
ARRIVE_NAME_HEAD = "(进来的是|走进来的是|推门进来的是)"


def _arrive_name_re(entities: Sequence[str]) -> re.Pattern:
    """倒装到达后置主语，名单从尺面实体表取（F5：原硬编码四名单）。"""
    alt = "|".join(sorted((re.escape(e) for e in entities), key=len, reverse=True))
    return re.compile(ARRIVE_NAME_HEAD + f"({alt})")
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


# ---- v0.3 中批：在场认定改「叙述层施事」双闸（tff 2026-10-19 拍板，稽核 F2 根治） ----
# 病根（l3-v022-audit F2 + pack §7.19 实测）：v2.2 的整行拒绝把「张三站在藏宝阁外，心中满是疑惑」
# 这类**真在场行连主语一起杀掉**，在场链被切碎=A 族独报残余 8/8 的唯一成因；同时 ch08 的位移锚行
# L015/L016 也被整行杀掉，导致 tff 判真的位移蒸发在宿主面结构性不可见。
# 闸一（辖域）=心理/传闻触发词所在小句及其后直到句末（。！？）的小句=被想/被传的内容层，不建立在场；
#   承接副词（便/于是/随后…）开头的子句退出辖域=叙述动作的续行，否则 ch50 L30「…觉得…便转身离开」
#   这类真动作会被辖域吞掉。
# 闸二（施事）=实体须是动作/状态谓词的施事（名后 ≤12 字内命中，跨不过句末与辖域），
#   「笔迹与王五的手书有几分类似」「李四在山下与外客会饮」型被提及者天然不命中。
_CLAUSE_SPLIT_RE = re.compile(r"[。！？，；]")
_CONNECT_RE = re.compile(r"^\s*(便|于是|然后|随后|接着|紧接着|这才|随即|立刻|马上|就|才|转身|起身|站起|抬起|转头|开口)")
_AGENT_ACTION_RE = re.compile(
    r"(坐|站|立|倚|躺|蹲|守|陪|待|在|走|奔|赶|跑|冲|进|出|回|推|拉|敲|开|关|锁|拿|握|持|抓|举|放|扔|取"
    r"|只剩|剩下|只有|唯有|独自|孤身"
    r"|翻|看|望|盯|扫|听|闻|嗅|说|道|问|答|喊|笑|哭|点头|摇头|皱眉|环顾|踱步|伸手|写|读|查|摸|抚|指|靠"
    r"|停|凝视|打量|端详|查看|抬|低|闭|睁|转身|起身|走近|来到|转身)")
_AGENT_WINDOW = 12


def _clause_scopes(line: str) -> List[tuple]:
    """行 → [(小句, 起始偏移, 是否落在回忆/传闻辖域内)]。"""
    out, start, scoped = [], 0, False
    for m in _CLAUSE_SPLIT_RE.finditer(line + "。"):
        seg = line[start:m.start()]
        if seg:
            head = seg.lstrip()
            if _CONNECT_RE.match(head):
                scoped = False  # 承接副词=叙述动作续行，退出辖域
            hit_trig = bool(_MENTION_TRIG_RE.search(seg))
            out.append((seg, start, scoped or hit_trig))  # 触发词小句自身=内容层，其后沿用
            scoped = scoped or hit_trig
        start = m.end()
    return out


def _presence_agents(line: str, entities: Sequence[str]) -> List[str]:
    """在场实体=与非动作/状态谓词相邻（前后 ≤12 字）的、位于非辖域小句里的实体。
    前后双向都要看：汉语存现句「藏宝阁内只剩下赵六一人」动词在主语前，只查后向会把开场在场者漏掉。"""
    hit = []
    for seg, _start, scoped in _clause_scopes(line):
        if scoped:
            continue
        for e in entities:
            p = seg.find(e)
            while p >= 0:
                win = (seg[p + len(e):p + len(e) + _AGENT_WINDOW]        # 后向：张三推开书房的门
                       + seg[max(0, p - _AGENT_WINDOW):p])               # 前向：藏宝阁内只剩下赵六一人
                if _AGENT_ACTION_RE.search(win):
                    hit.append(e)
                    break
                p = seg.find(e, p + 1)
    return hit



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
    arrive_name = _arrive_name_re(entities)
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
            # v0.3 中批：在场=叙述层施事双闸（不再整行拒绝，F2 根治）；引号台词/去找X 仍先剥。
            for e in _presence_agents(_SEEK_TARGET_RE.sub("", _narration(ln)), entities):
                present_line.setdefault(e, g)
        fr.present = sorted(present_line)
        fr.present_line = present_line
        arr, arr_move, dep = set(), set(), set()
        for _, ln in seg:
            sc = _action_scope(ln)  # v2.3 F1：作用域从在场扩到到达/离开（稽核=B 族输入面裸露），小句级非整行
            for m in arrive_name.finditer(sc):  # v2.2 倒装到达：后置主语直取
                arr.add(m.group(2))
                arr_move.add(m.group(2))  # 「进来的是X」=位移（v0.3 §7.18）
            for m in ARRIVE_RE.finditer(sc):
                s = _subject_near(sc, m.span(), entities, last_entity)
                if s:
                    arr.add(s)
                    if ARRIVE_MOVE_RE.search(m.group()):
                        arr_move.add(s)  # v0.3：位移支到达=可续接位移链
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
        fr.arrived, fr.arrived_move, fr.departed = sorted(arr), sorted(arr_move), sorted(dep)
    return frames
