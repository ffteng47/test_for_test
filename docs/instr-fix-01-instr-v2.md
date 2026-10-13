# instr-fix-01 批次落档：仪器戳 `instr-v2`，与尺戳分开记账

任务单 `info.txt` 的执行记录。**边界声明（任务单原话）：不动判据语义、不动 H 系列、
不动协议字段、不动夹具钉。** 唯一触碰提示词文本的是 W4b（一行删除），默认**缓办**——
`instr.W4B_TOUCHED = False`，提示词那句留着也只是冗余，代码兜底在后（W4a）。

仪器戳与尺戳（`EXTRACTION_RULER = v3.3-belief-type-criteria`）**分开记账**：
run.log 首行新增 `仪器=instr-v2-local` / `｜车道=local|cloud`。
换车道 = 仪器版本变更（护栏 3），此前抽取读数按老规矩不与新戳同表。

## 三类废卷的分层（P0 的正当性）

| 层 | 问题 | 工程能不能治 | 本批次买到什么 |
|---|---|---|---|
| A 仪器完整性 | 截断、坏 JSON、人名代 id | 能，且可确定性验证 | W1–W4 全在这里 |
| B 仪器有效性 | 格式全对但该抽的没抽 | 有天花板（14B 语义召回上限） | W5 把它与格式噪声**分开定量** |
| C 引擎质量 | 尺可信后正文本身不过关 | 完全无关 | 不碰（H5.7 过度声明已交过学费） |

**谁要是承诺"P0 做完即达商用"，那就是 H5.7 式的过度声明。**

## 工作项落地位置

| 项 | 机制 | 代码 | 验收 |
|---|---|---|---|
| W1 | 场景标记 / ~1800 字窗口 + 200 字重叠带切分，逐段抽取（每段提示词都带角色注册表），按 `(event_type, actor, fact_id)` 确定性合并去重，段内段号重映射回全局 | `instr.split_draft_segments` / `instr.dedup_proposals` / `llm_extract.make_segmented_llm_channel` | 冻结 v4c 全语料重跑 `finish=length` = 0；能完整跑完的章合并后条目数 ≥ 单跑基线 95% |
| W2 | 解析失败 → 坏输出+错误回喂重试 1 次 → 仍失败**只废该段**（记 `segment_failed` + 缺失 `char_span`，章级 `malformed_reply` 恒 0） | `llm_extract.extract_with_repair` | `_junk.json` 三份历史坏输出离线回放（零采样）修复率 100% 或段级优雅降级 |
| W3 | actor/target 先精确匹配编号 → 命中注册表姓名/昵称映射到编号 → 未知/多义定向追问一次 → 仍解不出才拒收并记因 | `instr.build_alias_index` / `instr.resolve_actor_id` / `llm_extract._resolve_actor_field` | v4c2 第 3 章（12 条人名废卷）重跑废卷 = 0；多义率单独入账 |
| W4a | 数值定点键缺省由代码补 `DEFAULT_FIXED_POINT = 700`，可审计、可全局改 | `instr.apply_code_defaults` | 补键记 `defaulted_fixed_point` 账；错误类型（字符串/bool/float）仍丢弃，不洗坏料 |
| W4b | 删提示词里的"默认 700"句 | **未动**，`instr.W4B_TOUCHED = False` | 需拍板才动；不拍则 W4a 独立生效 |
| W5 | 温度 0 连跑两遍，逐章条目集合 Jaccard + BELIEVES/SUSPECTS 检出稳定性 | `instr_measure.double_run_report` / `instr_cli.report` | 预登记硬门槛见下 |
| W6 | 模型路由层：两条车道共用同一套分段/修复/别名/默认值，只有 client 不同 | `llm_extract.make_laned_channel` / `live.build_laned_source` | 2×2 对表 + 车道决策规则 |

`readout` 新增两个常设列：**废卷率**（章级，无账记 `-`，没测 ≠ 0）、**一致率**
（`<跑法>_fluctuation.json` 的 Jaccard 中位，同样没测记 `-`）。

## W5 预登记硬门槛与升级路径（"工程够不够"的答案机制）

