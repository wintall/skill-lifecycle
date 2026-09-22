---
name: skill-lifecycle
description: >
  技能的创建、评估与自主进化管家，覆盖技能全生命周期：从零起草技能、用基线对比做量化评估、
  监测退化信号并修复（FIX）、从现有技能衍生增强版本（DERIVED）、从对话中捕获新技能（CAPTURED），
  并把每次翻车固化为回归测试、把每次经验沉淀为跨会话跨 Agent 的进化记忆。
  当用户提到以下任何意图时都应使用本技能：创建一个 skill / 写一个技能 / 保存为 skill /
  记住这个流程 / 沉淀这个流程；评估技能 / 测试技能好不好用 / 跑 benchmark / 对比技能效果；
  优化 skill / 改进 skill / skill 不好用 / skill 没生效 / skill 效果差 / skill 命中率低 /
  skill 退化 / skill 漂移 / evolve、optimize、fix、improve skill / skill not working /
  skill regression、skill drift；以及在执行任何技能过程中出现用户反复纠正、澄清、重试时。
  即使用户没有明确说「技能」二字，只要是在处理「可复用的工作流程」或抱怨某个技能不灵，
  也应触发本技能。
compatibility: 需要 Python 3.8+（仅用标准库）；需要文件系统读写权限以保存进化记忆与评估结果
---

# Skill Lifecycle — 技能全生命周期管家

把「技能」当作**软件资产**来管理：有创建、有测试、有版本、有病历（进化记忆）、有回归门禁。
它是 skill-creator（严谨评估）与 skill-evolution（自主进化）的融合实现，并且**可以管理它自己**。

## 核心原则

1. **文件即数据库**：进化记忆、测试用例、评估基准全部是纯文本（Markdown / JSON），
   任何能读写文件的 Agent 都能共享同一份资产。这意味着经验可以跨会话、跨 Agent 复用。
2. **主动调用可靠，自动触发辅助**：不要指望「后台实时守护」。信号监测依赖推理过程中主动记录，
   因此设计上以「用户/ Agent 主动发起」为主，信号只负责**提示该不该进化**。
3. **量化优先于直觉**：修改技能前后必须有基线对比数据，通过率、耗时、token 都用数字说话。
4. **每次翻车都留下资产**：退化信号 → 已知缺陷 → 回归测试用例，同一个坑不摔第二次。
5. **应用到技能文件前，必须征求用户同意**：所有 FIX/DERIVED 的修改都要先给方案、再确认、后落地。

## 四种模式

| 模式 | 含义 | 产出 | 何时使用 |
|---|---|---|---|
| **CREATE** | 从零起草并验证一个新技能 | 新技能目录（含测试用例与基准） | 用户要创建新技能 |
| **EVALUATE** | 对现有技能做量化评估 | `benchmark.json` / `benchmark.md` | 想知道技能好不好用、或改动前后对比 |
| **FIX** | 原地修复退化/失效的技能 | 同一技能的新版本（原地更新） | 信号积分 ≥5，或出现「纠正+澄清」致命组合 |
| **DERIVED** | 从现有技能衍生增强版本 | 新技能目录，与父技能共存 | 技能整体可用，但某子场景需要专门处理 |
| **CAPTURED** | 从对话中捕获全新的可复用技能 | 全新技能目录 | 出现 ≥2 个高价值捕获信号 |

---

## CREATE：创建新技能

1. **捕获意图**：先问清楚四件事——要做什么、何时触发、输出什么格式、要不要建测试用例。
   如果当前对话里已经有一段可复用的工作流，直接从对话中提取，不要让用户重复描述。
2. **起草 SKILL.md**：遵循 `references/writing-guide.md`，用 `templates/skill-skeleton.md` 起步。
   - `description` 必须同时写清「做什么」和「什么时候用」，措辞要主动一点（模型天然容易
     「该触发不触发」，描述写窄了就永远不会被用上）。
3. **初始化资产**：`python scripts/skill_cli.py init <技能路径>`，生成工作区与进化记忆。
4. **写测试用例**：真实用户会怎么说，就怎么写（2-3 条起步）。口语化、带具体细节，
   不要写「格式化这份数据」这种抽象请求。
5. **跑评估**：对每条用例跑 with_skill 与基线（without_skill），落盘 `grading.json` 和 `timing.json`。
6. **聚合看数据**：`benchmark` 命令生成对比表，把结果交给用户看，按反馈迭代。
7. **收尾**：`package` 打包，并在进化记忆里写一条 CAPTURED 日志。

## EVALUATE：量化评估

- **必须同时跑两组**：带技能 vs 基线。没有基线的分数没有意义。
- 基线选择：新建技能用 `without_skill`（完全不用）；改进已有技能用 `old_skill`（改动前的快照）。
- 断言要**可客观验证**（文件存在、字段正确、工具调用顺序），主观质量（文风、审美）交给用户看。
- 数据落盘后运行 `benchmark`，注意看 `notes` 里的观察：区分度不足的用例、方差过大的用例。

```bash
python scripts/skill_cli.py run-record --run-dir <...>/with_skill --tokens 84852 --duration-ms 23332
python scripts/skill_cli.py grade-add  --run-dir <...>/with_skill --text "输出包含利润 margin 列" --passed 1 --evidence "..."
python scripts/skill_cli.py benchmark  --iteration-dir <...>/iteration-1 --skill-name my-skill
```

## FIX：原地修复

触发后按 **Diagnose → Generate → Verify → Apply** 走，最多迭代 3 轮：

