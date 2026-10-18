# 项目路线图（层 × 路线对照）

> 版本：v0.45（2026-10-18 W1 探针通+W3 洪峰统计，配套 `docs/commercial/collaborator-guide.md` v1.0；指南已随商业研究迁入 `docs/commercial/`）
> 性质：诊断级路线文档。所有"现状"条目均有代码/文档证据；"路线"条目为待审方案，确认后才进开发。
> 冲突仲裁：纪律/禁区以 `docs/commercial/collaborator-guide.md` 为准；并行窗口以本文 §4 撞车矩阵为准。
> 单写者纪律：本文档由问题助手会话持有；其他会话改动须先批注声明（防文档面撞车，稽核建议 2026-10-15）。
> v0.2→v0.3：全文补齐文件路径，新增 §6 关键文件索引。
> v0.4→v0.5（现势同步，经 tff 授权补齐）：#69 已收口（§23：Jmed 三臂回 1.0、闸 1/3、H5.1 税 0）；#70 (b) 批已施加（尺戳 v3.7 入册 29774db，b3 同批，链验 528），三跑 v4g1..3 在跑；#78 判过（v4fL E2 20% 带内）；WP-E 排队条件收敛为 #70 收口；基线 526→528。
> v0.44→v0.45（**W1 探针通+W3 洪峰统计=批3 两项前置收口，W2 本体进行中**，2026-10-18，dev-assistant 按交接包执行，tff 交办）：工作区积压的主会话完工件先做检查点三笔入账（b8d4e13 L3 批1-2 全链/e0fa409 红线6清理批/9e60085 深读批，链验 605/13 现势复核绿后入库，禁区文件零触碰）。**W1**：v0.5-cloud 首跑成功（deepseek-chat@temp0，4 章 11359 tokens **$0.0047**≤授权≈$0.01；沙箱网络坑复现于上一执行环境、本环境直连通 401→带 key 200）；五态对照 16/16=100%（**宿主回填构造性跨端点成立**）；锚闸 2/3（A✅B✅C=**自撤**）；32b 失守域 #27 回补✅、#13 指对自撤、#09 未回——**云端非无条件更强**，仲裁价值=temp0 无拍间方差+部分回补。两个 W2 口径预警：C 降权条款被强守规模型读成「不得报」撤回指令（**降权必须是宿主侧先验，禁写模型可执行禁令**）；自撤行仍入 finding 计数（出口需撤回收纳位）。落 `l3-cloud-fallback-eval.md` §7+§2 行更新。**W3**（零 LLM $0，`l3_c_flood_stats.py`→`l3-c-flood-v01.console.log`）：C249 的 epistemic_pair 分布 dialogue_speculation 35%/speculation_speculation 21%/narrator_speculation 16%/dialogue_dialogue 14%/dialogue_narrator 12%/narrator_narrator 2%；**predicate 集中度 night_watch 204(82%)+key_count 28+key_custody 17=洪峰主体是同一静态事实的枚举配对爆炸**⇒W2 送检面按（章×predicate）聚合可砍一个量级；**锚安全闸警报：ch50 锚③候选恰全落在 dialogue_speculation+speculation_speculation 两类内，此两类不可整类硬压**（narrator_* 75 条移出则锚无损）。判分器仍留 sampling/ 旁路，判据线零改动；W2 判分对照（三臂喂 290 候选只判不找）进行中，读数落 pack §7.12。
> v0.43→v0.44（**批3 测试工作移交其他助手+交接包落档**，2026-10-18 10:10 tff「接下来的测试工作我分配给其他助手」；主会话录入，单写者纪律批注声明）：①交接包 `docs/l3-batch3-handoff-brief.md` v1.0——必读设计清单（三层设计 v0.1/pack §7.9-7.11/云评 v0.1）、已就绪零件表（l3/ 七模块+290 候选 JSON+判分试点+五态核验+人核台账+云端 key User 级已 setx 持久化 35 字符）、工作项 W1（v0.5-cloud 探针：首跑 WinError 10061=执行环境网络拦截非 deepseek 拒连，命令包就绪，ch50+08/12/22，≈$0.01）→W2（批3 判分对照=同一候选集喂三端点只判不找，归因鉴别实验兑现）→W3（C249 洪峰分流零 LLM 先跑）→W4（v0.4.3 temp=0 混淆清洗可选）、纪律红线七条、验收口径；②试点代码已加云端环境变量覆盖（api_key_env/temperature/usd_per_1k，key 不落盘）；③画线主轴终裁（甲死丁讫/批3 读数回答归因后定批4-5 走向）仍在 tff。链验 605 基线移交。
> v0.42→v0.43（**批1-2 收口=l3/ 纯派生层落地+云端回退评估落档**，2026-10-18，tff「确认放行」；主会话录入，单写者纪律批注声明）：交付 `plot_engine/l3/` 七模块+`sampling/l3_corpus_readout.py`+15 单测（写集仅 l3/+tests+sampling 出口，零尺零契约零门禁零 EventLog；偏离设计清单一件=新增 models.py 共享类型防循环 import，入册）。**验证全绿**：链验 **605 passed**（590+15，沙箱权限噪声已鉴别排除）；ch50 回归闸 **3/3 候选全中**；replay 重算**一致**；50 章出数 **A28/B13/C249/D0 共 290**（零 LLM $0）——C249=确定性层全量打标不定罪，配对洪峰留判分层（epistemic_pair 标签随候选走，说辞压制权在判分层=丁批 C 教训的架构化解法）。**归因鉴别实验本体就位**：找对子已收归宿主，批3 旁路判分对照（本地 32b vs NLI vs 云端）喂同一候选集，跳升=配对瓶颈实锤/仍塌=模型判断实锤。**云端评估落档** `docs/l3-cloud-fallback-eval.md` v0.1：混合路由推荐（本地默认+云端仲裁/二审，月成本 $0.01 量级），唯一缺口=`ALEXANDRIA_CLOUD_API_KEY` 未设置，探针批 v0.5-cloud（ch50+3 失守章≈$0.01）与云端读数身份（仲裁旁证 vs 入正秤）**两问待 tff 拍**。pack §7.11。链验基线 590→605。
> v0.41→v0.42（**批1-2 放行 + 云端 API 回退评估立项**，2026-10-18 09:39 tff「确认放行」；主会话录入，单写者纪律批注声明）：①**三层设计批1-2 开工**=`plot_engine/l3/` 纯派生层（scene_index 场景索引+fact_intervals 事实区间；零尺零门禁零契约零 EventLog，宿主侧确定性抽取把"找对子"从模型手里拿走=归因鉴别实验本体；v042 四件套随档移交：区间回填/宿主标注/D 族/送检面注释剥离）；②**云端 API 回退评估**（tff 指令：评估出问题章节回退云端的可能性）——范围=本地 32b 失守/漂移章（锚掉/区间失守/高误报章）转云端强模型重判的路由设计+成本测算+与"核验器降级不退休"纪律的兼容性，评估落档后拍板权在 tff；③混淆变量勘误在册（pack §7.10 归因三混淆：temperature≈2.0 未控/失败集中配对非判断/样本面）——批1-2 即鉴别实验，v0.4.3（temp=0+分族单跑）作可选并行小批。链验 590/13 为基线，批1-2 新增代码配测试同步入链。
> v0.40→v0.41（**丁批收口=v0.4.2 双臂复跑第二读数+预拍判决执行：甲不上、换抽取架构批1-2 申报**，2026-10-18，tff「确认拍丁」「3090 只跑 14B」「多 agent 并行」；主会话录入，单写者纪律批注声明）：`sampling/level3_pilot.py --v042`=V041+裁量规 3 条+宿主标注层（只标注不删除）+D 族章内逐字重复块（零 LLM）+端点/模型环境变量覆盖（章头 model@host 戳）。**A 臂 32b@11500 权威读数**：区间失守 0/20、五态 29/29=100% 逐字可核（四代延续）、出数 52→29、ch50 回归闸 2/3（B 锚②采样漂移性掉锚=bogus 配对顶替，smoke 双跑均 3/3）。**第二读数人核 29 条全量**：裸 13/29=44.8%／剔锚 42.3%／**宿主标注剔除后 12/22=54.5%**／OK 章 45.5%（v041 勘误后 43.6%）；宿主标注 7 发 6 中 1 误杀（ch08-B 链断式到达，人核维持真）；**召回 70.6%**（17 真域覆 12+新增 ch20-B，丢 5 域）；C 配对纪律提示词层压不住（新出 4 条可同真误报）；送检面卫生发现=注释行可被引用（批1-2 候选）。**B 臂 14b@3090 对照**：出数 23、区间失守 3 章（14b 守规弱，构造性锁死照样兜住）、ch50 锚 1/3——**失败形态跨模型规格一致**。**预拍判决执行：丁未推过线（54.5% 距上秤门槛远、召回受损）→问题收敛到模型语义判断能力本身→甲（OBS 分层上秤）不上，换抽取架构=`docs/l3-consistency-three-layer-design.md` 批1-2（plot_engine/l3/ 纯派生零尺零门禁）申报待 tff 放行**；v042 四件套（区间回填/宿主标注/D 族/端点戳）作已验证零件随档移交。归档 `level3-pilot-v042{,-qwen14b,-smoke1,-smoke2,-smoke3}.console.log`；pack §7.9 勘误+#19 翻转+§7.10。链验 590/13 不变（纯 sampling 旁路面）。
> v0.39→v0.40（**拍丁=先修三规则+补重复检测再复跑出第二读数**，2026-10-18 08:54 tff「确认拍丁」；主会话录入，单写者纪律批注声明）：**丁批开工**——①A 章首豁免=宿主侧纯代码按区间行位过滤（参照 Oh Story `storyctl.py:141` deslop_skipped 豁免窗口+豁免收窄纪律）；②B 回查失守=inkos 式双保险（提示词加「引文本身含到达叙述即撤回该发现」指令 + 宿主核验引文2 含到达模式标 withdrawn_candidate，`models/observation.ts` REVIEW_SOURCE_MISMATCH 同款）；③C 说辞-物证区分=抽取 schema 加认识论槽位（叙述者事实/角色台词/物证），矛盾只判同层，台词 vs 物证标 suspense 不判穿帮（FactTrack 分层）；④**补章内重复检测**=纯文本相似度脚本零 LLM（参照 Oh Story `check-degeneration.js` 逐行复读指纹+台词豁免），覆盖 ch15/20 实证空白的第四族 D；⑤复跑 v0.4.2（smoke 双跑+全量）+第二读数人核抽样。理论上限【勘误：原「33/39≈84.6%」算术错误，误报压制=移出分母非转真；且 #19 翻转后基数为 17 真 22 误报】：三规则明确对应 12 条全压制=17/27=63.0%，加 C 配对纪律 3 条=17/24=70.8%（pack §7.9 勘误）；**tff 亲拍后序：若丁推不过线=问题在模型语义判断能力本身，甲更不该上，换抽取架构（三层设计批1-2 接上）**。全程 sampling/ 旁路，零尺零契约零门禁，链验 590/13 不动。
> v0.38→v0.39（**乙′人核批收口=52 条 finding 逐条回原文出精确率**，2026-10-18，tff「可以批0」「注意模块稳定性」；主会话录入，单写者纪律批注声明）：**纯读档批，零代码零 schema 零尺面改动，链验 590/13 不动**。范围=OK 章 32 条全量+NH 章 B 族 4+ch50 锚 3 共 39 条（NH 章 A/C 13 条不在范围记未核）。判定口径先钉后判（章中硬切=真/章首开场=误报/说辞 vs 物证=误报/单处陈述=误报/有到达叙述=误报/同对重复=真注枚举膨胀）。**总分账 18 真/21 误报=46.2%，剔锚 15/36=41.7%，OK 章 14/32=43.8%；分族 A 58.3%（OK 54.5%）/B 全量 50.0%/C 33.3%（OK 28.6%）**——v0.2 抽检 5/5 乐观读数被全量证伪；B 族「人核前不可上秤」纪律兑现，上秤 50%=§7.8 反例非个例是半面。**三条口径发现入册喂批1-2 设计**：①A 缺章首豁免（误报 5 中 3）②C 混淆角色说辞/物证对立与作者矛盾（误报 10 中 5，真矛盾域集中钥匙数量/保管口径，与 ch50 锚③同型）③B 到达叙述被引为无到达证据（误报 6 中 4=回查失守）。**两注记**：ch42 人核抓出模型漏检真矛盾一例（张三/赵六「一把在我这里/由我保管」）=召回面缺口；ch50 锚③「叙事自觉」裁量空间记档（锚定义若修需 tff 拍）。落档 `docs/level3-fn-calibration-pack.md` §7.9。**画线主轴仍摊 tff**：三族精确率不足以直接接管线，但误报结构高度集中=三条皆为触发器/抽取层规则非模型能力上限；候选（甲 OBS 排序分层上秤 / 新丁=先修三规则再复跑出第二读数）待裁。
> v0.37→v0.38（**乙′人核批放行 + location 入 schema 方向拍板=影子投影执行 + 版本纪律五级入册**，2026-10-17，tff「可以批0」「location入schema是必须的」；主会话录入，单写者纪律批注声明）：①**批0 乙′人核开**——v0.4.1 OK 章 32 条 finding 回原文逐条核对出精确率（至少 B 族全量+A/C 抽样，CPU 零成本纯读档），B 族出数人核前不可上秤纪律不变；②**L3 三层架构设计落档** `docs/l3-consistency-three-layer-design.md` v0.1（纸面零码改）：新子包 `plot_engine/l3/`（scene_index/fact_intervals/interval_conflicts/temporal_checks/triggers，前两批纯派生零尺零门禁；判分器留 sampling/ 旁路带戳；与既有 `consistency.py`=L0 账面自洽划界）；施工六批登记，批 6 TCSP/因果重器暂缓至开牌日后；③**版本纪律五级**（设计文档 §8）：字段升级不废历史——原始章节不可变/旧抽取分代分表不删/新投影影子重生/新报告钉版本三元组（extractor+schema+auditor）/历史校准不冒充新版；**作废的是跨口径比较资格不是历史证据**；location=additive 变更，旧记录 None 记「未抽取」不记「不存在」（禁回填假账）；④**批4 影子化重构**：4a 影子重抽（sampling/ 零生产接触）→4b 平行校准→4c 切流（R1 红线拍拍的是切流时点非加字段本身）。画线主轴（甲 vs 丙）仍未裁；链验 590/13 不变（纯文档面）。
> v0.36→v0.37（**甲′批收口=l3-presence-v0.4.1 B 族加码，掉锚补正+误报面入册**，2026-10-17，tff「确认甲」）：改动最小性=区间形态/回填/A/C 指令全不动，仅 B 族补 C 族同款「逐条摘出再回查」；v0.4 掉锚根因假设（提示词只给 C 族做法）**证实**——ch50 B 锚三拍全回（冒烟双跑+全量）且配对即已知场景重置锚。读数：区间失守 0/20、五态对照 52 条=100% 逐字可核（构造性不变）、总出数 26(v0.2)→50(v0.4)→52(v0.4.1)、B 族出数章 5→12。**代价入册**：抽眼即中 B 族显性误报一例（ch21 把「门被推开王五走进来」的到达叙述本身引为「无到达叙述」证据）⇒**B 族出数人核前不可上秤；乙′（人核出精确率）由可选转必做**（至少 B 族全量+OK 章 A/C 抽样），丙′失去存在理由。归档 `level3-pilot-v041{,-smoke1,-smoke2}.console.log`（50186 tokens 本地 $0）；pack §7.8。链验 590/13 不变（纯 sampling 面）。**待拍板：是否开乙′人核批（CPU 零成本、纯读档回原文核对）。**
> v0.35→v0.36（**v0.4 行号区间批=四参照项目穿帮方案调研 + inkos 形态本地化验证跑**，2026-10-17，tff 认可方向并钉两风险）：调研结论（只读，Explore 报告入 pack §7.7 谱系）=四家无一单点解，共性=**账本注入预防+结构化对账检出+正则兜底**三层，其中 inkos「行号区间→宿主回填」直击我方「逐字纪律不可提示词强制」死穴。`sampling/level3_pilot.py --v04` 落 **l3-presence-v0.4**（送检每行 `001` 前缀、模型只交 ≤2 行区间、同进程对 `_section_body` 内存行列表回填=行号基准构造性锁死；v0.2/v0.3 常量逐字在档）。读数：**区间失守 0/20 章**；五态对照组（`quote_verify.py` 不退休，跳线口径 `>=160`→`==160`）v0.4=**50/50 逐字可核（100%）、stitched 及以上 0=回填管线零 bug**——引文纪律问题在区间形态下消失而非改善；但 **ch50 回归闸 B 锚 0/3（冒烟双跑+全量，系统性掉锚）**，与 v0.1「格式压死发现面」同型入册；出数面 26→50（NH 6/6、OK 12/13）**精确率未验**（ch06 见枚举膨胀形态），32 条 OK 章新 finding 未抽检、缺口如实记。归档 `level3-pilot-v04{,-smoke1,-smoke2}.console.log`（49764 tokens 本地 $0）。**三候选甲′（B 族加码再跑）/乙′（先人核 32 条出精确率）/丙′（区间仅 A/C、B 回引文式）摊 tff，画线权未动**。链验 590/13 不变（纯 sampling 面）。
> v0.34→v0.35（**a=程序侧引文核验离线兑现 + §7.5 严重度判读修正**，2026-10-17，tff「确认a」）：`sampling/quote_verify.py`（stdlib re+difflib，**autojunk 必关**否则高频汉字被当噪声压低匹配率）五态分层两代归档 console——v0.2=逐字46%+微改写42%+拼接2+疑编造1（4%）、v0.3=逐字50%+微改写41%+拼接1+疑编造2（6%）⇒「v0.3 兑现率崩到 34%」证伪=纯子串口径假阴性（多一个「的」字即 miss），**两代锚可定位率 ≈94–96% 相当；乙批判负维持但定性从「有害」改「无增益」**。抽案证 U 态≠编造（ch50 B 项锚真、压缩过甚）=机器判不动需人裁；核验层天花板=分层引文纪律、不裁矛盾真伪（真伪唯一人核证据=v0.2 抽检 5/5，样本小）。可组合画线形态=**甲+分层**（逐字层免抽检入 OBS/改写拼接层轻核/U 层精核），终拍权在 tff。pack §7.6 落档；链验 590/13 不变。
> v0.33→v0.34（**乙批收口=l3-presence-v0.3 判负入册，三路裁定批全部走完**，2026-10-17）：pack 新增 §7.5——锚点回归 ch50 3/3 通过（收紧未压死发现面）；但配对硬规**未兑现**：机检引文逐字命中率 v0.2=46%→v0.3=34%（`sampling/quote_hit_probe.py` 两代 console 复算），失配形态=「语义摘述披着引文的皮」（所指真、字面拼接）；分布位移（NH 2/6→1/6、OK 6/13→8/13 成员大换血）落在已实证的双跑拍间方差地板上，不定量归因。**乙批判负=措辞侧收紧对 32b 不成立**，「配对 vs 所指」分离须换实现层：三候选 a 程序侧逐字核验过滤（戳 v0.3.1）/ b 引文降级为定位线索（尺面删逐字规）/ c 停批回甲（OBS 观察挂起）——摊 tff，§7 甲/丙画线候选仍未裁。归档 `sampling/level3-pilot-v03.console.log`（20 章 48425 tokens 本地 $0）。链验 590/13 基线不变。
> v0.32→v0.33（**B5 码批兑现=章闭环裁决状态机进确认闸面**，2026-10-17，tff「1确认开」）：`metrics.adjudication_table` 派生菜单（committed=ready/处置章=needs_decision+四动作候选；判死族按 dump **抬头** ARC_CONFLICT/needs_arc_replan 认——r4/r5 实证抬头与 trace_status 两行不同源，按 trace 分会给大纲债章错开改契约出口）；backend jobs 表零迁移复用确认闸 CAS 状态机（`CHAPTER_DECISION_TASK`/`decide_chapter` 裁决即确认/`latest_chapter_decision` 按章查账）；readout `--adjudicate [--project --db]`（含已裁标记）+`--decide=章:动作`（非法动作拒、无项目拒，非提示性）。真数据：r4=ready6/决策4（ch02/07/10→arc_replan、ch05→contract_edit）；临时库端到端入账/查账/复裁取最新全通。**判据线零改动、管线不消费此账**（接线=另批申报）。链验 **590**/backend **13**（+2/+3 基线更新）。乙批（v0.3 验证跑）仍在跑，收口另批。
> v0.31→v0.32（**第二批三路裁定入库：B5 开、level3 画线走乙、云车道挂起**，2026-10-17，tff 原话「1确认开；2选择乙；3按照你的建议」）：①**B5 码批开禁**——章闭环裁决候选动作菜单（接受现状/重排大纲/改契约/手工改写）进确认闸面，需求证据=ch10 恒死 0/5 + 试点/五批暴露的人工处置面，任务 #107；②**乙=先磨尺再上秤**：`sampling/level3_pilot.py` 落 l3-presence-**v0.3**（v0.2 逐字留档可切；收紧=逐字引文≤30 字+分族配对硬规+C 族逐条摘出再两两对照），验证跑已发射（20 章 wpe50ch 集，本地 32b 零成本，`level3-pilot-v03.console.log` 归档），ch50 回归闸冒烟=双跑 2/3 与 3/3——**单发有拍间方差（temp 0.2 下单跑掉 B 锚、复跑全中），收口读数按「锚点须多拍确认」口径如实记录**；跑完出精确率对比读数，画线仍待 tff 终拍；③**云抽取车道挂起=不转正不追加预算**，重提条件=Phase 1 排期真用到抽取车道时备「补批凑一致性 vs 按方向证据立项」材料。链验基线 588/backend 10。
> v0.30→v0.31（**②WP-F B 档首条 B2 读者已知阅读卡兑现=三路拍板全部走完**，2026-10-17）：`plot_engine/metrics.py` 落 `render_reader_card`/`reader_card`（reader_ledger→截至章纯派生投影，账外 fact 一律记「未感知」不兜假账，卡面自标不进闸）、`plot_engine/readout.py` 接 `--reader-card [--ch=N]`（N>0=replay 截至章，replay 不可得直接抛）；测试 `test_reader_card.py` 首轮即抓到实 bug（facts 为 Dict，迭代出键非 Fact）。验证读数（归档真数据）：r5 终态=已知1/示意9/未感知2（12 fact）；wpe50ch `--ch=25` replay 中点同分布、截至 ch23（最后 committed 章）⇒投影随快照走实证。零尺零契约零门禁零上游回写，接口面=additive 两函数+一 CLI 分支。链验 **587→588**/backend **10** 全绿。兑现指针回写 `docs/wp-f-oh-story-digest.md`（含 B5 第二顺位申报触发=①③已满足⇒**向 tff 申报 B5 待拍板**）。**待拍板队列**：①level3 画线三候选甲/乙/丙；②抽取车道是否立项 Phase 1 量产配置（新预算决策）；③B5 章闭环裁决状态机进确认闸面（B 档第二顺位，触发已达）。
> v0.29→v0.30（**①level3 试点落档 + ③S 批五批复现收口**，2026-10-17）：①`sampling/level3_pilot.py`+`level3-pilot.console.log`（72b1f97）：l3-presence-**v0.2** 两步式（v0.1 单趟冒烟 ch50 全漏入册），20 章实跑——**ch50 三锚点全中、NH 出数 2/6、OK 出数 6/13 且抽检 5/5 全为真穿帮**（进阁重排/未进场先在/钥匙持有人矛盾）⇒ committed 章机检盲区实证；画线三候选（OBS 排序/v0.3 收紧配对/接管线批）摊 tff，画线权未动。③`sampling/ep1v39pv2c-r4/r5`（§16 收口）：五批 OK 5/9/4/6/6 均值 **60%**（五批全 ≥4=本地三代最大值，**方向复现成立**）、E2 是 1/5（**规模不翻**）、ch10 恒死 0/5 同键族 needs_arc_replan（作者债再证）、恒绿 ch01/03/08/09；成本 r4 $0.034/r5 $0.042，含误跑半批 S 线累计 ≈$0.19 ≤ 授权 $0.25；**发射事故入册 §15**（bash -c 内嵌引号坑⇒多步发射一律落脚本文件，残片隔离 `_badlaunch_132347`，误删半批 console.log 违成本归档纪律如实记录）。发射窗口码面冻结未破，链验 **587**/backend **10** 基线不变。**下一步**：②WP-F B 档首条 **B2 读者已知派生阅读卡**码批（解冻后开工）；「抽取车道升云是否立项 Phase 1 量产配置」=新预算决策待 tff 拍板。
> v0.28→v0.29（**三路待拍板项裁定入库：①level3 C 旁路试点开、③选 B（5 批复现验证）、②先选 1 条验证+其余排期到点提醒**，2026-10-17，tff 原话「1开，3B，2先选一条，验证，后面的7条排期，在适当的时候提醒我拍板」）：①`docs/level3-fn-calibration-pack.md` 追加放行记录：C 候选旁路试点开跑（dump 离线、不经 validator、零管线改动；本地 Ollama 实调，L3 提示词带新尺戳 l3-presence-v0.1 归档=R2 纪律）；③**云端预算首次正式授权**：S 批面续跑 r4/r5（含既有 r1..3 凑 ≥5 批复现），预估 ≤$0.25，命令与禁跑警示更新见 `docs/phase0-live-run-10ch.md` §15 复现块——跑批窗口内码面冻结；②WP-F B 档首条=主会话择 **B2 读者已知派生阅读卡渲染器**（纯派生读数形态，同构已验证的全-A 读数批：零尺零契约零门禁、不回写上游——接口稳定性纪律下代价最小、可在归档上直接验证；B5 裁决出口列第二顺位，待 ①③ 读数收口后申报）、其余 B1/B3/B4/B5/B6/B7 排期与提醒触发条件登记 `docs/wp-f-oh-story-digest.md`。执行序=①试点（GPU 独占时段）→③r4→r5 串跑→②B2 码批（复现收口后才动码面）。链验 **587**/backend **10** 基线不变。
> v0.27→v0.28（**WP-F A 档 7 条纯文档兑现：`docs/wp-f-a-docs-absorption.md` v0.1**，2026-10-17）：§A1 有声书选题 SOP（四步法，<15 本稀疏硬闸最高判「中」，黄金三章→3 章样章测听服完读）/§A2 EM 卡五字段→爽点需求草案（缺口=情绪链实读侧，归题5B/5C 债不预做决定）/§A3 拆文库权威面与投影面分离规格/§A4 双层追踪对照表（6 行对照，映射 B1/B2/B3 候选）/§A5 门禁三原则（写前门+兜底网、宁可漏拦不可误伤、只判结构不判值）/§A6 决策笔记纪律（proposed/implemented/rejected，被否先写最强理由，翻转另开互链；本会话「保留选项登记」即日按此补强）/§A7 预注册可证伪实验协议（门槛发射前冻结、判负入档不合入，建议 WP-C 激活时引用为模板）。七条合一时文件落档（ponytail：最少文件），A 档边界重申：零码改、零 GPU、不进任何判据；B 档仍另批申报、C 档维持搁置。链验 **587**/backend **10** 不动。
> v0.26→v0.27（**三路并行批拍板入库：爽点工程全-A 确认、level3_fn 先修闸序确认、WP-F C 档整组搁置保留；备选选项全部登记保留不否决 + tff 新增分层硬纪律**，2026-10-17）：tff 裁定「全部按推荐选项确认；其他选择未经验证，保留后续选择可能性记录在文档」。①`docs/r8-2-shuangdian-adjudication-pack.md` 加拍板记录：六题全-A（纯派生离线读数表，写集仅 metrics/readout 接线+tests，不新建文件），B/C 逐题登记保留选项+重提条件，**题5C 抽取爽点事件族红线维持独立拍板**；②`docs/level3-fn-calibration-pack.md` 加拍板记录：先修闸序后重谈 A/B/C，执行时新证据=闸序是**协议原文**（05 §7:178「仅在 Level 1/2 通过后运行」）⇒ 落为 05 §7 文本修订批（I1/I2 一字不动、HARD 集合零增删、Commit 语义零变化），A/B/C 全列保留候选（B 的 R1 尺面红线独立拍板）；③`docs/wp-f-oh-story-digest.md` 加拍板记录：A 档=纯文档队列、B 档=另申报不变、C1-C6 整组搁置保留（C3 触 WP-C 面维持禁区）。**随批新纪律（tff 原话入册）**：「一定要注意各个模块之间的接口契约的稳定性，单独修改一个模块不会影响整个架构」——本批两码动作均按此执行：闸序改动收敛在 `_review` 触发条件单点（签名/其他层零动）；读数批只消费既有模型的公开产物、不回写任何上游模块。**两兑现批已落码**：闸序批（a6fdeb7 拍板→38bb1ce：05 §7 文本+CHANGELOG 生效记录+validator 单点+用例反转，live 无传入方 today 行为零影响）；爽点读数批（af7e923：`metrics.thrill_table`/`r3r6_flags`+`readout --thrill`，零新文件零尺零契约零门禁，钩命中率复用 `validator._hook_ok` 同谓词；首跑 S 批 r2 钩 10/10、wpe50ch 46/46、ch50 死章 replay 不可得记「-」不入分母）。链验 **585→587**/backend **10**。
> v0.25→v0.26（**三路并行助手收口：WP-F 落档 + 爽点工程/level3_fn 两份拍板材料包（纸面，零码改）**，2026-10-17，tff 授权「启动多agent并行开发」后首个并行批）：①`docs/wp-f-oh-story-digest.md` v0.1（WP-F 吸收 digest，裁定④兑现）——三块方法论行号级取证（拆榜 story-long-scan/SKILL.md:11、双层追踪 tracking_commit.py:617-645 与我方 fact.py:21-22/ledger.py:41 近乎同构、门禁 storyctl.py:236 needs_decision 作者裁决出口=确认闸最缺交互形态）；落地候选 A 档 7 条纯文档/B 档 7 条需码批申报/C 档 6 条需拍板，禁区逐项排除（其拆文提示词渗尺=读数作废，ai_flavor 5 件全套排除=WP-C 同面）。②`docs/r8-2-shuangdian-adjudication-pack.md` v0.1——材料二②6 问逐题选项+推荐全 A（beat_type 五值纯派生/不进闸复用「伪定量不阻断」先例/复用已冻 tension_actual 但首期不落账/全派生尺 v3.9 零 bump——「从正文抽爽点标记」列红线单拍/双通道只定可输出可追溯线）；关键发现=models/ledger.py:103 注释自证承接位存在但全库零写入方；末尾附全 A 组合最小实施方案（离线爽点读数表 6 项，写集仅 metrics+readout 接线，零 GPU）。③`docs/level3-fn-calibration-pack.md` v0.1——ch50 三锚点回码对实；漏检根因链五条（location 键不在 PAYLOAD_SCHEMA、归档 event.db 198 事件 location 全 None、**闸序硬伤 validator.py:828：level3_fn 仅零 HARD 时触发，ch50 恰带 3 HARD 接了也轮不到**）；三候选实标定：A 纯派生但分布无分离度（线 ≥2 误报 10/13）、B 触尺面且存量样本为零、C 旁路试点唯一覆盖规则漂移族；(a) 可不等 T1 新事件型（降级子集存在）。三件均为纸面待拍板，链验 585/backend 10 不动。
> v0.24→v0.25（**S 批开批收口：tff 裁定「入库+开 S 批」，云端抽取三采样 OK 5/9/4=均值 60%、E2 首判是；本地 14B 抽取漏读改判领衔成分、ch10 为唯一两车道恒死作者债**，2026-10-17）：`sampling/ep1v39pv2c-r1..3`（`--lane cloud` deepseek-flash，Writer 仍本地 qwen2.5:14b、尺 v3.9/夹具 ladder-v5b/具名清单 patch-v2/闸 job#4 全不动，戳 instr-v2-cloud）。读数：OK 5/9/4、修复率 0.40/1.00/0.25、E2/E3=r1 否、**r2 是（9/10）**、r3 否——方差巨大（4–9），按「只按一致性下结论」纪律 E2 不翻是，但 r2 整体落在本地六批分布（2–4）之外。**归因改判**：本地六批恒死 ch02 在云端 r2 **round 1 patch_write 即 committed=True**（具名清单一次兑现）、ch07 同谱系脱死 ⇒ 此前「型别偷懒/整场没写」相当部分实为**抽取漏读/误标**（Writer 正文未变、只换眼）；**ch10 三车道批恒 ARC**（死键族 001|knowledge|f2+002|belief|f1，强眼补写后再失败）=纯作者输入债标本，止损条款按章收窄至 ch10。**成本证据**：云端 65–115k tokens/批=$0.027–0.047，三批合计 <$0.10（r1 云端段为仪表缺口未计量，§15 注估算）；发射前修两处=deepseek.router.json 顶层 `_comment` 键炸 `from_config`（数据修法移出）、review.py 收口行加云端 tokens/cost 分列（纯打印，链验 585 复绿）。Phase 1 候选入 §15：抽取车道升云+Writer 保本地，上线前 ≥5 批复现。链验 **585**/backend **10**。读数全文：报告 §15；审查材料后记同步。
> v0.23→v0.24（**#98 具名化三采样收口：E2 三批仍否，但归因收敛——错绑消退、残余转「型别偷懒」主导；S 批三条件齐，提交 tff 拍板**，2026-10-16）：`sampling/ep1v39pv2-r1..3`（闸 job#4、尺 v3.9、修订环 patch-v2）。OK 2/3/4（均值 30% vs v1 33%/批前 33%）、修复率 0.33/0.50/0.75、E2/E3 三批同否、G1/G3=True G2=False——**具名化没抬起 OK 率，改的是失败结构**。① **仪表微修双兑现**：死章 dump 现带 `## Revision` 段（r1 ch02 round1 `action=patch_write items=…` 直证「清单到过 Writer」=S 批条件①可快照核），空清单 patch_write 三批 0 复现（非契约层全落 rewrite_chapter）。② **归因谱系转移**（稳定死项 vs 终轮 Proposals 三批机检）：v1=「型别对但绑错 actor/事实」领衔→v2=「actor/事实绑对、仍写低档型别偷懒」领衔（INFERS 顶 OBSERVES/READS、IS_TOLD 顶 known 档，directive 已明写「可达该档只有 OBSERVES/READS、INFERS 只到 suspected」照旧走捷径）；**ch07 死项迁移=具名化修复错绑的单点实证**（v1 三批恒死 `003|belief|f3`→v2 该 BELIEVES 已正确绑定出现、改死他项）、**ch05 两批转 OK**。残余硬骨：ch02 `003|belief|f8` 三批整场没写+疑错绑（两代六批同判死项逐字一致，全场最硬单章）。③ **S 批（#97 云端强模型）三条件读数全齐**：①已过（dump 直证）、②残余属模型服从面非尺债（D10 保证可达才入契约）非夹具债（同项六批逐字同判）、③本地 3 批复现 ⇒ **是否开 S 批（只换 model、尺/夹具/清单不动、单独分表）待 tff 拍板**，本会话不擅自动云端预算。链验 **585**/backend **10** 不动。读数全文：`docs/phase0-live-run-10ch.md` §14。
> v0.22→v0.23（**#98 清单具名化批落盘：修订环 patch-v1→v2，指令面先于模型面**，2026-10-16）：§13 归因三分型共性=型别模型会写、绑定在裸编号清单面系统性串位（非结构不可写）⇒ 走比 #97 S 批（云端强模型）更便宜的指令面梯级。06 §4.2 补写清单改**具名形态**下发（actor 角色名、target 事实命题、档位可达型别从 KNOWLEDGE_RANK_CAP/FIELD_EVENT_TYPES 单源表筛出并点名排除不可达），items 全编号键 + EXTRACTION_RULER v3.9 一字未动；两条 §13 入册微修随批落：① 判死 ArcConflict **携带已跑轮次 trace**（quarantine 收 `exc.trace` ⇒ dump `## Revision` 段可见补写开火=S 批条件①，不再只靠消息文本）②失败升非契约层清单必空 ⇒ 落回该层默认动作、patch_write **不空挂开火**（消 r1 ch05 round 2 artifact）。run.log 戳 patch-v1→v2，读数与 `sampling/ep1v39p-rN` 分表禁混读。链验 **581→585**（trace 1/空清单 1/directive 具名 1/state 兜底 1）、backend 10 不变。**下一步**：patch-v2 冻结面 10 章×3 采样（复用闸单 job#4、同模型 qwen2.5:14b）→ §14 回写（与 patch-v1/批前三表并列、只按一致性下结论）→ 判负是否收敛为纯 needs_arc_replan / 「整场没写」型是否随具名化消失 → 再定 #97 S 批三条件。纯指令面批，零尺改。
> v0.21→v0.22（**patch-v1 冻结面三采样收口：E2 三批仍否，判负形态收敛为 4 章三批逐字同键的 needs_arc_replan；止损不触发，归因转指令面**，2026-10-16）：码批见 7cacd96。读数（`sampling/ep1v39p-r1..3`，闸单 **job#4** 复用、尺 v3.9 未 bump、批前/批后分表不混读）：OK 3/4/3、修复率 0.50/0.33/0.50、E2/E3 三批同否、G1/G3=True G2=False——**patch_write 没抬起 OK 率，它改的是判负形态**。① **稳定死章 4/4 三批 item 键逐字一致**（ch02 `003|belief|f8`、ch04 `003|knowledge|f7`、ch07 `003|belief|f3`、ch10 `001|knowledge|f2 + 002|belief|f1`），全部 needs_arc_replan，判死零误触发、零静默吞；② **ch09 两批转 OK**=裁定 2「BELIEVES 未必写不出」实证（rounds=0 时代从未给过 Writer 带清单的机会），r3 复死亦在补写一轮之后；③ **止损条款不触发**：ch05 三批恒 NEEDS_HUMAN（非补写可救型）、ch03/06/09 漂移，判负**未**收敛为纯 needs_arc_replan ⇒ Phase 0 结论维持「规模不成立」，不改判「管线成立、夹具 Arc 需作者重开」。④ **归因三分型**（r1 全量 + r2 复核）：型别偷懒（INFERS 顶 IS_TOLD/档位欠）、actor/事实错绑（对型事件绑错角色或错 fact）、整场没写（双 actor 零命中）——共性=**型别模型会写、绑定在编号清单面上系统性串位**，非结构不可写 ⇒ **#98 清单具名化批（指令面：状态取角色名 + KNOWLEDGE_RANK_CAP 导出的档位上限提示 + 显式 actor 归属；戳 patch-v1→v2）排在 #97 S 批（模型面）之前**，S 批三条件须等具名化后复采再判。⑤ 入册不动码两项（批内码面冻结，随 #98 微批）：ArcConflict 判死章 dump **无 `## Revision` 段**（`experiment.py` quarantine 传 trace=None、raise 不带部分轨迹）⇒ S 批条件①目前只能以判死消息 + rounds≥1 + Round0/终稿 diff 佐证；Writer 层根因在无 items 时仍挂 `action=patch_write` 空清单开火（r1 ch05 round 2），功能≈rewrite_chapter，读数须按 items 空/非空区分。链验 **581**/backend **10** 不动。读数全文：`docs/phase0-live-run-10ch.md` §13。
> v0.20→v0.21（**材料四落纸：第三次冻结会议程=修订动作批，串联分诊口径 tff 拍板**，2026-10-16）：§12 复议条件满足（残余≠0 且跨批稳定），「Revision 动作缺失」定案为结构缺口。拍板核心：**串联分诊——定向补写优先，同条 must_change 补写后再失败一次 → 该章标 needs_arc_replan 落作者桌面**（自动降期望维持否决=洗标准；实验夹具 Arc 归作者）。fail-fast 章（ch09 型）并入同一机制：先给一轮带缺失清单的补写（rounds=0 从未让 Writer 试过），再死才重规划。仪表：dump Revision 行记 `action=patch_write`+清单摘要；修复率分母剔 fail-fast 章。**EXTRACTION_RULER 维持 v3.9 不 bump**（抽取通道未动），读数按修订动作批前/批后分表；规划未变**复用闸单 job#4**。次序承诺：06 协议文本→一码批（补写请求+分诊计数+仪表，每型一正一反）→离线全绿→10 章×3→§13 回写；若 E2 仍否且判负收敛为纯 needs_arc_replan，Phase 0 结论改判「管线成立、夹具 Arc 需作者重开」进 R8。议程全文：`docs/freeze-meeting-and-r8-briefs.md` 材料四。纯文档批，零码改，基线 573/10 不动。
> v0.19→v0.20（**v3.9 冻结面三采样落锤：E2 三批同判否，但判负面收敛为两型确定结构；4A 缓议解除**，2026-10-16）：同模型（qwen2.5:14b@213）同规划（ladder-v5b，闸单 **job#4** plan_sha256=3a2ce082…64a666）三跑 `sampling/ep1v39-r1..3`——OK 4/4/2、ARC_CONFLICT 恒 ch09、E2/E3 三批同假、失败谱系三批同（H5.3 领衔 26/24/26）。均值 33% vs v3.8 26.7%，方向为正、规模仍不成立。**核心发现=章级确定性**：6/10 章三批定性完全一致（ch01/08 恒 OK、ch04/05/07/10 恒 FAIL、ch09 恒 ARC_CONFLICT），仅 ch02/03/06 漂移——错尺修正后判负主体非模型抖动，而是契约-模型失配确定章 + Arc 强制项 fail-fast（ch09 BELIEVES，批④路由实弹：1 轮判死替代烧满 3 轮）。抽取面 2A/提升仪表零触发（reattributed=0/规则提升=0）。**4A「Revision 动作缺失」残余≠0 实证、缓议解除**，材料=`docs/phase0-live-run-10ch.md` §12；下批候选=must_change 类失败的 Writer 定向补写动作 vs Arc 层重规划（06 §4 空白）。纯读数批，零码改，基线 573/10 不动。
> v0.18→v0.19（**码批 v3.9 落盘：材料三裁定 1A+1B/2A/3A+3B 三项全兑现，协议+尺+夹具收口**，2026-10-16）：① 1A+1B（bbff679）——`K_RANK`/`KNOWLEDGE_RANK_CAP` 单源表入 models/contract（三消费者=derive/validator/夹具），derive D10 强化=knowledge Δ 档位可达性前置拦截（不可达→ArcConflict，不再烧三轮修订以 H5.3 现形），validator `_change_implemented` knowledge 分支改「实现事件∧终态达档」与 H2.2 同谓词（③族 rank 互斥 6 章结构性清零；belief 分支与 H5.7 宽集合不动）；② 2A（26cc1bb）——抽取后处理 `_reattribute_is_told`（说话人段落判定+唯一听者换挂，保守 no-op，`is_told_reattributed` 记账入 malformed；三漏斗位与 `_promote_infers` 同点），**尺戳 v3.8→v3.9-is-told-reattach**，v3.6 提示词面失败实证 #70 教训后走结构面；③ 3A+3B（79341e0）——derive D12 越界钉拦截（forbidden∪hidden-gate 的 fact 钉 OBSERVES/READS→ArcConflict；IS_TOLD/INFERS 豁免），夹具 ch10 作者改钉 IS_TOLD Δ known→believed、ch06 补证人钉，LADDER_VERSION→**ladder-v5b-ch10istold**/half 同步 bump（50ch 经 import 继承未动）。协议文本：04 D10 扩展+新增 D12、05 H5.3 双判据注记、06 Arc 归属登记补两行、spec CHANGELOG v3.9 生效记录。4A（Revision 动作缺失）按裁定缓议，待新尺三采样残余读数。链验 **561→573**（#87+5/#88+5/#89+2）、backend 10 不动。**下一步**：新 plan_sha256（ladder-v5b 面）呈报开闸 → 10 章×3 采样（同模型，v3.9 尺表）→ §12 回写 → 4A 复议。
> v0.17→v0.18（**第二次冻结会议程草案落纸（材料三）**，2026-10-16）：§11 三机制转成 4 项拍板单——#1 H5.3↔H2.2 rank 互斥（建议 D10 rank 可达性强化 + `_change_implemented` 对齐，A+B 同批；C 自动降期望否决=洗标准）；#2 IS_TOLD actor 翻转（建议抽取后处理结构面确定性修复——提示词面已被 #70 封死、模型面 M 批已判无效）；#3 越界钉（建议 derive 拦截 forbidden-fact 的 OBSERVES/READS 钉 + 夹具 ch10 作者改钉并行）；#4 Revision 动作缺失**缓议**（先修尺重采样，残余≈0 则系错尺幻影）。拍板后次序承诺：1+2+3A 一码批（尺戳 v3.8→v3.9）→ 夹具改钉 → 离线全绿 → 10 章三采样新尺号 → §12 回写。议程：`docs/freeze-meeting-and-r8-briefs.md` 材料三。纯文档批，零码改，基线 561/10 不动。
> v0.16→v0.17（**43 未决章次重放机检全裁决：判负主力定性为「尺与约定」，非 Writer**，2026-10-16）：`event.db` 重放 pre-state + dump 头部重建终轮契约/提案 + 复跑 `_review`，**43/43 rule 集复现一致**。Δ 面判决 ①1（仅 M ch07）·②18（抽取型漂移/∉实现表）·③19（actor 翻转 13 + H5.3↔H2.2 rank 互斥 6）·④4·ARC 判死 1；钉面 ①≈21/②≈16/③≈9，①大头=**结构性写不出的越界钉**（ch10 OBSERVES 隐藏身份、ch07 钉2）。H5.7 24 条逐对终稿：真漏 8/误报仅 4（含翻案：halfch08 改判抽取幻觉——段序陷阱 Round 0≠终稿；m32ch06 改判真漏；「H5.4 契约自冲突」否决=漏驱动）。三大机制入冻结会：**H5.3↔H2.2 一致性修订=头号议程（尺面）**、IS_TOLD actor 约定入抽取 prompt、derive 越界钉拦截候选。读数：`docs/phase0-live-run-10ch.md` §11；取证脚本 `sampling/_forensics/adjudicate.py`。本节零码改，基线 561/10 不动。
> v0.15→v0.16（**归因双批落地：模型面与结构面（任务单过重）双双出局**，2026-10-16）：M 批（32B 全密度@213，复用闸单 jobs#1）OK 3/10、E2/E3 假、Contract/Arc 13 领衔、坏料仅 9 条——规模×2.3 换不来提交率，抽取清洁度不是约束；H 批（半密度契约@本地 14b，新夹具 `experiment_10ch_half`/ladder-v4-halfdensity，must_change 18→12、强制事件 16→11，新闸单 jobs#3——#2 因 payload 双重编码 fail-closed 作废留痕）OK 仍 3/10、修复率 **0.00**——契约减半未少一章未决，「任务单过重」不成立。剩余解释位=**钉判模态错位（尺/Writer 面）vs Revision 对 must_change 类无动作（06 §4 空白实证）**，冻结会议程据此收敛。读数表+复现：`docs/phase0-live-run-10ch.md` §10；归档 `sampling/attr_m32b_r1/`、`sampling/attr_half_r1/`。链验 **557→561**（半密度夹具 4 钉）；backend 10 不动。
> v0.14→v0.15（**v3.8 冻结面三采样判负落锤 + 确认闸首战实弹**，2026-10-16）：同模型同规划三跑（`sampling/ep1v38-r1..r3`，@213）读数一致——OK 率 30/20/30%，E2/E3 三批同假，失败主体三批同谱系 Contract/Arc 类（H5.3 领衔）；**十章规模在 v3.8 契约面修订后仍判否**，与 WP-E 五十章判负同向（缺陷在契约/Arc 语义层，非夹具）。本地 3090 跨硬件横批（`sampling/ep1v38-l1`，方案 A）读数同分布——测量面跨机器稳定；效率 213:3090≈1:2.6。G1 命中，08 §7 允许讨论改架构（候选=Level-3 在场一致性/WP-F/must_change 归属空白）。**确认闸首用**：闸单 jobs#1（plan_sha256=8c085a8a…606d2，confirmed_by=tff），四批 run.log 全带过闸戳。读数表+复现：`docs/phase0-live-run-10ch.md` §9（v3.8 尺表；fix-1/wpe50ch 旧尺对照分表不并列）。
> v0.13→v0.14（**R8 #1 确认闸码批收口**，2026-10-16）：设计稿 `docs/confirmation-gate-design.md` v1.0 冻结（tff 拍板 Q1–Q5 全按推荐；Q3=A `review.py` 入口 preflight，WP-0 写集例外亲批）；批1 `backend/noveldb.py` jobs 闸账四函数（add_confirm_job/get_job/latest_job/set_job_status CAS，状态机 queued→confirmed／queued→rejected→queued 代码层枚举，**SQL 零迁移**）；批2 `review --live` 前置检查——无 confirmed job/规划 sha256 不符→退出码 4+stderr 拦截原因含当前哈希，过闸戳进 run.log（归档自证）；--live 调用者全带 `--gate-project`（离线/救援不过闸）；验收 §4 四项全绿，链验 plot_engine **554→557**（+3 拦截态用例）、backend **6→10**（CAS 并发单赢等 4 用例）。Q5：闸前存量归档（wpe50ch/bo_ctrl）豁免，闸只卡新跑。
> v0.12→v0.13（**WP-A v3.8 码批收口**，2026-10-16）：epoch_1 八批全落库（A models／B plot reducer+联动钩子+abandon 内核／C validator H9 族+RULE_TO_LEVEL／D derive D11 单源漂移拦截／E 抽取尺 bump **v3.6→v3.8-foreshadow-payload**（v3.7 烧号不复用纪律兑现）／F 裁定 2A 阶梯四级化／G 协议文本 01/03/04/05/06/08/09+CHANGELOG 入册／H 全链复验）。链验 **531→554**（+23 用例，一正一反纪律达标）。**尺面纪律**：v3.8 起读数与 v3.6 分表，禁并列。fixture 层 EPOCH 字符串暂留 epoch_0（生效记录=09 §3.1+CHANGELOG，数据面首条 epoch_1 事件写入时按 09 §5 走）。弃伏工作台接线留 WP-0（5A 内核已落）。
> v0.11→v0.12（冻结会散会，2026-10-15，tff 照单拍板）：六项裁定 1A（04 补 D10 + derive 前置拦截 + 06 §4 登记归属）/ 2A（06 §5 阶梯删一级，四级）/ 3 追认（H8.x 只记 by_rule，08 勘误回填）/ 4A（derive 单源 gate→due，**v3.8 键名定稿 `due_by_chapter` 入 FORESHADOWING_SET payload**）/ 5A（新增 `abandon_foreshadowing` 动作入阶梯）/ 6A（ArcProgress 随 epoch_1 只冻字段，V3/V6 迁移断言）；确认闸落点追认 = **backend jobs 表不进 EventLog（不触发 T1）**。拍板记录：`docs/freeze-meeting-and-r8-briefs.md` 末节。**WP-A v3.8 码批即刻开工**；`docs/commercial/project-roadmap.md` 加陈旧快照注记（正典单一写者不变）。
> v0.10→v0.11（WP-E 收口，2026-10-15）：**50 章压测跑完并判负**——终态 OK 13／NEEDS_HUMAN 36／ARC_CONFLICT 1（ch09），处置率 74%，干净口径 E2 20%（§8 名义提交率 26%），E2/E3 退出闸 False；失败主体在契约/Arc 面（§6：74 对 20，H5.3×110 居首）= 冻结会议程 #1 must_change 归属空白的实据；**ladder-v5 夹具验证通过**（构造级不可达章：无；后 40 章 OK 率 27.5% 不劣于前 10 章 20%）；判死章位漂移（v4gL=ch05 vs wpe=ch09）入 temp0 自洽失稳同谱系；finish=length 可疑 8 次（上限 2400 vs 实出 ~5600–6000）对表 instr-v3 预注册。读数与复现：`docs/phase0-50ch-stress.md`；归档 `sampling/wpe50ch/`。**并表禁照旧**：50 章读数不与 v4 十章带 [20,40] 同表。
> v0.9→v0.10（三线并行助手收口，2026-10-15）：①**稽核判定 WP-E 读数可采信**（de88d9e 写集核验过、尺面/仲裁面自 90ea95b 零改动、ladder-v5 不回环独立复算成立；纪律注记：**50 章 E2 不得与 10 章 ladder-v4 基线同表并列**——阶梯规模不可比；对标文档 6 处行数/路径陈旧留下轮文档批）；②**H8.x 九桶议题闭合**：08 §4 原文核对确认九项全是状态账、无抽取桶，c176dc6 口径 A（只记 by_rule）协议合法，CANON 兜底才是越权——冻结会仅追认 08 勘误回填（`docs/freeze-meeting-and-r8-briefs.md` 议程#3）；③ instr-v3 预注册文档落档（`docs/r4-guided-decoding-prereg.md`）；④ 冻结会 6 项议程 + R8 前两项澄清提纲落档（21f1736），其中确认闸"确认事件进 EventLog=触发 T1 升 epoch"一条**可能追进冻结会**。另：collaborator-guide 已实际移至 `docs/commercial/`（工作树移动未提交），roadmap 旧路径引用待随该移动一并勘误；⑤ **WP-D 已交付**（开发助手）：`docs/wp-d-noveldb-mapping.md` v0.4 §8 六条实施偏差回填，主线独立复跑验收 6/6 全绿（snapshot_every=5 非逐章宁缺勿造、末态台账计数、noveldb 零改动、tension_to_real 锁定、单 story 自动发现、projects 主键=id@noveldb.py:24），backend 代码待其落库。
> v0.8→v0.9（现势同步）：**#79 已收口**（de88d9e：ladder-v5 五十章不回环夹具 + `review --fixture` 接线，离线 50/50 全绿、0 修订轮、E1–E6 全 True，链 526→531）；**WP-E 已起跑**：`sampling/wpe50ch/`（@213 暖隧道 qwen2.5:14b，instr-v2 默认，五十字节 ladder-v5），跑批期间 `plot_engine/` 全冻结。
> v0.7→v0.8（tff 裁定四则，2026-10-15）：①**商业姿态定案**——不进通用工具市场，纵深走垂直有声书交付（Phase 3 行更新）；②**R8 并入**为路线（§2 末），六项按 确认闸>爽点工程>量化去味>拆文库>扫榜>旧稿导入 入队；③**temp0 重复/刀锋失稳的前置 schema（grammar-constrained decoding）登记为 R4 后期补充**（L4 注）；④WP-E **放行**，硬前置 #79（50 章阶梯夹具）开工；oh-story 吸收通道 = WP-F 入矩阵。
> v0.6→v0.7（撤销批同步，tff 确认）：#70 (b) 型别批**判负已撤销**（§24：双遍闸 1/3、两臂 Jmed~0.60、失稳由型别互翻扩为事件存在性抖动；revert 29774db=90ea95b，尺退 v3.6@`llm_extract.py:49`，b3 同撤，链验回 526）；#70 收口→WP-A/WP-E 串行条件满足；v4gL 本地臂 E2 10% 带外（v3.7 尺面判负旁证）。补记入 §24。
> v0.5→v0.6（tff 指令，2026-10-15）：§6 新增"商业化分析文档"索引（docs/commercial/ 9 份 + refrence_projects/ 代码基线）
> v0.3→v0.4（稽核修正）：① WP-A 尺戳改 v3.8 并串行于在队 #70 之后（v3.7 已被 `_patch_b12_typecriteria.diff:9-13` 占用）；② §4 删除错误的 WP-A/WP-B 互斥（WP-B 写集为 `llm.py`/router，不改 `llm_extract.py`）、补登在跑批次 #69/#70/b3/#78；③ WP-D 开放问题①关闭（等 S2 §2.3 `novel_chapters` 表）；④ WP-E 排队至 #69/#70/#78 收口后；⑤ 立单写者纪律；⑥ 指南基线 525→526 已代为刷新。

