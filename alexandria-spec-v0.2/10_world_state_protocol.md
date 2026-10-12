# 10 World State 协议

> 版本：v0.2
> 冻结日期：2026-10-08
> epoch：epoch_0（定义见 09 §2.5）
> 上位协议：00_principles.md
> 下位协议：01 / 02 / 03 / 04 / 05 / 07 全部引用本协议
> 变更历史：见 CHANGELOG.md（v0.2 起独立文件，不内嵌于协议正文）

## 1. 目的

定义 Alexandria 中所有"实体与结构性状态"的 Schema：
角色、地点、物品、势力、境界、关系、库存。

本协议是 05_validation_protocol.md 中 H1(Canon) 与 H4(Resource)
两类 HARD 规则的**唯一数据基础**。缺少本协议，H1/H4 整体悬空，
07_commit_protocol.md 的 Reducer 亦无聚合根可消费。

## 2. 核心原则

| # | 原则 |
|---|------|
| W1 | 所有 Entity 有稳定 ID，跨 epoch 不变 |
| W2 | Entity 状态由 Event 驱动变更，不直接修改 |
| W3 | Entity Schema 冻结后，字段增删走 epoch 升级 |
| W4 | 空间关系必须可推理（连通性、归属、上限） |
| W5 | 境界是偏序，tier 为全序编号，不可用字符串比较 |
| W6 | 库存与资源必须可计数、可校验、不为负 |
| W7 | 死亡/未出生角色不得作为新 Event 的 actor（missing 有限制，见 §4.2） |
| W8 | StoryState 必须可 canonical 序列化（05 §5.5），可 Replay |

## 3. Entity 总览

```text
Character     角色          char_XXXXXX（6 位，上限 999,999）
Location      地点          loc_XXXXXX（6 位）
Item          物品          item_XXXXXX（6 位）
Faction       势力          fac_XXXXX（5 位）
Realm         境界体系      realm_XXXXX（5 位，体系定义非实例）
Relationship  关系边        rel_XXXXXX（6 位）
Inventory     库存边        inv_XXXXXX（6 位）
Ability       技能          abil_XXXXX（5 位）
Region        区域          rgn_XXXXX（5 位）
```

## 4. Character Schema

```python
class Character(BaseModel):
    character_id: str = Field(..., pattern=r"^char_\d{6}$")
    name: str
    aliases: List[str] = []
    gender: Optional[str] = None

    # 生存状态（由 CHANGES(field=status) 事件驱动）
    status: Literal["alive", "dead", "missing", "sealed", "unborn"]
    death_chapter: Optional[int] = None
    seal_chapter: Optional[int] = None

    # 能力体系
    realm: Optional[str] = None              # realm_id
    abilities: List[str] = []                # abil_id 列表
    attributes: Dict[str, int] = {}          # 定点化：力量/敏捷/... ×1000（05 §5.5）

    # 空间
    current_location: Optional[str] = None   # loc_id

    # 阵营
    faction_id: Optional[str] = None

    # 元数据
    introduced_at_chapter: int
    last_seen_at_chapter: Optional[int] = None
    epoch: str
```

### 4.1 status 语义

| status | 含义 | 可否作为 actor |
|--------|------|----------------|
| alive | 正常 | 可以 |
| dead | 死亡 | 禁止（I7） |
| missing | 失踪（下落不明） | 有限制（见 §4.2 附注） |
| sealed | 封印（能力受限） | 可以（usable_realms 视为 []） |
| unborn | 未出生 | 禁止（I7） |

### 4.2 状态转换（合法路径）

```text
alive → dead / missing / sealed        （仅 CHANGES field=status）
missing → alive / dead                 （仅 CHANGES field=status）
sealed → alive                         （仅 CHANGES field=status）
unborn → alive                         （仅 CHANGES field=status）
dead → alive                           禁止，Phase 0（需 RESURRECTED 事件，v0.3 待定）
dead → *                               禁止
```

missing 作为 actor 的限制（v0.2 明确）：

```text
- 其 Event.location 必须为 None（抽象事件），不适用 W-S5 位置一致性校验
- 除非同批含 CHANGES(field=status) 使其恢复 alive，
  否则不得更新其 current_location / inventory
```

### 4.3 与 04 CharacterChange 的字段映射（强制规则）

