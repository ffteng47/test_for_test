#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_flavor_lint.py — 网文「AI 味」确定性 lint（Oh Story check-ai-patterns.js 的 Python 完整移植版）

移植来源：
  Oh Story (https://github.com/oh-story-claudecode/oh-story)
  skills/story-long-write/scripts/check-ai-patterns.js (1586 行)
  skills/story-long-write/scripts/style-whitelist.js (39 行)

许可证（MIT，移植保留版权声明）：
  MIT License
  Copyright (c) 2025-2026 oh-story-claudecode
  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:
  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.
  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

移植保真承诺：
  - 23 个 finding type 全部移植，正则与阈值逐条对齐原实现；
  - REVIEW_CLASSES（mechanical/semantic）双分类完整保留，新增 type 未登记直接报错；
  - 7 条 blocking 规则（not-is-comparison / voice-contrast / negation-parade /
    reverse-not-is / trailer-ending / trailer-summary / em-dash）severity 保持 blocking；
  - 引号遮蔽（maskQuoted 等长「？」占位保偏移）、HTML 注释遮蔽（含未闭合注释重扫）、
    YAML front matter 跳过、代码围栏跳过、.deslop-whitelist 书目级豁免，语义全部对齐。

与原作的唯一差异（Alexandria T4 纪律的有意改造，C 类）：
  - 原作的 --fail-on=blocking|all 退出码门控被移除：本工具只产出报告（exit 恒为 0，
    文件读取失败 exit 2），finding 一律作为 T4/OBSERVATION 级报告列，永不作为提交 gate。
  - blocking / advisory / review / calibration 均作为 finding 字段输出，供报告列展示。

校准状态标注（calibration 字段，B 类纪律）：
  - corpora-calibrated：阈值在真人语料上校准过（《万疆》20 章 / 七猫 5584 章 /
    黑岩 3983 篇），见各常量注释；
  - uncalibrated-heuristic：直接沿用 Oh Story 原值，未按本项目题材重新定标。
    对推理/悬疑等「解释链即核心体裁」的题材，reasoning-chain-tic / metaphor-density-tic /
    system-notice-formality-tic 误报风险最高，定标前只作观察列。
"""

import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP


def js_tofixed(value, digits):
    """对齐 JS Number.prototype.toFixed：刚好落在中间时远离零进位
    （Python format 的 round-half-even 会在 x.x5 处与 JS 差一个单位，
    密度数值是报告字段，必须与原作逐字节一致）。"""
    quantum = Decimal(1).scaleb(-digits)
    rounded = Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return '{:.{}f}'.format(float(rounded), digits)

USAGE = """Usage: python3 ai_flavor_lint.py [--json] [--list-review-classes] <file...>

检测需要人工改写的高危 AI 味行文模式（移植自 Oh Story check-ai-patterns.js）：
  不是A而是B / 逗号分号冒号+肯定翻转 / 句号+肯定翻转 / 反复否定铺垫+肯定翻转 /
  破折号(按功能改写) / 碎句号(连续短叙述句) / 长段落(按镜头断段) /
  微动作复读 / 套式反应细节 / 抽象总结复读 / 套词密度 / 比喻密度 / 解释链密度 /
  系统公告公文腔 / 过度精炼短段 / 低连接密度 / 监控摄像头式动作清单 /
  音量反差腔 / 否定排比 / 工整并列 / 反序对比 / 预告式总结收尾 / 章尾状态总结体 /
  引号强调滥用

本书目级 .deslop-whitelist 字面片段在扫描前被等长遮蔽（不支持正则、不继承上级目录）。
本移植版只报告、不改写、不做退出码门控（T4/OBSERVATION 纪律）。
"""

# ---------------------------------------------------------------------------
# 基础字符集与跨度常量
# ---------------------------------------------------------------------------

STOP_CHARS = frozenset('。！？!?\n')
SOFT_SEPARATORS = frozenset('，,、；;：:')
HARD_SEPARATORS = frozenset('。.！!？?')
MAX_NEGATIVE_SPAN = 80
MAX_POSITIVE_SPAN = 80

# 碎句号：连续 STUTTER_MIN_RUN 个「叙述」短句（每句可见字数 ≤ STUTTER_MAX_SENTENCE）无呼吸。
# 只数叙述句，跳过对话/弹幕/系统播报（成片短句是这些体裁的正常形态，不算碎句号）。
STUTTER_MIN_RUN = 6
STUTTER_MAX_SENTENCE = 5
# 长段落：单段原始字符数超过阈值即提示按镜头断段（手机阅读保守阈值，正常单段远低于此）。
LONG_PARAGRAPH_CHARS = 200

# 微动作复读：「V了下 / V了一下 / 拍了两下 / 松了半圈」式轻量补语在叙述里高密度复现，
# 容易形成删减过头的电报体指纹。只扫引号外叙述；密度与次数双门槛同时达标才报，
# 单次出现是正常中文。
MICRO_TIC_PATTERN = re.compile(r'了(?:[一两三几半])?[下阵圈道声眼口气会]')
MICRO_TIC_MIN_HITS = 5
MICRO_TIC_PER_KILO = 6

# 「没A，也没B」「不A，也不B」否定对偶：七猫人类长篇约 0.07 处/千字，模型稿 0.4-1.5 处/千字；
# 写人物没做什么是英文式节奏，一章 3 处以上报一条提示。
NEGATION_PAIR_PATTERN = re.compile(r'(?:没有|没|不)[^，。！？；,!?\n]{1,10}[，,；]\s*[^，。！？；,!?\n]{0,6}?也(?:没有|没|不)')
NEGATION_PAIR_MIN_HITS = 3

# 套式反应细节：不是禁写身体，而是提示成片出现的“部位 + 轻微动作/状态”、
# “胸口像被撞了一下”、喉结/眼圈/声音放轻等通用情绪尾巴，以及“平静语气 +
# 像在念/宣判”模板。此类句子词面变化大，不能逐词 blocking；按章聚集到 4 处才
# advisory，要求逐处做删除测试。正常受伤、打斗、生理反应若承担物理后果可保留。
STOCK_REACTION_PATTERNS = [
    re.compile(r'(?:指尖|手指|指节|手背|掌心|拳头|袖口|衣角|裙角|下唇|嘴唇|唇角|嘴角|眉头|眼底|眸光|目光|视线|肩膀|呼吸)[^。！？!?\n]{0,16}(?:轻轻|微微|缓缓|悄然|不自觉|无意识|下意识|攥紧|握紧|收紧|绞紧|泛白|发白|叩|敲|摩挲|抿紧|抿成|移开|垂下|躲开|一颤|颤了?一下|停了?一下|顿了?一下)'),
    re.compile(r'(?:语气|声音)[^。！？!?\n]{0,12}(?:平静|冷静|平淡|冷淡|淡漠|平直)[^。！？!?\n]{0,12}(?:像|仿佛|如同|好像)[^。！？!?\n]{0,16}(?:念|读|报|说|陈述|宣判|背诵)'),
    re.compile(r'(?:胸口|心口)[^。！？!?\n]{0,16}(?:像|仿佛|如同|好像)[^。！？!?\n]{0,16}(?:撞|锤|压|攥|堵)[^。！？!?\n]{0,8}(?:一下|一记|一拳)?'),
    re.compile(r'(?:声音|嗓音|语气)[^。！？!?\n]{0,12}(?:放轻|压低|发紧|发颤|很轻|轻了些)'),
    re.compile(r'(?:喉结|喉头|喉咙)[^。！？!?\n]{0,10}(?:滚|动|紧|堵|发涩|发干)'),
    re.compile(r'(?:眼眶|眼圈|鼻子)[^。！？!?\n]{0,8}(?:发红|红了|发热|发酸|一酸)'),
    re.compile(r'(?:抿了?下唇|抿了?抿唇|抿了?下嘴|抿着笑)'),
]
STOCK_REACTION_MIN_HITS = 4
# 校准（真人语料，<br> 已还原为换行）：qimao 长篇 5584 章 + heiyan 短篇整篇 3983 篇。
# 长篇章尺度（中位约 2100 字）per-kilo 1.0→1.5 误报 0.43%→0.39%，几乎不动；
# 短篇整篇 8000-20000 字下 MIN_HITS 形同虚设、只剩密度门，1.0 时误报 5.57%，
# 1.5 降到 1.46%。故取 1.5，把两个总体拉到同一量级（四份副本共用一组阈值）。
STOCK_REACTION_PER_KILO = 1.5

# 监控摄像头式动作清单：同一段连续堆叠通用动作动词（伸手/拿起/取过/挑开/放下/转身等），
# 且用逗号/顿号串联成步骤表时，读感像无视角温度的监控记录。只做 advisory；
# 打斗/追逐等功能性动作编排可保留或人工复核。
ACTION_LIST_VERB_PATTERN = re.compile(r'伸手|抬手|探手|拿起|拿过|取出|取过|掏出|摸出|抓起|攥住|握住|捏住|按住|推开|拉开|打开|关上|放下|递给|挑开|掀开|扯开|拧开|倒出|端起|转身|回头|抬头|低头|弯腰|俯身|走到|走向|坐下|站起|看向|看着|盯着|扫过')
ACTION_LIST_MIN_HITS = 5
ACTION_LIST_MIN_SEPARATORS = 4

# 抽象总结复读：模板化段落常把角色当下经历拔成「命运/棋局/
# 这一刻终于明白/才刚刚开始」的作者总结。单个词可能服务题材；高密度聚集才报。
ABSTRACT_SUMMARY_PATTERNS = [
    re.compile(r'这一刻[，,]?[^\n。！？!?]{0,24}(?:终于|才)(?:明白|意识到)'),
    re.compile(r'从这一刻开始'),
    re.compile(r'(?:命运|宿命)[^\n。！？!?]{0,28}(?:齿轮|棋局|獠牙|改写|推向|安排)'),
    re.compile(r'早已[^\n。！？!?]{0,8}(?:布好|安排好)[^\n。！？!?]{0,8}(?:棋局|局)'),
    re.compile(r'前所未有的(?:决意|清醒|勇气|力量|恐惧|平静|信念)'),
    re.compile(r'(?:反击|复仇|战争|较量|故事|命运)[^\n。！？!?]{0,12}才刚刚开始'),
    re.compile(r'(?:新的开始|全新的开始)'),
]
ABSTRACT_SUMMARY_MIN_HITS = 3
ABSTRACT_SUMMARY_PER_KILO = 4

# 套词密度：单个「仿佛/一丝」可能是正常中文，高密度聚集才会形成模板腔。
# 词表只收本 repo banned-words 中已明确标为高危的形态，避免把普通功能词一网打尽。
CLICHE_PATTERNS = [
    re.compile(r'仿佛|犹如|宛若|如同'),
    re.compile(r'一丝|一抹|些许|几分|隐约'),
    re.compile(r'深吸一口气|缓缓|微微|轻轻|淡淡'),
    re.compile(r'眼中闪过|嘴角勾起|眸光微微一闪|指节泛白|目光锐利|眼神锐利'),
    re.compile(r'心中涌起一股|心头一震|心中一动|心下了然|心中暗道|心中一凛'),
    re.compile(r'不容置疑|不容置喙|不易察觉|显而易见|毫无疑问|不可否认'),
    re.compile(r'声音不大[，,]?却带着|语气平静无波|平静无波|声音平直|听不出情绪'),
    re.compile(r'不知何时|唾手可得|无声翻涌|沉默(?:在[^。！？!?\n]{0,16})?蔓延|难以言说'),
    re.compile(r'散发着一股|冰冷的光|格外刺眼|深邃而冰冷'),
]
CLICHE_DENSITY_MIN_HITS = 8
CLICHE_DENSITY_PER_KILO = 12

# 比喻密度：单个生活化比喻可服务画面；“像/好像/仿佛/如同”成片复现时，
# 容易变成 AI 式修辞堆叠。只做 advisory，修法是删到必要数量并回到具体画面，
# 不是把“像”换成另一组比喻词。
METAPHOR_MARKER_PATTERN = re.compile(r'好像|像是|仿佛|宛如|如同|犹如|(?<![不头图画影录摄肖])像(?![头像素])')
METAPHOR_LIKE_PHRASE_PATTERN = re.compile(r'(?:死|水|冰|火|潮水|石头|木头|机器|纸|铁|鬼|死人|刀|针|网|墙)一样')
METAPHOR_DENSITY_MIN_HITS = 7
METAPHOR_DENSITY_PER_KILO = 3

# 解释链密度：常见“他知道/他明白/这意味着/必须需要”
# 连续替读者推理，读感像报告。单个判断词可服务推理；高密度聚集才提示回到角色当下证据。
REASONING_CHAIN_PATTERNS = [
    {'key': 'mental', 'core': True,
     'pattern': re.compile(r'(?<![不没未无])(?:他|她|我)?(?:知道|明白|意识到|清楚|判断|确认|分析)')},
    {'key': 'connector', 'core': True,
     'pattern': re.compile(r'这意味着|也就是说|换句话说|真正的问题(?:在于)?|问题在于|关键在于|在这种情况下|按照这个逻辑|只有这样|想到这里')},
    {'key': 'modal', 'core': True,
     'pattern': re.compile(r'(?:(?<!不)(?:必须|需要|应该|只要|就会|可能|可以|能够|无法)|不能)[^。！？!?\n]{0,16}(?:判断|确认|承担|维持|稳住|控制|扩大|失控|带来|造成|理解|默认|回家|进门|核对|筛选|减少|建立|风险|结果|秩序|责任)')},
    {'key': 'abstract', 'core': False,
     'pattern': re.compile(r'(?:任务|条件|风险|来源|逻辑|局面|结果|责任|秩序|规则|信息不足|决策能力)')},
]
REASONING_CHAIN_MIN_HITS = 8
REASONING_CHAIN_CORE_MIN_HITS = 4
REASONING_CHAIN_MIN_BUCKETS = 2
REASONING_CHAIN_PER_KILO = 18

# 系统公告公文腔：只看成片方括号规则/面板行里的硬规则词。
# 这不是特定题材词表；单条严肃规则、日常叙述或普通对话不触发。
NOTICE_FORMAL_PATTERNS = [
    re.compile(r'不得|必须|不可|禁止|严禁|应当|须|需|务必'),
    re.compile(r'当前|本公告|本规则|本系统|提示|任务失败|临时权限|权限|状态|等级'),
    re.compile(r'维持|公共区域|秩序|优先|惩罚|处罚|违规|指令|执行'),
    re.compile(r'被视为|同样计入|计入|承担|责任|单位|撤回|转发|截图'),
]
NOTICE_FORMAL_CORE_PATTERN = re.compile(r'不得|必须|不可|禁止|严禁|应当|须|需|务必|被视为|同样计入|计入')
NOTICE_FORMAL_MIN_LINES = 4
NOTICE_FORMAL_MIN_HITS = 12
NOTICE_FORMAL_CORE_MIN_HITS = 5
NOTICE_FORMAL_PER_KILO = 60

# 过度精炼短段：过度处理样本里常见大量 15 字以内叙述段，且“的/了/就/着/过/呢/吧/啊”等
# 自然连接偏少；对照文本通常保留更多自然连接。此项只做 advisory，禁止机械注水。
OVERCOMPRESSED_PROSE_PARTICLE_PATTERN = re.compile(r'[的了就着过呢吧啊呀嘛]')
OVERCOMPRESSED_PROSE_MIN_CHARS = 1200
OVERCOMPRESSED_PROSE_MIN_PARAS = 45
OVERCOMPRESSED_PROSE_SHORT_MAX_CHARS = 15
OVERCOMPRESSED_PROSE_SHORT_RATIO = 0.58
OVERCOMPRESSED_PROSE_PARTICLE_PER_KILO = 85

# 低连接密度：单纯低功能词会误抓有大量中长句的文本；
# 因此必须叠加“中长句不足”，并只看引号外叙述。这是 overcompressed 的短窗口补充，只做 advisory。
LOW_CONNECTIVE_FUNCTION_TERMS = ['的', '了', '就', '在', '是', '也', '都', '还', '又', '把', '被', '给', '这个', '那个', '里面', '以后', '时候', '现在', '因为', '所以', '但是', '不过', '然后', '已经', '还是', '起来', '出来', '下去']
LOW_CONNECTIVE_PLAIN_TERMS = ['的', '了', '就', '也', '还', '又', '这个', '那个', '东西', '事情', '时候', '里面', '以后', '一下', '一点', '有点', '还是']
LOW_CONNECTIVE_MIN_CHARS = 800
LOW_CONNECTIVE_FUNCTION_PER_KILO = 100
LOW_CONNECTIVE_PLAIN_PER_KILO = 65
LOW_CONNECTIVE_LONG_SENTENCE_CHARS = 30
LOW_CONNECTIVE_LONG_SENTENCE_RATIO = 0.08

# either-or「不是A就是B / 不是A也是B」里紧贴的「是」是连词的一部分，不是肯定项系动词。
# 含「不」以沿用「不是A，也不是B」第二个否定段不算翻转的旧排除。
COMPACT_EITHER_OR_PREV = frozenset('不就也')
# 句尾语气/反问助词；「…，是吗 / 是吧 / 是嘛」是反问尾巴，不是否定后的肯定翻转。
TAG_PARTICLES = frozenset('吗吧嘛')
# 段首确认语；「不是第一次来。是的，他还记得……」里的「是的/是啊」
# 是承接确认，不是「不是 A，是 B」的肯定翻转。
AFFIRMATION_TAG_PARTICLES = frozenset('的啊呀呢')
AFFIRMATION_TAG_BOUNDARY = frozenset(['', '，', ',', '。', '.', '！', '!', '？', '?', '、', '；', ';', '：', ':', '\n', '\r', '\t', ' '])

# 成对引号（台词/系统播报/弹幕）的字符对，stripQuoted 与 quotedRanges 共用一份来源。
# 引号片段一律不跨行（字符类里排掉 \n）：正文漏一个收引号很常见（多段台词只在末段收尾、
# 全半角引号混用都会漏），若允许跨行配对，一个未闭合的开引号会把后面成百上千字全算成
# 「引号内」，让 quotedRanges 的消费方（not-is 跨行扫描）把整段叙述静默豁免掉。
QUOTE_PAIRS = [('「', '」'), ('『', '』'), ('【', '】'), ('“', '”'), ('‘', '’'), ('"', '"'), ("'", "'")]


def _escape_char_class(ch):
    return '\\' + ch if ch in '\\]^-' else ch


QUOTE_SOURCES = [
    '{open}[^{close}\n]*{open_close}'.format(
        open=re.escape(o), close=_escape_char_class(c), open_close=re.escape(c))
    for o, c in QUOTE_PAIRS
]

# ---- 实战测试漏网句式（来源：实战写作抓到的真实漏网例句；2026-07 校准）----
# 校准基线：《万疆》真人正文 20 章（第1/10/20/…/190章）+ demo 前 20 章。
# blocking 规则要求真人语料命中 ≈0（每 20 章 ≤1 处且人工判定确属该句式）；数据见各规则注释。

# 音量反差腔（实战漏网 A）：「声音不高，第一句却稳稳压住了整个大厅。」
# 引号外叙述逐处 blocking；修法是删掉音量铺垫，直接写声音落进场子的具体效果。
# 校准：《万疆》20 章 0 命中，demo 前 20 章 0 命中。
VOICE_CONTRAST_PATTERN = re.compile(r'声音(?:并)?不[大高响亮][^。！？!?\n]{0,16}[却但偏]')

# 否定排比（实战漏网 B）：「没有伴奏，没有和声，没有提词器。」同句 ≥2 个「没有X，」连排；
# 变体「他没炫技，没有那种…架势。他只是唱」先否定铺垫、再用「只是/只会/只有」收肯定。
# 只收「没/没有」段，不收「不X」段；光杆「没」挡两类非否定用法：
#   1) 黏着语素（沉没/淹没/埋没/出没/隐没…）——前字排除；
#   2) 时间惯用语（没多久/没过多久/没等X）——后字排除。
# 校准：《万疆》20 章 0 命中，demo 前 20 章 0 命中。
NEGATION_PARADE_PATTERNS = [
    re.compile(r'(?:没有[^。！？!?\n，,]{1,12}[，,]){2}'),
    re.compile(r'(?<![沉淹埋出隐湮吞覆漫泯])没(?!有?过?多久)(?:有)?[^。！？!?\n，,]{1,12}[，,]\s*没(?!有?过?多久)(?:有)?[^。！？!?\n，,]{1,16}[，,。.][^。！？!?\n，,]{0,6}只(?:是|会|有)'),
]
CROSS_NEGATION_START = re.compile(r'^不是[^。！？!?\n]{1,24}[。！？!?]?$')
CROSS_NEGATION_MIDDLE = re.compile(r'^(?:也|还)不是[^。！？!?\n]{1,24}[。！？!?]?$')
CROSS_NEGATION_END = re.compile(r'^只是[^。！？!?\n]{1,32}[。！？!?]?$')

# 两类常见但不能直接判错的工整框架，只做 advisory。与 blocking 规则不同，这里故意扫描
# 台词：自然点单「不放辣，不放葱」靠对象最短长度排除；更长的同动词清单交语义审查判断功能。
DECISION_FRAME_PATTERN = re.compile(r'至于([㐀-鿿]{1,3})不\1[，,]\s*怎么\1')
REPEATED_NEGATIVE_VERB_PATTERN = re.compile(r'不([㐀-鿿]{1,2})([㐀-鿿]{2,8})[，,]\s*不\1([㐀-鿿]{2,8})')

# 反序对比腔（实战漏网 C）：「是真嗓子，不是修音修出来的」——not-is-comparison 的反序变种。
# 前字排除从 either-or 的 不/就/也 扩展到全部「X是」连词/副词合成词。
# 校准：《万疆》20 章 0 命中，demo 前 20 章 0 命中，按 blocking 实现。
REVERSE_NOT_IS_PATTERN = re.compile(r'是([^。！？!?\n，,]{1,12})[，,]\s*(?:而)?不是([^。！？!?\n]{1,20})')
REVERSE_NOT_IS_PREV_EXCLUDE = frozenset(
    list(COMPACT_EITHER_OR_PREV) +
    list('还只可但于倒像若要正便总老更最算怕凡或即自竟原本仍许净光单尽'))

# 预告式总结收尾（实战漏网 D）：只扫文末窗口（剥引号后可见字数，按行取整）。
# 「正式拉开序幕/帷幕」是场内事件的报幕式陈述，前置 lookbehind 排除。
# 校准：《万疆》20 章排除「正式拉开序幕」2 处报幕句后 0 命中，demo 前 20 章 0 命中。
TRAILER_ENDING_PATTERN = re.compile(
    r'没人知道|谁也不知道|谁也没想到|殊不知|(?:这)?才刚刚开(?:始|头)'
    r'|正(?:朝着|向着)[^。！？!?\n]{0,24}(?:压|涌|袭|逼)(?:了?过去|了?过来|来)'
    r'|(?<!正式)拉开(?:序幕|帷幕)|即将(?:开始|来临|降临)')
TRAILER_ENDING_WINDOW_CHARS = 600

# 章尾状态总结体：把细纲「结尾设定」原样写成总结句收章。与 trailer-ending 共用文末窗口，
# 区别是它盖章过去、trailer-ending 预告将来。
# 校准（文末 600 字窗口，命中逐条人工复核）：qimao 章中段 20000 章命中 1 处（0.005%）、
# heiyan 整篇 3999 篇命中 22 处（0.550%，全部是上列禁用形态）。
TRAILER_SUMMARY_PATTERN = re.compile(
    r'这一(?:夜|天|刻|战|年|局|役)[，,]?[^。！？!?，,\n]{0,6}(?<!命中)(?<!是)注定[^。！？!?\n]{0,8}[。！]'
    r'|就这样[，,][^。！？!?，,\n]{0,8}(?:一切|全部)[^。！？!?，,\n]{0,4}(?:结束了|落幕|收场)[。！]'
    r'|这一切[，,]?[^。！？!?，,\n]{0,6}(?:都)?(?:说明|意味着|结束了)(?!的)(?:(?!什么)[^。！？!?\n]){0,6}[。！]'
    r'|(?:新的篇章|新的旅程|崭新的篇章|新的人生)[^。！？!?\n]{0,6}(?:开始|拉开|展开)'
    r'|命运[^。！？!?\n]{0,6}齿轮')

# 引号强调滥用（实战漏网 E，advisory 密度型，风格照 metaphor-density-tic）：
# 叙述里短词加引号强调（他是被请来"把关"的）。只数叙述层 1-4 字成对引号片段；
# 排除项：【】系统面板载体、引语动词前 6 字/后 3 字邻接的极短台词、引号内含句读的台词、
# 引号外无叙述的行、引号套引号（台词内强调）。全文 ≥3 处报一条。
# 校准：demo 前 20 章 0 章过阈值；《万疆》20 章 2 章过阈值（转述载体，真人也这么写），
# 所以该规则只做 advisory，不升 blocking。
QUOTE_EMPHASIS_MIN_HITS = 3
QUOTE_EMPHASIS_MAX_VISIBLE = 4
QUOTE_EMPHASIS_SPEECH_VERB_PATTERN = re.compile(r'[说道问喊答念叫回吼骂写读唱嘀咕]')

# ---------------------------------------------------------------------------
# review 分类（下游分流）：mechanical = 表面形态确定、就地改写即可；
# semantic = 可能承担叙事功能，需读上下文判断保留还是改。blocking 只能是 mechanical。
# 新增 finding type 必须在此登记，否则运行期直接报错。
# ---------------------------------------------------------------------------
REVIEW_CLASSES = {
    'not-is-comparison': 'mechanical',
    'voice-contrast': 'mechanical',
    'negation-parade': 'mechanical',
    'reverse-not-is': 'mechanical',
    'trailer-ending': 'mechanical',
    'trailer-summary': 'mechanical',
    'em-dash': 'mechanical',
    'long-paragraph': 'mechanical',
    'period-stutter': 'mechanical',
    'micro-action-tic': 'mechanical',
    'negation-pair-tic': 'semantic',
    'cliche-density-tic': 'mechanical',
    'stock-reaction-tic': 'semantic',
    'action-list-tic': 'semantic',
    'abstract-summary-tic': 'semantic',
    'metaphor-density-tic': 'semantic',
    'reasoning-chain-tic': 'semantic',
    'system-notice-formality-tic': 'semantic',
    'overcompressed-prose-tic': 'semantic',
    'low-connective-density-tic': 'semantic',
    'quote-emphasis-tic': 'semantic',
    'formulaic-parallelism': 'semantic',
}

# severity：7 条 blocking（原作生成/去味清理必须清零），其余 advisory（提示，
# justified 的长推理/氛围段可保留）。
SEVERITY = {
    'not-is-comparison': 'blocking',
    'voice-contrast': 'blocking',
    'negation-parade': 'blocking',
    'reverse-not-is': 'blocking',
    'trailer-ending': 'blocking',
    'trailer-summary': 'blocking',
    'em-dash': 'blocking',
    'long-paragraph': 'advisory',
    'period-stutter': 'advisory',
    'micro-action-tic': 'advisory',
    'negation-pair-tic': 'advisory',
    'cliche-density-tic': 'advisory',
    'stock-reaction-tic': 'advisory',
    'action-list-tic': 'advisory',
    'abstract-summary-tic': 'advisory',
    'metaphor-density-tic': 'advisory',
    'reasoning-chain-tic': 'advisory',
    'system-notice-formality-tic': 'advisory',
    'overcompressed-prose-tic': 'advisory',
    'low-connective-density-tic': 'advisory',
    'quote-emphasis-tic': 'advisory',
    'formulaic-parallelism': 'advisory',
}

# 校准状态（B 类纪律）：corpora-calibrated = 阈值经真人语料校准；
# uncalibrated-heuristic = 沿用 Oh Story 原值，未按本项目题材定标，定标前只作观察列。
CALIBRATION = {
    'not-is-comparison': 'corpora-calibrated',
    'voice-contrast': 'corpora-calibrated',        # 《万疆》20 章 0 命中
    'negation-parade': 'corpora-calibrated',       # 《万疆》20 章 0 命中
    'reverse-not-is': 'corpora-calibrated',        # 《万疆》20 章 0 命中
    'trailer-ending': 'corpora-calibrated',        # 《万疆》20 章 0 命中
    'trailer-summary': 'corpora-calibrated',       # 七猫 20000 章 0.005% / 黑岩 3999 篇 0.550%
    'em-dash': 'corpora-calibrated',
    'stock-reaction-tic': 'corpora-calibrated',    # 七猫 5584 章 + 黑岩 3983 篇密度校准
    'long-paragraph': 'uncalibrated-heuristic',
    'period-stutter': 'uncalibrated-heuristic',
    'micro-action-tic': 'uncalibrated-heuristic',
    'negation-pair-tic': 'uncalibrated-heuristic',
    'cliche-density-tic': 'uncalibrated-heuristic',
    'action-list-tic': 'uncalibrated-heuristic',
    'abstract-summary-tic': 'uncalibrated-heuristic',
    'metaphor-density-tic': 'uncalibrated-heuristic',
    'reasoning-chain-tic': 'uncalibrated-heuristic',
    'system-notice-formality-tic': 'uncalibrated-heuristic',
    'overcompressed-prose-tic': 'uncalibrated-heuristic',
    'low-connective-density-tic': 'uncalibrated-heuristic',
    'quote-emphasis-tic': 'corpora-calibrated',    # 《万疆》/demo 过阈值章数复核 → 定 advisory
    'formulaic-parallelism': 'uncalibrated-heuristic',
}


# ---------------------------------------------------------------------------
# 基础工具函数
# ---------------------------------------------------------------------------

_VISIBLE_RE = re.compile(r'[一-鿿Ａ-ｚA-Za-z0-9]')


def visible_length(sentence):
    """可见字数：中日韩/全角字母/ASCII 字母数字计数。"""
    return len(_VISIBLE_RE.findall(sentence))


def compact(text, _limit=80):
    normalized = re.sub(r'\s+', ' ', text).strip()
    return normalized[:77] + '...' if len(normalized) > _limit else normalized


def is_divider(trimmed):
    return bool(re.fullmatch(r'-{3,}', trimmed)) or bool(re.fullmatch(r'[*_]{3,}', trimmed))


_STRUCTURAL_RE = re.compile(r'(#{1,6}\s|>\s?|[-*+]\s|\d+[.)]\s|\|)')
_CHAPTER_HEADING_RE = re.compile(r'第[零一二三四五六七八九十百千万\d]+章(?:\s|_|$)')


def is_structural(trimmed):
    """markdown 结构行（标题/列表/引用/表格）不是叙述正文。"""
    return bool(_STRUCTURAL_RE.match(trimmed)) or bool(_CHAPTER_HEADING_RE.match(trimmed))


def split_sentences(trimmed):
    return [s for s in (p.strip() for p in re.split(r'[。！？!?]', trimmed)) if s]


def sentence_around(text, index):
    start = index
    while start > 0 and text[start - 1] not in STOP_CHARS:
        start -= 1
    end = index
    while end < len(text) and text[end] not in STOP_CHARS:
        end += 1
    return compact(text[start:end].strip())


def count_terms(text, terms):
    count = 0
    for term in terms:
        index = text.find(term)
        while index != -1:
            count += 1
            index = text.find(term, index + len(term))
    return count


def strip_quoted(text):
    """去掉成对引号内的片段（台词/系统播报），只留引号外叙述。"""
    out = text
    for src in QUOTE_SOURCES:
        out = re.sub(src, '', out)
    return out


def mask_quoted(text):
    """把成对引号片段（含引号）替换为等长「？」占位：既豁免引号内台词/播报，又保住原文
    偏移量，供逐处 blocking 规则定位与截取原文摘录（stripQuoted 会移位，不适合定位）。
    占位字符用「？」而不是「。」：占位既要截断各规则的 [^。！？!?…] 否定类，又不能落在
    任何规则的接受位。占位长度不变，故偏移与摘录窗口不漂移。"""
    out = text
    for src in QUOTE_SOURCES:
        out = re.sub(src, lambda m: '？' * len(m.group()), out)
    return out


def quoted_ranges(text):
    """返回引号内片段（含引号本身）的 [start, end) 区间，供 not-is 对比句豁免台词用。"""
    ranges = []
    for src in QUOTE_SOURCES:
        for m in re.finditer(src, text):
            ranges.append((m.start(), m.end()))
    return ranges


def inside_ranges(pos, ranges):
    return any(start <= pos < end for start, end in ranges)


def mask_html_comments(line, open_before, line_index=0, unclosed_openings=frozenset()):
    """把行内 HTML 注释（含 `<!--`、`-->` 本身）换成等长空格；open_before 表示上一行留下
    未闭合注释。unclosed_openings 里的 `<!--` 到文末都没闭合：只抹掉这四个字符，
    后面照常当正文。opened_at 是本行最后一个开始注释的 `<!--` 位置（"行号:列号"），没有则为 None。"""
    out = []
    open_ = open_before
    cursor = 0
    opened_at = None
    while cursor < len(line):
        if open_:
            close = line.find('-->', cursor)
            end = len(line) if close == -1 else close + 3
            out.append(' ' * (end - cursor))
            cursor = end
            if close != -1:
                open_ = False
            continue
        start = line.find('<!--', cursor)
        if start == -1:
            out.append(line[cursor:])
            break
        out.append(line[cursor:start] + '    ')
        cursor = start + 4
        key = '{}:{}'.format(line_index, start)
        if key in unclosed_openings:
            continue
        open_ = True
        opened_at = key
    return ''.join(out), open_, opened_at


def parse_fence_marker(trimmed_line):
    m = re.match(r'(?:`{3,}|~{3,})', trimmed_line)
    if not m:
        return None
    return {'char': m.group()[0], 'length': len(m.group())}


def has_yaml_front_matter(lines):
    if not lines[0] or lines[0].strip() != '---':
        return False
    saw_yaml_field = False
    for i in range(1, min(len(lines), 40)):
        trimmed = lines[i].strip()
        if trimmed == '---':
            return saw_yaml_field
        if re.match(r'[A-Za-z0-9_-]+:\s*', trimmed):
            saw_yaml_field = True
    return False


# ---------------------------------------------------------------------------
# not-is-comparison（「不是A，而是B」及变体）跨行扫描
# ---------------------------------------------------------------------------

def position_for_offset(line_starts, offset):
    low, high = 0, len(line_starts) - 1
    while low <= high:
        mid = (low + high) // 2
        current = line_starts[mid]
        nxt = line_starts[mid + 1] if mid + 1 < len(line_starts) else None
        if offset < current['offset']:
            high = mid - 1
        elif nxt and offset >= nxt['offset']:
            low = mid + 1
        else:
            return {'line': current['lineNo'], 'column': offset - current['offset'] + 1}
    return {'line': line_starts[0]['lineNo'], 'column': 1}


def scan_block(block):
    text = '\n'.join(entry['text'] for entry in block)
    line_starts = []
    cursor = 0
    for entry in block:
        line_starts.append({'offset': cursor, 'lineNo': entry['lineNo']})
        cursor += len(entry['text']) + 1
    return find_not_is_comparisons(text, lambda off: position_for_offset(line_starts, off))


def find_not_is_comparisons(text, get_position):
    findings = []
    quoted = quoted_ranges(text)
    offset = 0

    while offset < len(text):
        start = text.find('不是', offset)
        if start == -1:
            break

        # 引号内是台词/系统播报：口语里「不是A，是B」是自然辩解/反问，不算叙述层 AI 对比句式。
        if inside_ranges(start, quoted):
            offset = start + 2
            continue

        # 避开常见是非问句片段「是不是」。
        if start > 0 and text[start - 1] == '是':
            offset = start + 2
            continue

        candidate = text[start:]
        marker_end = find_positive_flip_end(candidate)

        if marker_end == -1:
            offset = start + 2
            continue

        raw = trim_trailing_noise(extract_finding(candidate, marker_end))
        if len(raw) >= 4:
            position = get_position(start)
            findings.append({
                'line': position['line'],
                'column': position['column'],
                'type': 'not-is-comparison',
                'severity': 'blocking',
                'message': '高频 AI 对比句式；删掉否定铺垫，直接写后项，或改成动作/细节呈现。',
                'excerpt': compact(raw),
            })

        offset = start + max(len(raw), 2)

    return findings


def find_positive_flip_end(candidate):
    index = 2  # 「不是」之后
    scanned = 0
    crossed_separator = False

    while index < len(candidate) and scanned <= MAX_NEGATIVE_SPAN:
        char = candidate[index]

        if starts_with_at(candidate, index, '而是'):
            return index + 2

        if char in SOFT_SEPARATORS:
            nxt = skip_gap(candidate, index + 1)
            if starts_with_at(candidate, nxt, '而是'):
                return nxt + 2
            if (nxt < len(candidate) and candidate[nxt] == '是'
                    and (nxt + 1 >= len(candidate) or candidate[nxt + 1] not in TAG_PARTICLES)
                    and not is_affirmation_tag_at(candidate, nxt)):
                return nxt + 1
            crossed_separator = True

        if char in HARD_SEPARATORS:
            nxt = skip_gap(candidate, index + 1)
            if (nxt < len(candidate) and candidate[nxt] == '是'
                    and (nxt + 1 >= len(candidate) or candidate[nxt + 1] not in TAG_PARTICLES)
                    and not is_affirmation_tag_at(candidate, nxt)):
                return nxt + 1
            if char != '.':
                break
            crossed_separator = True

        if char in STOP_CHARS:
            break

        # 紧凑形式「不是A是B」只在第一从句内（跨分隔符之前）捕捉——跨分隔符后句尾的
        # 「是」（只是/可是/但是/还是/于是/倒是/总是…）是合成词一部分，不是肯定系动词。
        # 主语在前的翻转如「，他是」「，那是」有意不抓：没有词表无法在分隔符局部
        # 区分合成词，误报（逼改写好好的正文）代价比漏掉这种罕见形式更高。
        if (char == '是' and index > 0
                and candidate[index - 1] not in COMPACT_EITHER_OR_PREV
                and not crossed_separator):
            return index + 1

        index += 1
        scanned += 1

    return -1


def extract_finding(candidate, marker_end):
    end = marker_end
    limit = min(len(candidate), marker_end + MAX_POSITIVE_SPAN)
    while end < limit:
        if candidate[end] in STOP_CHARS:
            break
        end += 1
    return candidate[:end]


def starts_with_at(text, index, needle):
    return text[index:index + len(needle)] == needle


def is_affirmation_tag_at(text, index):
    if index >= len(text) or text[index] != '是':
        return False
    particle = text[index + 1] if index + 1 < len(text) else None
    if particle not in AFFIRMATION_TAG_PARTICLES:
        return False
    boundary = text[index + 2] if index + 2 < len(text) else ''
    return boundary in AFFIRMATION_TAG_BOUNDARY


def skip_gap(text, index):
    """跳过行内空白与换行（含空行/段落间距），停在下一个实义字符。"""
    while index < len(text) and (is_inline_space(text[index]) or text[index] == '\n'):
        index += 1
    return index


def is_inline_space(char):
    return char in (' ', '\t', '\r')


def trim_trailing_noise(text):
    return re.sub(r'[\s|）)】\]]+$', '', text)


# ---------------------------------------------------------------------------
# 逐条规则 finder（prose_lines: [{'text': str, 'lineNo': int}, ...]）
# ---------------------------------------------------------------------------

def find_voice_contrast(prose_lines):
    """音量反差腔（实战漏网 A）：引号外叙述逐处 blocking，位置与摘录取自原文
    （mask_quoted 等长占位保偏移；命中片段不含问号占位符，故不会落进占位区）。"""
    findings = []
    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        masked = mask_quoted(text)
        for m in VOICE_CONTRAST_PATTERN.finditer(masked):
            findings.append({
                'line': line_no,
                'column': m.start() + 1,
                'type': 'voice-contrast',
                'severity': 'blocking',
                'message': '音量反差腔：「声音不大/不高…却/但…」是 AI 高频反差模板；删掉音量铺垫，直接写声音落进场子的具体效果（谁停了手、哪排安静了）。',
                'excerpt': compact(text[m.start():m.start() + len(m.group())]),
            })
    return findings


def find_negation_parade(prose_lines):
    """否定排比（实战漏网 B）：同句「没有X，」连排 / 先否定后「只是」收肯定。
    可能在同一片文字上重叠命中，按区间去重只报一次。"""
    findings = []
    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        masked = mask_quoted(text)

        spans = []
        for pattern in NEGATION_PARADE_PATTERNS:
            for m in pattern.finditer(masked):
                spans.append((m.start(), m.start() + len(m.group())))
        spans.sort()

        last_end = -1
        for start, end in spans:
            if start < last_end:
                last_end = max(last_end, end)
                continue
            last_end = end
            findings.append({
                'line': line_no,
                'column': start + 1,
                'type': 'negation-parade',
                'severity': 'blocking',
                'message': '否定排比：「没有X，没有Y…」/「没X，没有Y，只是Z」是 AI 高频排比模板；删掉否定清单，直接写现场实际有什么，最多留一个最有信息量的否定。',
                'excerpt': compact(text[start:end]),
            })
    return findings


def find_formulaic_parallelism(prose_lines):
    findings = []
    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        for pattern, message in (
            (DECISION_FRAME_PATTERN, '「至于X不X，怎么X」把同一决定拆成工整栏目；若只是复述细纲，压成角色当下的一次判断或直接动作。'),
            (REPEATED_NEGATIVE_VERB_PATTERN, '同动词「不V A，不V B」容易写成否定清单；含台词也要按语境复核，保留真正有功能的一项即可。'),
        ):
            for m in pattern.finditer(text):
                findings.append({
                    'line': line_no,
                    'column': m.start() + 1,
                    'type': 'formulaic-parallelism',
                    'severity': 'advisory',
                    'message': message,
                    'excerpt': compact(m.group()),
                })

    # 跨段「不是A / 也不是B / 只是C」既可能是细纲复述，也可能是正常的
    # 辩解、悬念排除或情绪递进。纯句法无法稳定区分，因此只给 advisory，交给语义复核。
    window = []
    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed:
            continue
        if is_divider(trimmed) or is_structural(trimmed):
            window.clear()
            continue
        if window and line_no - window[-1]['lineNo'] > 2:
            window.clear()
        window.append({'text': mask_quoted(trimmed), 'original': trimmed, 'lineNo': line_no})
        if len(window) > 3:
            window.pop(0)
        if len(window) != 3:
            continue
        if (not CROSS_NEGATION_START.match(window[0]['text'])
                or not CROSS_NEGATION_MIDDLE.match(window[1]['text'])
                or not CROSS_NEGATION_END.match(window[2]['text'])):
            continue
        findings.append({
            'line': window[0]['lineNo'],
            'column': 1,
            'type': 'formulaic-parallelism',
            'severity': 'advisory',
            'message': '跨段「不是… / 也不是… / 只是…」可能是工整否定铺排，也可能承担辩解或悬念排除；通读语境，只在重复细纲或拖慢画面时改写。',
            'excerpt': compact(' / '.join(e['original'] for e in window)),
        })
    return findings


def find_reverse_not_is(prose_lines):
    """反序对比腔（实战漏网 C）：「是A，不是B」。排除基建复用 not-is-comparison：
    引号内剥离、「是的/是啊」确认语；前字合成词与反问尾巴见 REVERSE_NOT_IS_PREV_EXCLUDE。"""
    findings = []
    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        masked = mask_quoted(text)
        for m in REVERSE_NOT_IS_PATTERN.finditer(masked):
            start = m.start()
            # 「就是/也是/还是/只是/可是…」里的「是」是合成词一部分，不是肯定项系动词。
            if start > 0 and masked[start - 1] in REVERSE_NOT_IS_PREV_EXCLUDE:
                continue
            # 「是不是…」问句起头。
            if start + 1 < len(masked) and masked[start + 1] == '不':
                continue
            # 「是的，…不是…」承接确认语（复用 not-is 的判定）。
            if is_affirmation_tag_at(masked, start):
                continue
            # 「…，不是吗/不是么/不是吧」反问尾巴。
            if m.group(2) and m.group(2)[0] in '吗么吧':
                continue
            findings.append({
                'line': line_no,
                'column': start + 1,
                'type': 'reverse-not-is',
                'severity': 'blocking',
                'message': '反序对比腔：「是A，不是B」与「不是A，是B」同族；删掉后置否定，直接写 A 的具体表现，或用细节让读者自己对比。',
                'excerpt': compact(text[start:start + len(m.group())]),
            })
    return findings


def find_trailer_ending(prose_lines):
    """预告式总结收尾（实战漏网 D）：只扫文末窗口。从文末往回收集叙述行，
    直到剥引号后的可见字数达到窗口大小（按行取整，边界行整行计入）。"""
    window_lines = []
    accumulated = 0

    i = len(prose_lines) - 1
    while i >= 0 and accumulated < TRAILER_ENDING_WINDOW_CHARS:
        text = prose_lines[i]['text']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            i -= 1
            continue
        window_lines.insert(0, prose_lines[i])
        accumulated += visible_length(strip_quoted(trimmed))
        i -= 1

    findings = []
    for entry in window_lines:
        text, line_no = entry['text'], entry['lineNo']
        masked = mask_quoted(text)
        for m in TRAILER_ENDING_PATTERN.finditer(masked):
            findings.append({
                'line': line_no,
                'column': m.start() + 1,
                'type': 'trailer-ending',
                'severity': 'blocking',
                'message': '预告式总结收尾：「没人知道/才刚刚开始/正朝着…压了过去」是 AI 章尾预告腔；结尾停在具体动作、画面或一句台词上，悬念让事件自己挂住，别替读者预告下一章。',
                'excerpt': compact(text[m.start():m.start() + len(m.group())]),
            })
        for m in TRAILER_SUMMARY_PATTERN.finditer(masked):
            findings.append({
                'line': line_no,
                'column': m.start() + 1,
                'type': 'trailer-summary',
                'severity': 'blocking',
                'message': '章尾状态总结体：「这一夜注定…/这一切都结束了/新的人生才刚刚开始/命运的齿轮」是把细纲的结尾设定原样写成了总结句；结尾设定要落成最后一个具体动作、画面或台词，别替读者盖章。',
                'excerpt': compact(text[m.start():m.start() + len(m.group())]),
            })
    return findings


def find_quote_emphasis_tic(prose_lines):
    """引号强调滥用（实战漏网 E）：统计叙述层 1-4 字成对引号强调片段，全文只报一条
    （密度型分布指纹）。台词类排除见 QUOTE_EMPHASIS_* 常量注释。"""
    hits = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        # 引号外没有叙述的行（独立台词/弹幕流/拟声词连发）整行跳过：
        # 强调滥用是叙述层指纹，没有叙述就无所谓强调。
        if visible_length(strip_quoted(trimmed)) == 0:
            continue
        ranges = quoted_ranges(text)

        for start, end in ranges:
            if text[start] == '【':
                continue  # 系统面板/公告载体，不是强调引号
            # 引号套引号：台词内部的强调属于角色语言，不算叙述层强调滥用。
            if any(s2 <= start and end <= e2 and (s2 != start or e2 != end)
                   for s2, e2 in ranges):
                continue
            inner = text[start + 1:end - 1]
            visible = visible_length(inner)
            if visible < 1 or visible > QUOTE_EMPHASIS_MAX_VISIBLE:
                continue
            if re.search(r'[。！？!?…，,；;：:]', inner):
                continue  # 含句读的是台词/播报，不是强调
            before = text[max(0, start - 6):start]
            after = text[end:end + 3]
            if (QUOTE_EMPHASIS_SPEECH_VERB_PATTERN.search(before)
                    or QUOTE_EMPHASIS_SPEECH_VERB_PATTERN.search(after)):
                continue  # 引语动词邻接=极短台词
            hits += 1
            if first_line is None:
                first_line = line_no
            if len(samples) < 6 and inner not in samples:
                samples.append(inner)

    if hits < QUOTE_EMPHASIS_MIN_HITS:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'quote-emphasis-tic',
        'severity': 'advisory',
        'message': '引号强调滥用：叙述里 1-4 字短词加引号强调 {} 处；只留真正反讽/转述必要的一两处，其余去掉引号直接写，或换成具体动作让读者自己品。'.format(hits),
        'excerpt': compact(' '.join(samples)),
    }]


def find_negation_pair_tic(prose_lines):
    """否定对偶：统计引号外叙述里「没A，也没B」式句子，全文只报一条。"""
    hits = 0
    first_line = None
    samples = []
    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed)
        for m in NEGATION_PAIR_PATTERN.finditer(narrative):
            hits += 1
            if first_line is None:
                first_line = line_no
            if len(samples) < 4:
                samples.append(m.group())
    if hits < NEGATION_PAIR_MIN_HITS:
        return []
    return [{
        'line': first_line,
        'column': 1,
        'type': 'negation-pair-tic',
        'severity': 'advisory',
        'message': '否定对偶偏多：「没A，也没B」式叙述 {} 处；写人物没做什么是英文式节奏，改成他做了什么（留一两处真正要强调的）。'.format(hits),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_micro_action_tic(prose_lines):
    """微动作复读：统计引号外叙述里「了X量词」轻量补语的密度。次数与每千字密度双门槛，
    全文只报一条（这是分布级指纹，不是逐处问题）。"""
    hits = 0
    narrative_chars = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed)
        narrative_chars += visible_length(narrative)
        for m in MICRO_TIC_PATTERN.finditer(narrative):
            hits += 1
            if first_line is None:
                first_line = line_no
            if len(samples) < 6 and m.group() not in samples:
                samples.append(m.group())

    if narrative_chars == 0 or hits < MICRO_TIC_MIN_HITS:
        return []
    per_kilo = (hits / narrative_chars) * 1000
    if per_kilo < MICRO_TIC_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'micro-action-tic',
        'severity': 'advisory',
        'message': '微动作复读：「了下/了一下」式轻量补语 {} 处（{}/千字）；同一反应模板高密度复现是机械指纹，合并动作 beat、换具体细节，别每个动作都补一个轻反应尾巴。'.format(hits, js_tofixed(per_kilo, 1)),
        'excerpt': compact(' '.join(samples)),
    }]


def find_stock_reaction_tic(prose_lines):
    """套式反应细节：统计引号外叙述中通用的部位/声线反应与固定语气比喻。
    这是删除测试的候选集，不是身体描写黑名单；全篇只报一条，保留有动作后果、
    伤势、人物习惯或情节功能的细节。"""
    hits = 0
    narrative_chars = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed)
        narrative_chars += visible_length(narrative)

        for pattern in STOCK_REACTION_PATTERNS:
            for m in pattern.finditer(narrative):
                hits += 1
                if first_line is None:
                    first_line = line_no
                sample = sentence_around(narrative, m.start())
                if len(samples) < 6 and sample and sample not in samples:
                    samples.append(sample)

    if narrative_chars == 0 or hits < STOCK_REACTION_MIN_HITS:
        return []
    per_kilo = (hits / narrative_chars) * 1000
    if per_kilo < STOCK_REACTION_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'stock-reaction-tic',
        'severity': 'advisory',
        'message': '套式反应细节：指尖/指节/喉结/眼圈/声音放轻等通用反应或“平静得像在念”式语气比喻 {} 处（{}/千字）；逐处做删除测试，只标注情绪、不改变选择、关系、物件或动作结果的删掉，不要换部位或同义动作。'.format(hits, js_tofixed(per_kilo, 1)),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_action_list_tic(prose_lines):
    findings = []
    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed).strip()
        if not narrative:
            continue

        verbs = [m.group() for m in ACTION_LIST_VERB_PATTERN.finditer(narrative)]
        if len(verbs) < ACTION_LIST_MIN_HITS:
            continue
        separators = len(re.findall(r'[，、；;]', narrative))
        if separators < ACTION_LIST_MIN_SEPARATORS:
            continue

        findings.append({
            'line': line_no,
            'column': 1,
            'type': 'action-list-tic',
            'severity': 'advisory',
            'message': '监控摄像头式动作清单：同段连续动作动词 {} 个、分隔符 {} 个；合并琐碎步骤，只保留有情绪/情节功能的动作，必要时用角色犹豫、误判或环境反馈做缓冲。'.format(len(verbs), separators),
            'excerpt': compact(' '.join(verbs[:8])),
        })
    return findings


def find_cliche_density_tic(prose_lines):
    """套词密度：统计引号外叙述中的高危禁用词聚集。不是逐词替换器；只在密度高到
    形成模板腔时提示，修法是删总结、换具体动作/物件/对话，不是同义词轮换。"""
    hits = 0
    narrative_chars = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed)
        narrative_chars += visible_length(narrative)

        for pattern in CLICHE_PATTERNS:
            for m in pattern.finditer(narrative):
                hits += 1
                if first_line is None:
                    first_line = line_no
                if len(samples) < 8 and m.group() not in samples:
                    samples.append(m.group())

    if narrative_chars == 0 or hits < CLICHE_DENSITY_MIN_HITS:
        return []
    per_kilo = (hits / narrative_chars) * 1000
    if per_kilo < CLICHE_DENSITY_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'cliche-density-tic',
        'severity': 'advisory',
        'message': '套词密度过高：高危 AI 套词 {} 处（{}/千字）；不要同义词轮换，改成角色当下可见的动作、物件、对话和具体后果。'.format(hits, js_tofixed(per_kilo, 1)),
        'excerpt': compact(' '.join(samples)),
    }]


def find_metaphor_density_tic(prose_lines):
    """比喻密度：统计引号外叙述中“像/好像/仿佛/如同”等比喻标记。
    单个比喻不是问题；高密度成片时才提示，避免把文本改成另一种修辞模板。"""
    hits = 0
    narrative_chars = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed)
        narrative_chars += visible_length(narrative)

        for m in METAPHOR_MARKER_PATTERN.finditer(narrative):
            hits += 1
            if first_line is None:
                first_line = line_no
            sample = sentence_around(narrative, m.start())
            if len(samples) < 6 and sample and sample not in samples:
                samples.append(sample)

        for m in METAPHOR_LIKE_PHRASE_PATTERN.finditer(narrative):
            prefix = narrative[max(0, m.start() - 8):m.start()]
            if re.search(r'好像|像是|像|仿佛|宛如|如同|犹如', prefix):
                continue
            hits += 1
            if first_line is None:
                first_line = line_no
            sample = sentence_around(narrative, m.start())
            if len(samples) < 6 and sample and sample not in samples:
                samples.append(sample)

    if narrative_chars == 0 or hits < METAPHOR_DENSITY_MIN_HITS:
        return []
    per_kilo = (hits / narrative_chars) * 1000
    if per_kilo < METAPHOR_DENSITY_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'metaphor-density-tic',
        'severity': 'advisory',
        'message': '比喻密度过高：像/好像/仿佛/如同等比喻标记 {} 处（{}/千字）；保留最有叙事功能的少数比喻，其余回到具体动作、物件、声音或后果，不要换成新比喻。'.format(hits, js_tofixed(per_kilo, 1)),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_reasoning_chain_tic(prose_lines):
    """解释链密度：统计引号外叙述中“知道/明白/这意味着/必须需要”等判断链。
    全篇只报一条；修法不是补结构虚词，而是把判断落到动作、物件、对话和现场反馈。"""
    hits = 0
    core_hits = 0
    narrative_chars = 0
    first_line = None
    samples = []
    buckets = set()

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed)
        narrative_chars += visible_length(narrative)

        for spec in REASONING_CHAIN_PATTERNS:
            for m in spec['pattern'].finditer(narrative):
                hits += 1
                if spec['core']:
                    core_hits += 1
                buckets.add(spec['key'])
                if first_line is None:
                    first_line = line_no
                sample = compact(m.group())
                if len(samples) < 8 and sample not in samples:
                    samples.append(sample)

    if narrative_chars == 0 or hits < REASONING_CHAIN_MIN_HITS:
        return []
    if core_hits < REASONING_CHAIN_CORE_MIN_HITS or len(buckets) < REASONING_CHAIN_MIN_BUCKETS:
        return []
    per_kilo = (hits / narrative_chars) * 1000
    if per_kilo < REASONING_CHAIN_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'reasoning-chain-tic',
        'severity': 'advisory',
        'message': '解释链密度过高：知道/明白/这意味着/必须/需要等判断链 {} 处（{}/千字）；像逻辑报告时，把判断落到角色当下可见的动作、物件、对话和现场反馈。'.format(hits, js_tofixed(per_kilo, 1)),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_notice_formality_tic(prose_lines):
    """系统/规则行如果连续像 API 文档或政府公文，读者容易闻到机器味。
    修法不是删除规则，而是保留功能后把一部分硬词改成白话或具体后果。"""
    hits = 0
    notice_chars = 0
    notice_lines = 0
    core_hits = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not re.fullmatch(r'【[^】]+】', trimmed):
            continue
        notice_lines += 1
        notice_chars += visible_length(trimmed)

        core_hits += len(NOTICE_FORMAL_CORE_PATTERN.findall(trimmed))

        for pattern in NOTICE_FORMAL_PATTERNS:
            for m in pattern.finditer(trimmed):
                hits += 1
                if first_line is None:
                    first_line = line_no
                sample = compact(m.group())
                if len(samples) < 8 and sample not in samples:
                    samples.append(sample)

    if (notice_lines < NOTICE_FORMAL_MIN_LINES or notice_chars == 0
            or hits < NOTICE_FORMAL_MIN_HITS or core_hits < NOTICE_FORMAL_CORE_MIN_HITS):
        return []
    per_kilo = (hits / notice_chars) * 1000
    if per_kilo < NOTICE_FORMAL_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'system-notice-formality-tic',
        'severity': 'advisory',
        'message': '系统公告公文腔过密：方括号规则行中硬规则词 {} 处（{}/千字）；保留为角色看见的屏幕/公告/规则载体，只在载体内部白话化部分硬词，或补角色当场看懂的具体后果，不改成叙述者解释。'.format(hits, js_tofixed(per_kilo, 1)),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_overcompressed_prose_tic(prose_lines):
    """长文本整体过于“精炼”：短段很多、自然连接偏少，读起来像处理过的梗概/分镜表。
    修法是通读后补断裂处，不是为凑阈值全局加“的/了/就”。"""
    narrative_chars = 0
    narrative_paras = 0
    short_paras = 0
    particles = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if (not trimmed or is_divider(trimmed) or is_structural(trimmed)
                or re.fullmatch(r'【[^】]+】', trimmed)):
            continue
        narrative = strip_quoted(trimmed).strip()
        length = visible_length(narrative)
        if length == 0:
            continue

        if first_line is None:
            first_line = line_no
        narrative_paras += 1
        narrative_chars += length
        if length <= OVERCOMPRESSED_PROSE_SHORT_MAX_CHARS:
            short_paras += 1
            if len(samples) < 6:
                samples.append(narrative)

        particles += len(OVERCOMPRESSED_PROSE_PARTICLE_PATTERN.findall(narrative))

    if (narrative_chars < OVERCOMPRESSED_PROSE_MIN_CHARS
            or narrative_paras < OVERCOMPRESSED_PROSE_MIN_PARAS):
        return []
    short_ratio = short_paras / narrative_paras
    if short_ratio < OVERCOMPRESSED_PROSE_SHORT_RATIO:
        return []
    particle_per_kilo = (particles / narrative_chars) * 1000
    if particle_per_kilo >= OVERCOMPRESSED_PROSE_PARTICLE_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'overcompressed-prose-tic',
        'severity': 'advisory',
        'message': '过度精炼短段：叙述段 {} 个，其中 {} 个≤{}字（{}%），自然连接 {}/千字偏少；先通读判断，确有提纲感再补断裂处和必要结构虚词，有意短镜头可留，别机械注水。'.format(
            narrative_paras, short_paras, OVERCOMPRESSED_PROSE_SHORT_MAX_CHARS,
            js_tofixed(short_ratio * 100, 0), js_tofixed(particle_per_kilo, 1)),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_low_connective_density_tic(prose_lines):
    """低连接密度：长文本/中短窗口里，引号外叙述的功能词和白话连接同时偏低，且缺少
    中长承接句，会呈现“提纲/电报体”分布。修法是恢复必要连接和句群，不是全局补词。"""
    body_chars = 0
    function_hits = 0
    plain_hits = 0
    first_line = None
    sentences = []
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue

        # 只看引号外叙述。台词/弹幕/系统播报可以天然短促，混入统计会把体裁特征误当电报体。
        narrative = strip_quoted(trimmed).strip()
        narrative_len = visible_length(narrative)
        if narrative_len == 0:
            continue

        if first_line is None:
            first_line = line_no
        body_chars += narrative_len
        function_hits += count_terms(narrative, LOW_CONNECTIVE_FUNCTION_TERMS)
        plain_hits += count_terms(narrative, LOW_CONNECTIVE_PLAIN_TERMS)

        for sentence in split_sentences(narrative):
            length = visible_length(sentence)
            if length == 0:
                continue
            sentences.append(length)
            if length <= 12 and len(samples) < 6:
                samples.append(sentence)

    if body_chars < LOW_CONNECTIVE_MIN_CHARS or not sentences:
        return []
    function_per_kilo = (function_hits / body_chars) * 1000
    if function_per_kilo >= LOW_CONNECTIVE_FUNCTION_PER_KILO:
        return []
    plain_per_kilo = (plain_hits / body_chars) * 1000
    if plain_per_kilo >= LOW_CONNECTIVE_PLAIN_PER_KILO:
        return []
    long_sentence_ratio = (sum(1 for ln in sentences if ln >= LOW_CONNECTIVE_LONG_SENTENCE_CHARS)
                           / len(sentences))
    if long_sentence_ratio >= LOW_CONNECTIVE_LONG_SENTENCE_RATIO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'low-connective-density-tic',
        'severity': 'advisory',
        'message': '低连接密度：引号外叙述功能词 {}/千字、白话连接 {}/千字，且≥{}字承接句仅 {}%；容易像提纲/电报体。通读后补必要连接和中长句群，别机械注水。'.format(
            js_tofixed(function_per_kilo, 1), js_tofixed(plain_per_kilo, 1), LOW_CONNECTIVE_LONG_SENTENCE_CHARS,
            js_tofixed(long_sentence_ratio * 100, 0)),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_abstract_summary_tic(prose_lines):
    """抽象总结复读：统计引号外叙述中的高抽象收束模板。全篇只报一条，提醒回到角色
    当下可见的文件、动作、对话或物理后果；不要用命运大词替读者总结。"""
    hits = 0
    narrative_chars = 0
    first_line = None
    samples = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue
        narrative = strip_quoted(trimmed)
        narrative_chars += visible_length(narrative)

        for pattern in ABSTRACT_SUMMARY_PATTERNS:
            for m in pattern.finditer(narrative):
                hits += 1
                if first_line is None:
                    first_line = line_no
                sample = compact(m.group())
                if len(samples) < 6 and sample not in samples:
                    samples.append(sample)

    if narrative_chars == 0 or hits < ABSTRACT_SUMMARY_MIN_HITS:
        return []
    per_kilo = (hits / narrative_chars) * 1000
    if per_kilo < ABSTRACT_SUMMARY_PER_KILO:
        return []

    return [{
        'line': first_line,
        'column': 1,
        'type': 'abstract-summary-tic',
        'severity': 'advisory',
        'message': '抽象总结复读：命运/棋局/这一刻终于明白/才刚刚开始等作者总结 {} 处（{}/千字）；回到角色当下可见的文件、动作、对话或物理后果，别替读者盖章。'.format(hits, js_tofixed(per_kilo, 1)),
        'excerpt': compact(' | '.join(samples)),
    }]


def find_period_stutter(prose_lines):
    findings = []
    run_len = 0
    run_start_line = None
    run_sample = []

    def flush():
        nonlocal run_len, run_start_line, run_sample
        if run_len >= STUTTER_MIN_RUN:
            findings.append({
                'line': run_start_line,
                'column': 1,
                'type': 'period-stutter',
                'severity': 'advisory',
                'message': '碎句号：连续 {} 个短句无呼吸；按目标句长把碎句合并成中长句、补回画面与连接（见本 skill 句长/疏密节奏规则）。'.format(run_len),
                'excerpt': compact(' '.join(run_sample)),
            })
        run_len = 0
        run_start_line = None
        run_sample = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed:
            continue  # 空行是一句一段排版，不打断叙述连贯
        if is_divider(trimmed) or is_structural(trimmed):
            flush()  # 分隔线/markdown 结构行：重置碎句计数
            continue
        narrative = strip_quoted(trimmed)
        if visible_length(narrative) == 0:
            flush()  # 纯对话/弹幕/系统播报：成片短句是正常形态，重置碎句计数
            continue
        # 只数引号外叙述句：混合行（叙述+引号内物件/短台词）的引号外片段仍参与碎句计数。
        for sentence in split_sentences(narrative):
            if visible_length(sentence) <= STUTTER_MAX_SENTENCE:
                if run_len == 0:
                    run_start_line = line_no
                run_len += 1
                if len(run_sample) < 6:
                    run_sample.append(sentence)
            else:
                flush()
    flush()
    return findings


# ---------------------------------------------------------------------------
# 段落级检测 + 文档扫描
# ---------------------------------------------------------------------------

def scan_prose_patterns(prose_lines):
    """段落级检测：碎句号（连续短叙述句）、长段落、破折号（按功能改写，非机械替换）。"""
    findings = []

    for entry in prose_lines:
        text, line_no = entry['text'], entry['lineNo']
        trimmed = text.strip()
        if not trimmed or is_divider(trimmed) or is_structural(trimmed):
            continue

        for dash in re.finditer(r'——|—|--+', text):
            findings.append({
                'line': line_no,
                'column': dash.start() + 1,
                'type': 'em-dash',
                'severity': 'blocking',
                'message': '破折号按功能改写：打断→动作 beat/短句，拖长音→省略或动作，插入说明→逗号/冒号；勿一律改句号。',
                'excerpt': compact(text[max(0, dash.start() - 8):dash.start() + len(dash.group()) + 8]),
            })

        if len(trimmed) > LONG_PARAGRAPH_CHARS:
            findings.append({
                'line': line_no,
                'column': 1,
                'type': 'long-paragraph',
                'severity': 'advisory',
                'message': '段落过长（{} 字）：按镜头/新动作/新线索/视线切换断段，别一段到底。'.format(len(trimmed)),
                'excerpt': compact(trimmed[:40]),
            })

    findings.extend(find_voice_contrast(prose_lines))
    findings.extend(find_negation_parade(prose_lines))
    findings.extend(find_formulaic_parallelism(prose_lines))
    findings.extend(find_reverse_not_is(prose_lines))
    findings.extend(find_trailer_ending(prose_lines))
    findings.extend(find_quote_emphasis_tic(prose_lines))
    findings.extend(find_period_stutter(prose_lines))
    findings.extend(find_micro_action_tic(prose_lines))
    findings.extend(find_negation_pair_tic(prose_lines))
    findings.extend(find_stock_reaction_tic(prose_lines))
    findings.extend(find_action_list_tic(prose_lines))
    findings.extend(find_abstract_summary_tic(prose_lines))
    findings.extend(find_cliche_density_tic(prose_lines))
    findings.extend(find_metaphor_density_tic(prose_lines))
    findings.extend(find_reasoning_chain_tic(prose_lines))
    findings.extend(find_notice_formality_tic(prose_lines))
    findings.extend(find_overcompressed_prose_tic(prose_lines))
    findings.extend(find_low_connective_density_tic(prose_lines))
    return findings


def scan_document(input_text, unclosed_openings=frozenset()):
    """unclosed_openings：到文末都没闭合的 `<!--` 位置（"行号:列号"）。未闭合的注释不是注释，
    否则一个漏写的 `-->` 会把后面整章藏起来；这些位置按正文扫描，只把 `<!--` 本身抹掉。"""
    lines = re.split(r'\r?\n', input_text)
    findings = []
    fence = None
    in_front_matter = has_yaml_front_matter(lines)
    comment_open = False
    comment_start = None
    block = []
    prose_lines = []

    def flush_block():
        nonlocal block
        if not block:
            return
        findings.extend(scan_block(block))
        block = []

    for index, line in enumerate(lines):
        trimmed = line.strip()

        if in_front_matter:
            if index > 0 and trimmed == '---':
                in_front_matter = False
            continue

        fence_marker = parse_fence_marker(trimmed)
        if fence:
            if (fence_marker and fence_marker['char'] == fence['char']
                    and fence_marker['length'] >= fence['length']):
                fence = None
            continue

        if fence_marker and not comment_open:
            flush_block()
            fence = fence_marker
            continue

        # HTML 注释（如 `<!-- 去味:跳过 -->` 豁免标记）是元信息不是正文：注释段等长换成空格
        # 保列号，整行都是注释的直接跳过；注释可跨行。
        masked_text, comment_open, opened_at = mask_html_comments(
            line, comment_open, index, unclosed_openings)
        if opened_at is not None:
            comment_start = opened_at
        if masked_text != line and not masked_text.strip():
            continue

        block.append({'text': masked_text, 'lineNo': index + 1})
        prose_lines.append({'text': masked_text, 'lineNo': index + 1})

    if comment_open and comment_start is not None:
        return scan_document(input_text, unclosed_openings | {comment_start})

    flush_block()
    findings.extend(scan_prose_patterns(prose_lines))
    findings.sort(key=lambda f: (f['line'], f['column']))
    return findings


# ---------------------------------------------------------------------------
# 书目级 .deslop-whitelist 豁免（移植自 style-whitelist.js）
# ---------------------------------------------------------------------------

def load_style_whitelist(file_path):
    """只取本书目录：绝不继承无关工作区或别的书的选择。"""
    parent = os.path.dirname(os.path.abspath(file_path))
    book = os.path.dirname(parent) if os.path.basename(parent) == '正文' else parent
    whitelist_path = os.path.join(book, '.deslop-whitelist')
    try:
        with open(whitelist_path, 'r', encoding='utf-8') as fh:
            lines = [ln.strip() for ln in re.split(r'\r?\n', fh.read())]
        return sorted((ln for ln in lines if ln and not ln.startswith('#')),
                      key=len, reverse=True)
    except FileNotFoundError:
        return []


def style_spans(text, whitelist):
    spans = []
    for literal in whitelist:
        at = text.find(literal)
        while at != -1:
            spans.append((at, at + len(literal)))
            at = text.find(literal, at + 1)
    return spans


def mask_style_text(text, whitelist):
    chars = list(text)
    for start, end in style_spans(text, whitelist):
        chars[start:end] = '？' * (end - start)
    return ''.join(chars)


# ---------------------------------------------------------------------------
# review 分类登记检查（原作运行期 exit(2)，移植版改为抛错——数据/登记问题，不是扫描结果）
# ---------------------------------------------------------------------------

def review_class(finding_type):
    review = REVIEW_CLASSES.get(finding_type)
    if review is None:
        raise RuntimeError(
            "internal error: finding type '{}' has no review class "
            "(add it to REVIEW_CLASSES)".format(finding_type))
    return review


def scan_file(file_path):
    """扫描单个文件，返回带完整元数据（severity/review/calibration）的 finding 列表。"""
    with open(file_path, 'r', encoding='utf-8') as fh:
        input_text = fh.read()
    whitelist = load_style_whitelist(file_path)
    findings = scan_document(mask_style_text(input_text, whitelist))
    out = []
    for finding in findings:
        ftype = finding['type']
        finding['file'] = file_path
        finding['review'] = review_class(ftype)
        finding['calibration'] = CALIBRATION.get(ftype, 'uncalibrated-heuristic')
        out.append(finding)
    return out


def main(argv):
    json_output = False
    files = []

    for arg in argv[1:]:
        if arg == '--check':
            pass  # 与 normalize-punctuation.js 对称保留；检测始终只读
        elif arg == '--list-review-classes':
            sys.stdout.write(json.dumps(REVIEW_CLASSES, ensure_ascii=False, indent=2) + '\n')
            return 0
        elif arg == '--json':
            json_output = True
        elif arg in ('-h', '--help'):
            sys.stdout.write(USAGE + '\n')
            return 0
        elif arg.startswith('-'):
            sys.stderr.write('Unknown option: {}\n{}\n'.format(arg, USAGE.rstrip()))
            return 2
        else:
            files.append(arg)

    if not files:
        sys.stderr.write('No files provided\n{}\n'.format(USAGE.rstrip()))
        return 2

    all_findings = []
    for file_path in files:
        try:
            all_findings.extend(scan_file(file_path))
        except OSError as error:
            sys.stderr.write('{}: unable to read ({})\n'.format(file_path, error))
            return 2

    if json_output:
        sys.stdout.write(json.dumps({'findings': all_findings},
                                    ensure_ascii=False, indent=2) + '\n')
    else:
        for f in all_findings:
            sys.stdout.write(
                '{file}:{line}:{column}: [{severity}] {type} ({review}/{calibration}): '
                '{message} ({excerpt})\n'.format(**f))

    # T4/OBSERVATION 纪律：finding 一律只作报告列，不门控。无论有无 finding，退出码恒为 0。
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