---

## 0. 总路线一张图

```
双轨制：
轨道一（生成侧）plot_engine/：协议冻结的内核已建 → 语义层补强 → 质量收敛 → 商业验证
轨道二（交付侧）backend/ 有声书管线：骨架已建（S2 进行中）→ 接生成侧产物 → TTS/QC/导出 → 读者产品

当前位置：
  轨道一 = 用户四阶段计划的 "Phase 0 收尾 + Phase 2 部分超前 + Phase 1 语义层未开工"
  轨道二 = docs/migration-plan.md 的 S2（后端骨架+核心移植）阶段，与 plot_engine 未接线
```

---

## 1. 层 × 路线总矩阵

| 层 | 模块（路径） | 现状 | 对应路线 | 路线阶段 |
|---|---|---|---|---|
| L0 契约层 | `plot_engine/models/` + `alexandria-spec-v0.2/` | epoch_0 冻结（v0.2 spec） | **R0 契约演进路线**：epoch_1 设计（伏笔/人物目标/冲突网络） | Phase 1 前置 |
| L1 状态内核 | `plot_engine/reducer.py`、`plot_engine/reducers/`、`store.py`、`eventlog.py`、`replay.py`、`commit.py`、`reduce.py`、`canonical.py`、`consistency.py` | 完整；`reducers/plot.py` 为 no-op | **R1 剧情语义路线**：伏笔生命周期、人物目标落账 | Phase 1 主线 |
| L2 判定层 | `plot_engine/validator.py`、`derive.py`、`sceneplan.py`、`classify.py` | L1/L2 确定性判定完整 | **R2 判定扩展路线**：剧情规则族（H9.x）；L3 LLM 软判定预留 | Phase 1 伴随 |
| L3 修订层 | `plot_engine/revision.py`、`revision_actions.py`、`rescue.py` | 归因阶梯 + 人工重入完整 | **R3 定向返工路线**：arc 级自动动作从"升级人工"走向"半自动" | Phase 1→2 |
| L4 生成层 | `plot_engine/llm.py`、`llm_writer.py`、`llm_extract.py`、`extract.py`、`markup.py`、`markup_channel.py`、`writer.py`、`live.py` | 角色路由 + 后置校验完整；无前置约束；尺戳 v3.6 | **R4 生成约束路线**：guided decoding 接入；模型 bakeoff 收敛 | Phase 2 前置 |
| L5 测量层 | `plot_engine/metrics.py`、`prose_audit.py`、`ai_flavor_lint.py`、`ai_flavor_baseline.py`、`instr.py`、`instr_cli.py`、`instr_measure.py`、`instr_replay.py`、`reanchor.py`、`counterfactual.py`、`diff_audit.py`、`fixture_audit.py`、`model_probe.py`、`experiment.py`、`review.py` | 体系最完整，尺号制度化 | **R5 测量运营路线**：50 章压测、lint 扩充、盲测运营 | 贯穿全程 |
| L6 出口层 | `plot_engine/reading.py`、`sample.py`、`readout.py`、`viewer.py`、`blind_review.py` | 内部出口完整 | **R6 交付接线路线**：state.db → `backend/noveldb.py` 导入 → 有声书管线 | Phase 2→3 |
| 轨道二 | `backend/`（`noveldb.py`、`asr_qc.py`、`context_manager.py`、`domain.py`、`emotion_map.py`、`master_audio.py`、`projects.py`、`rules.py`、`sync_state.py`） | S2 骨架阶段 | **R7 有声书管线路线**：`docs/migration-plan.md` S2→S3→S4 | 并行轨 |

