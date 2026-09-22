# 端到端演示

本演示完整走一遍「创建一个技能 → 发现退化 → 修复 → 固化回归测试」的闭环。
所有命令可直接复制执行，无需任何凭据。

假设 `skill-lifecycle` 位于 `./skill-lifecycle`。

---

## 第 1 步：捕获一个草稿技能

场景：你刚和 Agent 花了几轮对话，把一份会议记录整理成了周报。
这个过程值得固化。

```bash
python skill-lifecycle/scripts/skill_cli.py capture weekly-report \
  --dir ./my-skills \
  --summary "把会议记录整理成结构化周报" \
  --signals "multi_step_solution, reusable_pattern"
```

产出：

```
my-skills/weekly-report/
├── SKILL.md            # 骨架，待补充
└── evolution-memory.md # 已写入一条 CAPTURED 日志
my-skills/.skill-lifecycle/weekly-report/
├── evals.json
└── signals.json
```

## 第 2 步：补充 SKILL.md 并加测试用例

编辑 `my-skills/weekly-report/SKILL.md`，把流程写清楚。然后：

```bash
python skill-lifecycle/scripts/skill_cli.py eval-add \
  --workspace ./my-skills/.skill-lifecycle/weekly-report \
  --prompt "这是今天的产品评审会记录（见 notes.md），帮我整理成周报发给团队" \
  --expected "包含本周进展、风险项、下周计划三部分，风险项要标出负责人"

python skill-lifecycle/scripts/skill_cli.py eval-add \
  --workspace ./my-skills/.skill-lifecycle/weekly-report \
  --prompt "把这段只有三行的会议记录整理成周报，信息很少" \
  --expected "信息不足时应向用户确认，而不是编造内容"
```

第二条是**边界用例**——它测的是技能会不会瞎编。

## 第 3 步：跑评估（with_skill 与基线各一次）

```bash
# 带技能
mkdir -p ./my-skills/.skill-lifecycle/weekly-report/iteration-1/eval-1/with_skill/outputs
python skill-lifecycle/scripts/skill_cli.py run-record \
  --run-dir ./my-skills/.skill-lifecycle/weekly-report/iteration-1/eval-1/with_skill \
  --tokens 84210 --duration-ms 23100

python skill-lifecycle/scripts/skill_cli.py grade-add \
  --run-dir ./my-skills/.skill-lifecycle/weekly-report/iteration-1/eval-1/with_skill \
  --text "输出包含本周进展、风险项、下周计划三部分" --passed 1 \
  --evidence "报告三个章节标题齐备"

# 基线（不用技能）
mkdir -p ./my-skills/.skill-lifecycle/weekly-report/iteration-1/eval-1/without_skill/outputs
python skill-lifecycle/scripts/skill_cli.py run-record \
  --run-dir ./my-skills/.skill-lifecycle/weekly-report/iteration-1/eval-1/without_skill \
  --tokens 91500 --duration-ms 25400

python skill-lifecycle/scripts/skill_cli.py grade-add \
  --run-dir ./my-skills/.skill-lifecycle/weekly-report/iteration-1/eval-1/without_skill \
  --text "输出包含本周进展、风险项、下周计划三部分" --passed 0 \
  --evidence "只有一段流水账，没有分章节"
```

## 第 4 步：看基准

```bash
python skill-lifecycle/scripts/skill_cli.py benchmark \
  --iteration-dir ./my-skills/.skill-lifecycle/weekly-report/iteration-1 \
  --skill-name weekly-report
```

输出示例：

```
| 配置 | 运行数 | 通过率 | 标准差 | 平均 tokens | 平均耗时(ms) |
|---|---|---|---|---|---|
| with_skill | 1 | 100% | 0.000 | 84210 | 23100 |
| without_skill | 1 | 0% | 0.000 | 91500 | 25400 |

## 与基线对比
- 通过率变化：**+100%**（基线：without_skill）
- mean_tokens 变化：**-7290**

## 观察
- 未找到运行记录之外的异常；样本量 1，标准差仅供参考
```

注意最后一行：**样本只有 1 次时标准差没有意义**，这是工具诚实提示的一部分。

## 第 5 步：使用中发现退化，记录信号

用户第二次用这个技能时说：「不对，我说了风险项要标负责人，你又没标。」

```bash
python skill-lifecycle/scripts/skill_cli.py signals-add \
  --workspace ./my-skills/.skill-lifecycle/weekly-report \
  --type user_correction --note "风险项没标负责人"
```

用户又澄清了一遍：「我是说每个风险项后面要跟 @人名。」

```bash
python skill-lifecycle/scripts/skill_cli.py signals-add \
  --workspace ./my-skills/.skill-lifecycle/weekly-report \
  --type clarification --note "每个风险项后跟 @负责人"
```

第二条一记录，工具立刻判定：

```
累计积分：5 ｜ 建议模式：FIX ｜ 理由：致命组合：用户纠正 + 用户澄清 同时出现
```

## 第 6 步：生成进化报告并修复

```bash
python skill-lifecycle/scripts/skill_cli.py report ./my-skills/weekly-report --mode FIX
```

工具会自动把已知缺陷、结构问题、历史日志填进报告模板，生成
`reports/2026-09-22-fix-report.md`。按模板填写根因和修改方案，
走完「验证（失败场景 + 正常场景 + 边界场景）→ 用户确认 → 应用」。

## 第 7 步：把这次翻车固化成回归测试

```bash
python skill-lifecycle/scripts/skill_cli.py defect-add ./my-skills/weekly-report \
  --dim 有效性 --desc "风险项未标注负责人"

python skill-lifecycle/scripts/skill_cli.py defect-to-eval ./my-skills/weekly-report \
  --index 1 --resolve \
  --prompt "整理这份会议记录成周报" \
  --expected "每个风险项后必须跟 @负责人"
```

这条用例会永久留在 `evals.json` 里（`source: "defect:1"`），
以后每次评估都会检查它——**同一个坑不会再摔第二次**。

## 第 8 步：查看健康状态

```bash
python skill-lifecycle/scripts/skill_cli.py health ./my-skills/weekly-report
```

```
技能健康报告：weekly-report
------------------------------------------------------------
结构健康分    ：92/100
进化记忆      ：2 条日志，0 条已知缺陷
信号积分      ：0（建议模式：NONE —— 信号不足，无需进化）
测试用例      ：3 条
最近迭代      ：iteration-1
   - with_skill 通过率：100%
   - without_skill 通过率：0%
```

## 第 9 步：打包分发

```bash
python skill-lifecycle/scripts/skill_cli.py package ./my-skills/weekly-report --out ./dist
```

得到 `dist/weekly-report.skill`，可上传给任何支持技能的环境。

---

## 自举演示

最后，让管家管一下它自己：

```bash
python skill-lifecycle/scripts/skill_cli.py self-check
python skill-lifecycle/scripts/skill_cli.py scan ./skill-lifecycle
python skill-lifecycle/scripts/skill_cli.py health ./skill-lifecycle
```

它自己也在自己的管辖范围内——修改它时同样要走「诊断 → 方案 → 回归验证 → 用户确认」。