| CharacterChange.field | 数据落点 | 由哪类 Event 实现 |
|-----------------------|----------|-------------------|
| knowledge | Knowledge Ledger（03 §4） | OBSERVES / READS / IS_TOLD / INFERS |
| belief | Belief Ledger（03 §5） | BELIEVES / SUSPECTS / DOUBTS |
| location | Character.current_location | CHANGES(field=location) |
| realm | Character.realm | CHANGES(field=realm) |
| status | Character.status | CHANGES(field=status) |
| relationship | Relationship 表 | RELATIONSHIP_CHANGED |
| inventory | Inventory 表 | ITEM_ACQUIRED / ITEM_CONSUMED |
| attributes | Character.attributes | CHANGES(field=attributes) |
| abilities | Character.abilities | CHANGES(field=abilities) |

Chapter Contract 的 must_change 写哪个 field，就必须由对应的 Event 类型实现，
Validator 据此判定（04 §5.2 W1/W2）。

## 5. Location Schema

```python
class Location(BaseModel):
    location_id: str = Field(..., pattern=r"^loc_\d{6}$")
    name: str

    # 区域归属
    region_id: Optional[str] = None
    parent_location_id: Optional[str] = None

    # 空间关系
    connected_to: List[str] = []              # 直接可达的 loc_id
    distance: Dict[str, int] = {}             # loc_id -> 距离 ×1000

    # 访问控制
    unlocked: bool = True
    unlock_conditions: List[str] = []         # 条件表达式列表（§5.2）

    # 规则
    realm_cap: Optional[str] = None           # 该地点允许的最高 realm_id
    faction_control: Optional[str] = None     # 当前控制势力 fac_id

    # 元数据
    introduced_at_chapter: int
    epoch: str
```

### 5.1 空间推理规则（v0.2 编号 W-S，避免与 05 SOFT 规则 S1~S5 撞名）

```text
W-S1. 连通性：connected_to 是对称关系（A→B 则 B→A）
W-S2. 距离：distance 满足三角不等式（Phase 0 只做 OBSERVATION）
W-S3. 父子：parent_location_id 构成树（无环）
W-S4. 可达判定：角色从 A 到 B 必须存在路径
W-S5. 位置一致：Event 中 actor.current_location 必须等于 Event.location
             或 Event.location 为空（抽象事件；missing 角色豁免，见 §4.2）
W-S6. 境界上限：角色进入 location 时，realm.tier <= location.realm_cap.tier
```

### 5.2 解锁模型（Phase 0 最小版）

```text
unlocked: bool                    — 全局开关
unlock_conditions: List[str]      — 条件 ID 列表

Phase 0 条件类型：
  - fact:<fact_id>       该 fact.narrative_truth = true
  - realm:<realm_id>     角色 realm.tier >= 该 realm.tier
  - item:<item_id>       角色 inventory 包含该 item

同一列表内所有条件 AND 组合；OR 通过多条 unlock_conditions 展开。

Phase 0 约定：unlocked 在实体初始化时设定，运行期不变；
"能否进入"由 unlock_conditions 对当前 StoryState 的实时求值决定
（事实随剧情推进变化，无需改 unlocked 本身）。
unlocked 自身变更的事件通道留待 v0.3 定义，Phase 0 禁止直接写入（I8）。
```

## 6. Item Schema

```python
class Item(BaseModel):
    item_id: str = Field(..., pattern=r"^item_\d{6}$")
    name: str

    item_type: Literal[
        "consumable", "equipment", "material", "key", "misc", "quest"
    ]

    attributes: Dict[str, Any] = {}

    # 唯一性
    unique: bool = False
    stackable: bool = True

    # 使用约束
    required_realm: Optional[str] = None      # 使用所需最低 realm_id
    consumed_on_use: bool = False

    introduced_at_chapter: int
    epoch: str
```

## 7. Faction Schema

```python
class Faction(BaseModel):
    faction_id: str = Field(..., pattern=r"^fac_\d{5}$")
    name: str

    parent_faction_id: Optional[str] = None

    relations: Dict[str, str] = {}            # fac_id -> "ally"|"neutral"|"hostile"

    controlled_locations: List[str] = []
    members: List[str] = []                   # char_id 列表

    introduced_at_chapter: int
    epoch: str
```

## 8. Realm Schema（境界体系）

关键：境界必须是偏序 + tier 全序编号，禁止字符串比较。

```python
class Realm(BaseModel):
    realm_id: str = Field(..., pattern=r"^realm_\d{5}$")
    name: str                                 # "筑基" / "元婴"
    tier: int = Field(..., ge=1)              # 全序编号，从 1 起
    system_id: str                            # 所属体系（如 "cultivation_main"）

    previous_realm: Optional[str] = None      # 前一境界 realm_id
    next_realm: Optional[str] = None          # 后一境界 realm_id

    # 能力约束
    allowed_abilities: List[str] = []         # 该境界允许的 abil_id
    usable_realms: List[int] = []             # 该境界可动用 tier 上限（Phase 0 通常 = [tier]；
                                              # sealed 角色视为 []）
    min_attributes: Dict[str, int] = {}       # 突破所需最低属性 ×1000

    epoch: str
```