---

## 2. 各层路线详述

### L0 契约层 → R0 契约演进路线

- **现状**：`plot_engine/models/` 逐字对齐 `alexandria-spec-v0.2/` 十份协议（`00_principles.md`～`10_world_state_protocol.md`）；epoch_0 已于 2026-10-08 重冻结（`alexandria-spec-v0.2/09_versioning.md` §2.5）。
- **路线**：
  1. epoch_1 设计稿（**已产出**：`docs/epoch1-foreshadow-design.md` v0.2，待审查冻结）：伏笔生命周期、人物级目标模型、冲突关系边（`plot_engine/models/fact.py:31` 注明 Phase 0 静态）。
  2. 契约冻结会：一次性定稿，触发条件 T1/T2/T5 全部命中，必须升 epoch。
  3. 迁移脚本 + 全量 Replay 验证（`09_versioning.md` V3/V5/V6 强制）。
- **里程碑**：epoch_1 冻结 = Phase 1 全线的开工枪（记入 `alexandria-spec-v0.2/CHANGELOG.md`）。
- **验收**：迁移后旧 epoch_0 数据只读可 replay（V4/V6）。

### L1 状态内核 → R1 剧情语义路线

- **现状**：四族 reducer 完整纯函数（`plot_engine/reducers/knowledge.py`、`belief.py`、`world.py`、`reader.py`）；`plot_engine/reducers/plot.py` no-op；`plot_engine/models/state.py:64` `foreshadowing: List[str]` 占位且**当前无任何写入方**（`plot_engine/llm_extract.py` `PAYLOAD_SCHEMA` 不含剧情事件），存量迁移对象为空。
- **路线**：
  1. `reducers/plot.py` 语义化（设计见 `docs/epoch1-foreshadow-design.md` §3）。
  2. 人物目标落账（`models/ledger.py` 新增 `CharacterGoalEntry`，设计稿 §2.2）。
  3. 弧进度状态机：`models/state.py:59` `active_arc` 从 Any 升级为结构化 ArcProgress（P1）。