```
废卷率 < 2%（30 章即 0 章）  ∧  Jaccard 中位 ≥ 0.85  ∧  探针集 BELIEVES 两跑一致
  └─ 全达标 → pass:open_v4d_baseline（才准开 v4d 基线）
  └─ 废卷达标但一致率/召回不达标 → ceiling_B:route_stronger_model_or_self_consistency_x3
       （天花板在 B 层，触发对冲：抽取路由到更强模型 或 自一致性 ×3 确定性合并）
  └─ 两者都救不回 → BELIEVES 类原语列为"本产品代不支持"，转商用规格裁剪，不再烧探针
  └─ 废卷率本身不达标 → instrument_fail:fix_A_first（A 层没修好，B/C 层花的钱都在买噪声）
```

## W6 预登记车道决策规则

云端车道在探针集召回显著更高（`+0.05`）且双跑一致率 ≥ 本地 ⇒ 抽取默认切云端，
本地留作降级档；两者差不多 ⇒ 留本地（省 COGS、少一个外部依赖），云端只在本地
废卷/漏检时按章兜底。

**判据文本之争（v3.3 对 v3.4b）在 W5 云端数字落地前一律不再投入**——强抽取模型
很可能让那两行措辞的差异直接失去意义。

## 三条护栏（治理，不是代码）

1. **仪器戳要记下云的完整身份。** `instr.lane_identity_report` 产出
   `provider + model + version + base_url + temperature + max_tokens + extra_body`，
   写入 run.log 与台账。云端模型会被供应商静默换版 ⇒ **钉测探针集定期回放当金丝雀**，
   读数漂移即报警。这就是"度量仪器必须先被度量"，对象从本地模型换成外部服务。
2. **书稿出域是商业决策，需要拍板，不是工程默认。** 私有化部署客户不能把稿子送出去
   ⇒ 本地车道不是备胎，是一个产品档（云端标准档 / 本地部署档），差距由 W5 的 2×2
   量化并写进产品规格书。
3. **换车道 = 仪器版本变更。** 默认车道一旦切换，戳升档
   （`instr-v2-local` → `instr-v2-cloud`），v4d 基线在哪条车道上跑，跑之前一次说清。

## 怎么跑（零生成）

```bash
# 1) W1（可选）：分段拆分看一眼
python -c "from plot_engine.instr import split_draft_segments as s; \
print([ (g.index, g.para_start) for g in s(open('稿.txt',encoding='utf-8').read()) ])"

# 2) 用真实模型把冻结 v4c 全语料抽取两遍，proposal 骨架落 JSON（chapters/malformed/tokens/recall）
#    —— 这一步零生成，只做抽取回放；token 量为 v4d 预算零头。

# 3) W5 单车道双跑报告
python -m plot_engine.instr_cli l1.json l2.json --probes 2,3,9 --chapters 30 \
    --out docs/instr-w5-fluctuation.json

# 4) W6 2×2 对表（本地1 本地2 云端1 云端2）
python -m plot_engine.instr_cli l1.json l2.json c1.json c2.json --probes 2,3,9 \
    --chapters 30 --out docs/instr-w6-2x2.json

# 5) W2 验收：_junk.json 历史坏输出离线回放
python -m plot_engine.instr_measure replay-junk <run>/dump/_junk.json \
    --out docs/instr-w2-junk-replay.json
```

JSON 契约见 `plot_engine/instr_cli.py` docstring（只重放 proposal 骨架：
`type/actor/target/payload`，进集合一致率口径的是"抽到了什么"）。

## 时序与代价

- W1–W4 编码数日（本批次已完成），W5/W6 回放半天；
- 成本：**零生成**；抽取回放约 30 章 × 2 跑 + 修复回放，token 为 v4d 预算零头；
- 全部完成后才准开 v4d 基线。

## P1 连锁反应（先不定稿）

等 W5 云端数字：强模型单跑召回就达标 ⇒ "关键词提名 + 定向确认"可能整个不需要，
P1 缩水成"证据片段进 schema"一件事；强模型也救不回 BELIEVES ⇒ 才轮到确定性提名上场，
且届时它服务的是明确量化过的缺口。