1. **诊断**（可交给 `agents/diagnoser.md` 子代理）：
   - `scan` 扫结构问题；`health` 看记忆、信号、历史基准
   - 五维评估：有效性 / 性能 / 稳定性 / 可测试性 / 体验，各 1-5 分
   - 根因归类：缺少知识 / 错误假设 / 指令歧义 / 边界缺失 / 流程冗余 / 交互不友好
   - **先读进化记忆**，避免重复已经失败过的方向
2. **生成方案**：`report` 命令生成进化报告，逐条写清「维度 + 优先级 + 位置 + 当前内容 → 修改为 + 理由 + 回归风险」。
3. **验证**：三类场景必须都过——原始失败场景（修好了吗）、已知正常场景（有没有回归）、边界场景。
   回归失败就回到第 2 步；部分通过就把通过的部分先给用户。
4. **应用**：**用户确认后**才改文件，用精确替换，不要整文件覆盖。
5. **收尾**：`defect-to-eval` 把缺陷转成回归测试；`health` 复检；进化记忆追加一条 FIX 日志
   （含教训，供下次参考）。

## DERIVED：衍生增强

适用于「技能整体能用，但某子场景总是处理不好」。与 FIX 的区别：**不替换父技能**。

- 新技能的 `description` 必须写明「是 {父技能} 的衍生版本，专用于 {子场景}」
- 触发关键词要比父技能**更窄更精确**，确保只在子场景时被选中，避免抢父技能的触发
- 明确验证一遍：衍生技能与父技能的触发条件不冲突

## CAPTURED：捕获新技能

当对话中出现「≥3 轮交互解决了一个完整问题，且没有现成技能覆盖」时：

1. 用四维评估判断值不值得存：新颖性 / 可复用性（预期 ≥每月1次）/ 复杂性（≥3步）/ 可泛化性（能否参数化）
2. 达到 3 维以上，主动提示用户：「这个过程没被现有技能覆盖，要不要存成 `{建议名称}` 技能？」
3. 用户同意后：`capture` 生成骨架 → 提炼知识（保留领域规则、决策标准、边界情况；丢弃笔误、跑题、死胡同）
   → 补测试用例 → 跑评估 → 确认后启用
4. 详细操作见 `references/modes.md`

---

## 信号监测（何时该进化）

退化信号积分（会话内累计）：用户纠正 +3、指令歧义 +3、用户澄清 +2、反复重试 +2、
缺失上下文 +2、负面情绪 +2、冗余调用 +1、话题偏离 +1、正面反馈 -1。

- **≥5 分** 或 **「用户纠正 + 用户澄清」同时出现** → 建议 FIX
- **≥2 个高价值捕获信号**（多步骤解决 / 新领域知识 / 可复用模式）→ 建议 CAPTURED
- 2~4 分 → 继续观察

记录方式（在推理过程中主动调用，不要指望自动）：

```bash
python scripts/skill_cli.py signals-add --workspace <workspace> --type user_correction --note "表格样式又被搞错了"
python scripts/skill_cli.py signals-show --workspace <workspace>
```

## 文件布局

```
<技能目录>/                      # 被管理的技能（可打包分发）
├── SKILL.md
└── evolution-memory.md          # 进化记忆：日志 + 已知缺陷 + 优化模式库

<workspace>/                     # 默认：<技能父目录>/.skill-lifecycle/<技能名>/
├── evals.json                   # 测试用例（含由缺陷转化的回归测试）
├── signals.json                 # 信号事件流
├── reports/                     # 进化报告
└── iteration-N/
    ├── eval-<name>/
    │   ├── with_skill/          # 带技能运行
    │   └── without_skill/       # 基线运行（或 old_skill）
    ├── benchmark.json
    └── feedback.json            # 用户反馈
```

## 命令行速查

```bash
python scripts/skill_cli.py init <skill-path>              # 初始化工作区
python scripts/skill_cli.py scan <skill-path>              # 结构合规扫描（免费）
python scripts/skill_cli.py health <skill-path>            # 健康报告
python scripts/skill_cli.py capture <name> --dir <parent>  # 捕获新技能
python scripts/skill_cli.py eval-add --workspace W --prompt "..." --expected "..."
python scripts/skill_cli.py defect-add <skill-path> --dim 稳定性 --desc "..."
python scripts/skill_cli.py defect-to-eval <skill-path> --index 1 --resolve
python scripts/skill_cli.py signals-add --workspace W --type retry
python scripts/skill_cli.py report <skill-path> --mode FIX
python scripts/skill_cli.py benchmark --iteration-dir <...>/iteration-1
python scripts/skill_cli.py package <skill-path>
python scripts/skill_cli.py self-check                     # 自举检查
```

## 自举

本技能自身也遵守上述全部约定：它有自己的 `evolution-memory.md`、可以被 `scan` 扫描、
修改它自己时同样要走「诊断 → 方案 → 回归验证 → 用户确认」的流程。
修改本技能后，请运行 `self-check` 并把变更记录进它自己的进化记忆。

## 参考文件

- `references/modes.md` — 五种模式的完整流程与判定细节
- `references/schemas.md` — evals.json / grading.json / benchmark.json 等数据结构
- `references/writing-guide.md` — 如何写好一个 SKILL.md（含渐进式披露与踩坑清单）
- `agents/diagnoser.md` — FIX 诊断子代理指令
- `agents/grader.md` — 断言评分子代理指令
- `agents/analyzer.md` — 基准结果分析子代理指令
- `examples/demo-workflow.md` — 端到端可复现演示