- **验收**：planted→paid 全生命周期纯函数单测（新 `plot_engine/tests/test_reducer_plot.py`）；replay parity 不回归（`plot_engine/tests/test_replay.py`）。

### L2 判定层 → R2 判定扩展路线

- **现状**：`plot_engine/validator.py` 沙盒模拟 + HARD/SOFT/OBS 三层判定完整；H5.3 生成守卫与 `derive.py` 共用映射表（`models/contract.py` `FIELD_EVENT_TYPES`）。
- **路线**：
  1. 新增剧情 HARD 族 H9.1–H9.4（设计稿 §4）：伏笔逾期未回收（对照 `models/contract.py:17` `KnowledgeGate.must_reveal_by_chapter`）、无源回收、伏笔过浅；**登记处为 `plot_engine/revision.py:38` `RULE_TO_LEVEL`**（不在 validator.py，稽核修正）。
  2. L3 LLM-as-validator 软判定（`validator.py` 头部预留，Phase 2 接入，仅 SOFT/OBSERVATION）。
- **验收**：新规则族 1 正 1 反用例（增补 `plot_engine/tests/test_validator_l1.py`）；规则进 `RULE_TO_LEVEL` 归因表。

### L3 修订层 → R3 定向返工路线

- **现状**：`plot_engine/revision.py` Root Cause 八层归因 + 阶梯动作 + `max_rounds=3`（`models/revision.py:26`）+ 人工升级；`plot_engine/rescue.py` 人工重入（链尾守卫）。
- **路线**：
  1. arc 级半自动动作：弧张力偏离时自动重派生后续章 Contract（挂既有 `derive.py`）。
  2. "阶段性奖励"机制：以弧里程碑（`models/contract.py` `TurningPoint` 达成）驱动后续章目标注入。