### 8.1 比较规则

```text
R1. 同一 system_id 内，tier 全序
R2. 不同 system_id 之间不可比较（防止跨体系 bug）
R3. 比较必须走函数：can_defeat(a, b) := a.system_id == b.system_id and a.tier > b.tier
R4. 禁止直接比较 name 字符串
```

### 8.2 Phase 0 唯一体系

Phase 0 只支持一个 system_id（如 cultivation_main）。多体系共存推迟到 Phase 1。

## 9. Relationship Schema

```python
class Relationship(BaseModel):
    relationship_id: str = Field(..., pattern=r"^rel_\d{6}$")
    from_character: str                       # char_id
    to_character: str                         # char_id

    type: Literal[
        "family", "master_disciple", "friend", "enemy",
        "ally", "rival", "lover", "colleague", "unknown"
    ]

    strength: int = Field(500, ge=0, le=1000) # ×1000
    trust: int = Field(500, ge=0, le=1000)    # ×1000

    symmetric: bool = True

    established_at_chapter: int
    ended_at_chapter: Optional[int] = None

    epoch: str
```

### 9.1 对称关系处理

```text
R1. symmetric=True 的关系存储为一条，查询时双向匹配
R2. symmetric=False 的关系存储为两条（from→to 和 to→from）
R3. 同一对角色之间可以有多条关系（如"师徒" + "敌人"）
R4. 关系建立/变更/终结必须通过 RELATIONSHIP_CHANGED 事件（01 §3.4）
```

## 10. Inventory Schema

```python
class InventoryEntry(BaseModel):
    inventory_id: str = Field(..., pattern=r"^inv_\d{6}$")
    character_id: str
    item_id: str
    quantity: int = Field(..., ge=0)

    acquired_at_chapter: int
    consumed_at_chapter: Optional[int] = None

    epoch: str
```

### 10.1 库存变更规则

```text
R1. 获得物品：ITEM_ACQUIRED 事件
R2. 消耗物品：ITEM_CONSUMED 事件
R3. quantity 变更后必须 >= 0
R4. unique=True 的物品 quantity 恒为 1
R5. 同一 (character_id, item_id) 合并为一条（stackable）
R6. 非 stackable 物品：每条 InventoryEntry 是独立实例
```

## 11. Ability Schema（Phase 0 最小版）

```python
class Ability(BaseModel):
    ability_id: str = Field(..., pattern=r"^abil_\d{5}$")
    name: str

    ability_type: Literal["combat", "utility", "passive", "special"]

    required_realm: Optional[str] = None      # 使用所需最低 realm_id
    consumed_resource: Optional[str] = None   # 消耗的 item_id

    introduced_at_chapter: int
    epoch: str
```

Phase 0 简化：Ability 只做 ID 引用，不展开效果树。
效果由 Writer 层理解，Validator 只检查"角色是否持有该 ability"（H2.4）
与境界门槛（H1.4）。

## 12. Region Schema

```python
class Region(BaseModel):
    region_id: str = Field(..., pattern=r"^rgn_\d{5}$")
    name: str

    contained_locations: List[str] = []       # loc_id 列表
    unlock_conditions: List[str] = []         # 同 §5.2 条件语法
    realm_cap: Optional[str] = None

    epoch: str
```

## 13. StoryState 聚合根（v0.2）

```python
class StoryState(BaseModel):
    # 元数据
    story_id: str
    chapter_no: int
    version: int
    epoch: str
    schema_version: int = 2

    # 实体（本协议）
    characters: Dict[str, Character] = {}
    locations: Dict[str, Location] = {}
    items: Dict[str, Item] = {}
    factions: Dict[str, Faction] = {}
    realms: Dict[str, Realm] = {}
    abilities: Dict[str, Ability] = {}
    regions: Dict[str, Region] = {}

    # 边（本协议）
    relationships: List[Relationship] = []
    inventory: List[InventoryEntry] = []

    # 认知层（02 / 03）
    facts: Dict[str, Fact] = {}
    fact_relations: List[FactRelation] = []
    knowledge_ledger: List[KnowledgeEntry] = []
    belief_ledger: List[BeliefEntry] = []
    reader_ledger: List[ReaderKnowledgeEntry] = []

    # 剧情层（04）
    active_arc: Optional[ArcContract] = None
    active_chapter: Optional[ChapterContract] = None

    # 结构层
    story_threads: List[str] = []
    foreshadowing: List[str] = []

    # 校验（05 §5.5 canonical 序列化）
    state_hash: str
```