- **验收**：定向返工后首轮通过率（first_pass，`metrics.py` 决策桶）不劣化；`RevisionTrace` 全程可回放。

### L4 生成层 → R4 生成约束路线

- **现状**：后置校验链完整但无前置约束；`plot_engine/llm.py:40` `extra_body` 透传口已在；温度定点×1000（`llm.py:39`）；**尺/生成锁 qwen2.5:14b（指南 §1.5）**；`EXTRACTION_RULER` 当前 **v3.8-foreshadow-payload**（`llm_extract.py:49`，WP-A 批次 E；#69 入册 f326660 v3.6；#70 曾上 v3.7/29774db，判负撤销 90ea95b，戳号 v3.7 已烧不复用；v3.8 读数与 v3.6 分表）。
- **路线**：
  1. extract 角色接 guided decoding（vLLM `guided_json`/`structured_outputs`，Ollama 降级 `format`）——配置面先行（根目录 `router_*.json`，如 `router_q25_14b.json`、`deepseek.router.json`），代码面小改（`llm.py`）；产出读数变化须按"一因一批 + 尺戳 bump + 新旧分表"（指南 §1.2，尺戳用例钉 `plot_engine/tests/test_instr.py`）。
  2. 模型 bakeoff 收敛：从根目录多份 `router_*.json` 收敛到生产双车道各一；qwen3 MoE 禁上尺（指南 §1.5）。
  3. Writer 表面按尺号制度迭代（`llm_writer.py` `WRITER_SURFACE` bump 纪律不变）。
  4. **后期补充（tff 裁定登记 2026-10-15）**：temp0 贪心在刀锋章的重复/argmax 翻转失稳（§19–§20、§24 三连物证）的正解是**前置 schema**——grammar-constrained/guided decoding 从键名到型别全约束；本路线第 1 条即其入口，**不进当前测量靶批**，instr-v3 预注册在 backlog，基线定谳后另起一批。**预注册材料已落**：`docs/r4-guided-decoding-prereg.md`（Ollama 0.40.x 零码 extra_body 接入、grammar 不治面清单、maxItems 必写、后置校验不可撤）。
- **验收**：guided 模式 `MALFORMED_PROPOSAL` 率对比报告（走 `instr_measure.py` 仪器，落 `sampling/<批次>/`）；新旧尺号读数分表不并列。

### R8 商业输入路线（tff 裁定并入，2026-10-15）

- **依据**：`docs/commercial/r8-commercial-input-requirements-v1.0.md`（六项 A 类缺陷）+ 四项目深研（四家均为代码级深读对象：架构、机制、函数实现全部可查可研，详见 `docs/commercial/refrence/` 各项目详审文档）。
- **入队序（已裁定）**：确认闸（**已收口 v0.14**：设计 v1.0 冻结+码批两批落库，`docs/confirmation-gate-design.md`）> 爽点工程 > 量化去味 > 拆文库 > 扫榜 > 旧稿导入。
- **承接映射**：确认闸→R3+R5 审听出口（`review.py`/`viewer.py` 面）；爽点工程→WP-A（R1 语义层是地基，不另起炉灶）；量化去味→WP-C（暂停中，归属裁定后激活，写集仍是禁区面）；拆文库/扫榜→**WP-F**（oh-story 吸收通道：拆榜/爆款方法论、双层追踪记录〔作者真相 vs 读者已知〕、门禁脚本参考）；旧稿导入→R6/WP-D 相邻面（bible 通道已有）。
- **姿态**：垂直有声书交付，不与 AI-NWA/inkos 拼通用工具广度；护城河=确定性尺+盲测仪+事件溯源内核（inkos 同构 reducer 印证方向、无质量语义尺=差距所在）。