## 14. 与 01 Event Protocol 的接口（v0.2 Taxonomy 已同步）

本协议要求并已落入 01 §3 的新事件：

```text
WorldEvents 新增：
  ITEM_ACQUIRED          payload: {character_id, item_id, quantity}
  ITEM_CONSUMED          payload: {character_id, item_id, quantity}
  RELATIONSHIP_CHANGED   payload: {from, to, relationship_type, strength_delta, trust_delta}

CHANGES.field 枚举统一为：
  status / realm / location / faction / attributes / abilities
  （不再包含 inventory / relationship，改用上述专用事件）

其他 v0.2 新增事件（来源为其他协议修订）：
  FACT_CONTRADICTED（03 §5.4）、READER_*（01 §3.5）——详见 CHANGELOG.md
```

## 15. 不变量（Invariants）

```text
I1.  所有 ID 全局唯一，跨 epoch 不变
I2.  所有引用（character_id / location_id / item_id / ...）必须存在
I3.  Character.current_location 必须为已知 Location 或 None
I4.  InventoryEntry.quantity >= 0
I5.  Realm.tier 在同一 system_id 内全序且无重复
I6.  Relationship 的 from/to 必须为已知 Character
I7.  dead / unborn 角色不得作为新 Event 的 actor（missing 限制见 §4.2）
I8.  Location.unlocked 初始化后 Phase 0 运行期不变（变更通道见 §5.2，v0.3 定义）
I9.  StoryState 必须可 canonical 序列化、可 Replay（05 §5.5）
I10. Location.parent_location_id 构成树（无环）
I11. Location.connected_to 对称
I12. unique=True 的 Item，其库存总量 <= 1
I13. Character.status 转换必须走 §4.2 合法路径
```

## 16. Validator 使用点（供 05 引用）

本协议为以下 HARD 规则提供数据：

```text
H1.1 死亡角色出场            → Character.status + Event.chapter > death_chapter
H1.2 未持有物品使用          → InventoryEntry.quantity
H1.3 角色在 A 地，事件在 B 地 → Character.current_location vs Event.location（W-S5）
H1.4 低境界使用高境界能力    → Realm.usable_realms / tier + Ability.required_realm
H3.4 同一角色同时出现在两个地点 → 同章内 current_location 变更冲突
H4.1 消耗不存在的资源        → InventoryEntry + ITEM_CONSUMED
H4.2 资源数量为负            → InventoryEntry.quantity
H4.3 未解锁区域进入          → Location.unlocked + unlock_conditions（§5.2）
```

## 17. 待定项（Phase 1 及以后）

```text
- 时间体系（纪年 / 月份 / 季节）
- 货币与价格系统
- 天气与环境状态
- 多 realm system 共存
- 传送门 / 非连通图空间
- Ability 效果树
- 势力内部结构（门派职级）
- 角色状态扩展（受伤 / 中毒 / buff）
- dead → alive 复活事件（RESURRECTED，v0.3 候选）
```

## 18. 附录：完整示例（节选）

```json
{
  "characters": {
    "char_000001": {
      "character_id": "char_000001",
      "name": "张三",
      "aliases": ["三哥"],
      "status": "alive",
      "realm": "realm_00003",
      "abilities": ["abil_00001", "abil_00007"],
      "attributes": {"strength": 1200, "agility": 800},
      "current_location": "loc_000012",
      "faction_id": "fac_00001",
      "introduced_at_chapter": 1,
      "epoch": "epoch_0"
    }
  },
  "locations": {
    "loc_000012": {
      "location_id": "loc_000012",
      "name": "宗门大殿",
      "region_id": "rgn_00001",
      "connected_to": ["loc_000011", "loc_000013"],
      "unlocked": true,
      "realm_cap": "realm_00005",
      "faction_control": "fac_00001",
      "introduced_at_chapter": 3,
      "epoch": "epoch_0"
    }
  },
  "realms": {
    "realm_00003": {
      "realm_id": "realm_00003",
      "name": "筑基",
      "tier": 3,
      "system_id": "cultivation_main",
      "previous_realm": "realm_00002",
      "next_realm": "realm_00004",
      "usable_realms": [3],
      "epoch": "epoch_0"
    }
  }
}
```