### L5 测量层 → R5 测量运营路线

- **现状**：体系最完整：决策桶/E2 率（`metrics.py`）、n-gram 复述（`prose_audit.py`）、AI 味 lint+基线（`ai_flavor_lint.py`、`ai_flavor_baseline.py`）、反事实（`counterfactual.py`）、重锚（`reanchor.py`）、instr 仪器（`instr*.py`）、尺号制度（v3.6）。
- **路线**：
  1. **50 章压测**（Phase 0 验收证据化）：可追溯/发现违规/状态恢复三条逐条出证据；落盘纪律（指南 §1.1）：`sampling/<批次>/` + 可复现命令进报告（新文档 `docs/phase0-50ch-stress.md`，创建前确认）。
  2. lint 规则持续扩充（1 正 1 反纪律）——**当前暂停，见 §4 WP-C**。
  3. 盲测运营常态化（`blind_review.py` ≥30 章/≥15 失败章下限）；**禁读答案键 `docs/samples/blind-v2paired-key.md`**（指南 §2）。
- **验收**：压测报告 + 盲评工作表 + 答案键分离。

### L6 出口层 → R6 交付接线路线

- **现状**：`reading.py` 唯一取数路径，`sample.py`/`readout.py`/`viewer.py`/`blind_review.py` 四出口；与 `backend/` 零接线（grep 证据）。
- **路线**：
  1. `state.db → backend/noveldb.py` 导入器（**字段映射已产出**：`docs/wp-d-noveldb-mapping.md` v0.2，开放问题①已关闭）。
  2. 幂等导入（对齐 `backend/noveldb.py` "所有写接口幂等"约束）。
  3. 导入后交 R7 管线。
- **验收**：fixture 三方对账（人物/facts/章节数）；重复导入零重复行（映射表 §5 七条用例）。

### 轨道二 backend → R7 有声书管线路线

- **现状**：`docs/migration-plan.md` 阶段 2 进行中（`backend/noveldb.py` 已建八表：projects/characters/chapters/scenes/segments/audio_versions/voice_samples/jobs）。
- **路线**（按 `docs/migration-plan.md` S2→S4 不变）：S2 收尾（ebook/story 移植、中文提示词三件套）→ S3 GPU worker+TTS Provider+声音工厂 → S4 导出 M4B+`frontend/`（Vue 2）+E2E；接 R6 后 plot_engine 自产小说走同一管线。
- **验收**：migration-plan 各阶段既有验收标准原样沿用。

---

## 3. 阶段路线（用户四阶段计划 ↔ 项目映射）

| 用户计划 | 项目映射 | 涉及路线 | 当前状态 | 下一步 |
|---|---|---|---|---|
| Phase 0 生产内核 | alexandria Phase 0 | L0–L3 + R5 压测 | 已建成，50 章证据**已补（判负）** | **WP-E 已收口**：`sampling/wpe50ch/` 读数 `docs/phase0-50ch-stress.md`——处置率 74%，E2/E3 False，当前冻结面下 50 章规模不成立 |
| Phase 1 剧情能力 | epoch_1 语义层（`docs/epoch1-foreshadow-design.md` v0.2） | R0→R1→R2→R3 | **契约已冻结（v0.12 六项裁定）** | **WP-A v3.8 码批已收口落库（v0.13）**——伏笔账本/H9/D11/四级阶梯/v3.8 尺全绿；**Live 三采样已判负（v0.15，`docs/phase0-live-run-10ch.md` §9）**——读数一致、规模不成立；**归因双批已判（v0.16，§10）**——模型面（32B）与结构面（半密度契约）均出局，议程收敛为「钉判模态错位 vs Revision 动作缺失」；下一步=冻结会（G1 已命中） |
| Phase 2 成品质量 | 测量/文风/生成约束 | R4 + R5 + R6 | 约半数超前开工 | WP-B 码批 / **WP-D 已交付**（`docs/wp-d-noveldb-mapping.md` v0.4 §8） |
| Phase 3 商业验证 | 盲测→读者→付费 | R6 + R7 + 盲测 + **R8** | 工具已备，数据未启动 | **已定案：不进通用工具市场，纵深走垂直有声书交付**；50 章产物 → 盲评 → 接 R7 |

**顺序律**：R0（契约冻结）是 R1/R2/R3 的硬前置；R4/R5/R6 与 R0–R3 可并行；R7 全程并行、在 R6 后汇合。

---

## 4. 撞车矩阵（并行窗口仲裁表，以本表为准）

> 仲裁依据：`docs/commercial/collaborator-guide.md` §1 纪律包 / §2 禁区清单。"时间互斥"指与 GPU 生成批或他人批次的互斥。

| 工作包 | 写集（路径） | 禁区碰撞 | 时间互斥 | 放行门控 | 并行窗口结论 |
|---|---|---|---|---|---|
| WP-0 集成中枢 | `plot_engine/live.py`、`review.py`、`experiment.py` + `alexandria-spec-v0.2/CHANGELOG.md` | 无 | 批次在跑时勿改（指南 §2） | tff | 全程，跑批窗口内冻结 |
| WP-A 伏笔语义码批 | `plot_engine/models/ledger.py`、`models/state.py`、`models/event.py`、`reducers/plot.py`、`validator.py`（仅 H9 族）、`llm_extract.py`（仅 PAYLOAD_SCHEMA+尺戳，**串行 #70 后**）、`derive.py`（仅联动校验，**串行 b3 后**）、`revision.py`（仅 RULE_TO_LEVEL 登记）、`plot_engine/tests/`、`alexandria-spec-v0.2/`（01/03/04/05/09 + CHANGELOG） | 无 | **串行于 #70 三跑收口之后（已满足）；尺戳钉 v3.8，键名 `due_by_chapter` 已定稿（v0.12 裁定 4A）** | 契约冻结会已散会（拍板记录 `docs/freeze-meeting-and-r8-briefs.md` 末节） | **已收口（v0.13，八批 A–H 全落库，链验 554）** |
| WP-B guided decoding | `plot_engine/llm.py`、`plot_engine/tests/test_llm_client.py`、根目录 `router_*.json` | 无 | 跑批需独占 @213 车道 | 码批无门控；**跑批需 tff 放行** | 码批现在可并行；跑批排队 |
| WP-C 文风 lint | `plot_engine/ai_flavor_lint.py` + `plot_engine/tests/` | **`plot_engine/ai_flavor_*.py` 是他人在做面（指南 §2）** | — | tff 协调归属 | **暂停** |
| WP-D noveldb 导入 | `backend/plot_import.py` + `backend/tests/`（`plot_engine/` 零改动）；依据 `docs/wp-d-noveldb-mapping.md` v0.4 §8 | 无（禁区清单不含 `backend/`） | 无（纯离线，指南 §3 点名） | 无 | **已交付落库（9a00003，主线代）**：验收 6/6 + 链 531 零回归，主线独立复跑核过；六条实施偏差已回填 §8 |
| WP-F oh-story 吸收 | `docs/`（方法论+需求拆解），如落地 lint 另批申报 | 量化去味条目与 WP-C 同面（禁区 `ai_flavor_*.py`） | 零 GPU | R8 入队序第 4–5 位 | 排队（R8） |
| WP-E 50 章压测 | `sampling/<批次>/` + 新报告 `docs/phase0-50ch-stress.md` | 禁读 `docs/samples/blind-v2paired-key.md` | 独占 @213；跑批期间 `plot_engine/` 全冻结 | 锁 qwen2.5:14b；谱系=**暖**（与 v4 基线同谱系）；夹具=ladder-v5 | **已收口（2026-10-15）**：`sampling/wpe50ch/` 50/50，读数 `docs/phase0-50ch-stress.md`；冻结解除 |

**在跑/在队批次登记（时间互斥的真实来源，2026-10-15 稽核实测）**：

| 批次 | 内容 | 触碰面 | 状态 |
|---|---|---|---|
| #69 (a) 归因判据批 | IS_TOLD actor 判据入尺，尺戳 v3.6 | `plot_engine/llm_extract.py` + `plot_engine/tests/test_instr.py` | **已收口**（f326660；读数 §23：Jmed 1.0×3、闸 1/3、H5.1 税 0/0/0） |
| #70 (b) 型别批 | READS/BELIEVES/SUSPECTS 型别判据，尺戳 **v3.7** | `plot_engine/llm_extract.py:52` + `plot_engine/tests/test_instr.py`（`_patch_b12_typecriteria.diff`） | **判负已撤销**（三跑 v4g1..3 闸 1/3，§24；revert=90ea95b，尺退 v3.6） |
| b3 合法性修正批 | dead/unborn 不进 mental 事件候选 actor 集 | `plot_engine/derive.py:154-169` + `plot_engine/tests/test_derive_contract.py`（`_patch_b3_deadfilter.diff`） | **已撤销**（随 90ea95b；dead/unborn 过滤回到原实现） |
| #79 五十章阶梯夹具 | 10 步循环夹具在 ch11+ 重复 add=压测伪影；新阶梯+review 夹具接线 | `plot_engine/tests/fixtures/`、`review.py` | **已收口（de88d9e）**：ladder-v5（20 对×2 章不回环），离线 50/50 全绿，链 526→531 |
| #78 闸 | 生成批跨机可移植性 | 全生成面 | **已判过**（v4fL E2 20% 带内，§23；生成批默认车道仍 @213） |

**验证基线（改码前后都要绿）**：`.venv/Scripts/python.exe -m pytest plot_engine/tests -q` = **561 passed**（2026-10-16 归因批复测；历次 525→526→528→撤→526→531→WP-A +23→554→确认闸 +3→557→半密度夹具 +4→561；注：沙盒内跑会因 WinError 5 临时目录权限产生 87 errors 假象，须非沙盒或先配置可用 TEMP）。

---

## 5. 风险登记（路线级）

| 风险 | 影响路线 | 缓解 |
|---|---|---|
| epoch_1 设计质量不足 → 全线返工 | R0–R3 | 设计稿（`docs/epoch1-foreshadow-design.md` v0.2）先审后冻，一次定稿 |
| 50 章压测暴露长尾（CAS 冲突/快照膨胀） | R5/L1 | 压测报告先行，问题分级再修 |
| Ollama guided 能力弱于 vLLM | R4 | 双路径设计，配置切换（`router_*.json`） |
| 导入通道遇上 epoch_1 schema 变更 | R6 | WP-D 与 WP-0 对齐 epoch 时点；映射表 §6 已标注 epoch 敏感字段 |
| 读者验证样本不足 | Phase 3 | 盲测下限纪律已内置（`plot_engine/blind_review.py`） |
| 他人脏面活跃（`frontend/`、`docs/usage-wiki.md`、`docs/ebooks-standard.md`、`deploy/patches/` 等在改） | WP-C/集成 | 禁区清单勿碰；commit 前 `git status` 对照指南 §2 |
| 沙盒环境跑测试产生假红（WinError 5） | 全部码批验收 | 验收跑批一律非沙盒或预配 TEMP，报告注明环境 |
| 尺戳双占（v3.7 已被 #70 占用后撤销） | WP-A/R4 | 戳号已烧不复用；WP-A 钉死 v3.8；今后尺戳分配进 §4 批次登记 |
| `docs/commercial/collaborator-guide.md` 基线数字滞后 | 全部 | 已七次刷新（…→WP-A 后 554→确认闸后 557→归因批后 561）；仲裁以 **561** 为准 |
| 章内在场一致性盲区（WP-E ch50 实证三连穿帮机检全漏，`docs/phase0-50ch-stress.md` §6） | Level-3 / WP-F / epoch_2 | **backlog**：(a) level3_fn 判分线待 tff 定标；(b) 在场静态事实=T1 新事件型，赶 epoch_2/WP-F 双层追踪，WP-A 范围已冻结不动刀 |

---

## 6. 关键文件索引（备查）

### 治理与路线文档

| 路径 | 用途 |
|---|---|
| `docs/project-roadmap.md`（本文 v0.6） | 层 × 路线 + 撞车矩阵 + 在跑批次登记 |
| `docs/commercial/collaborator-guide.md` v1.0 | 纪律包 + 禁区清单（冲突时纪律以它为准） |
| `docs/epoch1-foreshadow-design.md` v0.2 | WP-A epoch_1 契约设计稿（**已冻结并已按 v0.12 裁定实施落库**，v0.13） |
| `docs/wp-d-noveldb-mapping.md` v0.4 | WP-D 字段映射表 + §8 实施回填（已交付） |
| `docs/migration-plan.md` | 轨道二 S0–S4 迁移总计划 |
| `alexandria-spec-v0.2/`（`00`–`10` + `CHANGELOG.md` + `README.md`） | 协议冻结基线 |

### 商业化分析文档（docs/commercial/，2026-10-15 引入）

| 路径 | 用途 |
|---|---|
| `docs/commercial/r8-commercial-input-requirements-v1.0.md` | R8 商业化输入路线需求规格（tff 五项裁决已确认；6 项缺陷优先级与验收） |
| `docs/commercial/oh-story-architecture-and-commercial-analysis-v1.0.md` | Oh Story 架构与商业化分析 |
| `docs/commercial/ai-novel-writing-assistant-comparison-v1.0.md`（v1.1） | AI-NWA 对标评估（研究稿对账 + 三点修正 + 开放决策支持） |
| `docs/commercial/refrence/README.md` | 参考项目索引 + 四方对照矩阵 + 机制参考总表 |
| `docs/commercial/refrence/comparison.md` | 四方 vs 我方对比总文档（互证/差距/反方证据/开放决策支持） |
| `docs/commercial/refrence/ai-novel-writing-assistant.md`、`inkos.md`、`oh-story.md`、`sillytavern.md` | 分项目架构/商业/业务流/代码流（本地代码核实） |

对应代码基线：`refrence_projects/`（AI-Novel-Writing-Assistant / inkos / oh-story-claudecode / SillyTavern 四个克隆，仅作分析素材）。

### 在队补丁（未施加，撞车源）

| 路径 | 用途 |
|---|---|
| `_patch_b12_typecriteria.diff` | #70 型别批（尺戳 v3.7；判负已撤销 90ea95b，留档待 (b') 重划靶） |
| `_patch_b3_deadfilter.diff` | b3 合法性批（改 `derive.py:154-169` + `test_derive_contract.py`） |
| `_patch_a_attribution.diff` | a 归因相关补丁（状态待确认） |

### 生成侧核心代码（plot_engine/）

| 路径 | 用途 |
|---|---|
| `plot_engine/models/`（11 个模型文件） | 契约层：event/fact/ledger/contract/sceneplan/state/proposal/commit/revision/experiment/entity |
| `plot_engine/reducer.py` + `plot_engine/reducers/`（5 族） | 状态内核分派 + 纯函数 reducer |
| `plot_engine/store.py`、`eventlog.py`、`replay.py`、`commit.py`、`reduce.py` | 持久化/CAS/事件溯源/提交管线 |
| `plot_engine/validator.py`、`derive.py`、`sceneplan.py` | 判定层 |
| `plot_engine/revision.py`、`revision_actions.py`、`rescue.py` | 修订层 |
| `plot_engine/llm.py`、`llm_writer.py`、`llm_extract.py`、`writer.py`、`live.py` | 生成层 |
| `plot_engine/reading.py`、`sample.py`、`readout.py`、`viewer.py`、`blind_review.py` | 出口层 |
| `plot_engine/metrics.py`、`prose_audit.py`、`ai_flavor_lint.py`、`instr*.py`、`reanchor.py`、`counterfactual.py` | 测量层 |
| `plot_engine/tests/`（80+ 测试文件） | 验证基线 561 passed |

### 交付侧核心代码（backend/）

| 路径 | 用途 |
|---|---|
| `backend/noveldb.py` | 产品级 SQLite 数据层（八表，R6 导入目标） |
| `backend/projects.py`、`domain.py`、`rules.py`、`context_manager.py`、`sync_state.py` | 业务骨架（S2 进行中） |
| `backend/asr_qc.py`、`master_audio.py`、`emotion_map.py` | 音频 QC/合成/情感（S3/S4） |

### 配置与产物

| 路径 | 用途 |
|---|---|
| 根目录 `router_*.json`（如 `router_q25_14b.json`、`router_local.json`、`deepseek.router.json`） | 模型路由配置（角色→端点/温度） |
| `sampling/<批次>/` | 采样跑法产物落盘目录（落盘纪律 §13） |
| `plot_engine/tests/fixtures/`（`experiment_10ch.py`、`traitor_arc.json`） | 离线 fixture |

### 禁区（指南 §2，触碰即回滚）

| 路径 | 原因 |
|---|---|
| `docs/samples/blind-v2paired-key.md` | 盲评答案键，禁读 |
| `docs/usage-wiki.md`、`docs/ebooks-standard.md`、`frontend/src/api/*`、`frontend/src/views/*`、`frontend/src/data/store.js`、`deploy/patches/*`、`.qoder/settings.local.json`、`plot_engine/ai_flavor_*.py`、sqlite `-shm/-wal`、`_aiflavor_*` | 他人在做的工作面，勿 stage/commit |
| `1.txt` | 临时任务单，禁载纪律/结论 |

---

> 本文档 v0.4 待审。审查意见以批注形式给出后，按意见更新版本号与内容；实施层面的代码改动一律走开发助手 + 稽核流程。
