# 数据结构

全部为纯文本（JSON / Markdown），任何 Agent 都能读写。字段命名与官方 skill-creator
保持兼容，便于互相导入导出。

## evals.json

测试用例集合，位于 `<workspace>/evals.json`。

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "name": "1-add-profit-margin-column",
      "prompt": "老板发来 Q4 销售表，要在 D 列后面加一列利润率百分比",
      "expected_output": "新增一列利润率，百分比格式，保留两位小数",
      "files": ["samples/q4.xlsx"],
      "assertions": [
        { "text": "输出文件包含名为「利润率」的列", "kind": "structural" },
        { "text": "利润率数值为百分比且保留两位小数", "kind": "value" }
      ],
      "source": "manual",
      "created_at": "2026-09-22 10:30"
    }
  ]
}
```

- `source`：`manual`（手写）或 `defect:<序号>`（由已知缺陷转化）——后者是回归测试
- `assertions` 可先留空，跑测试的同时再补
- 目录名约定：`eval-<id>-<slug>/`

## eval_metadata.json

每次运行的元信息，位于运行目录内。

```json
{
  "eval_id": 1,
  "eval_name": "1-add-profit-margin-column",
  "prompt": "老板发来 Q4 销售表……",
  "assertions": ["输出文件包含名为「利润率」的列"]
}
```

## grading.json

断言评分结果，位于运行目录内。**字段名必须是 `text` / `passed` / `evidence`**。

```json
{
  "expectations": [
    {
      "text": "输出文件包含名为「利润率」的列",
      "passed": true,
      "evidence": "第 5 列表头为「利润率」"
    },
    {
      "text": "利润率数值为百分比且保留两位小数",
      "passed": false,
      "evidence": "数值为 0.1234，未转百分比"
    }
  ]
}
```

## timing.json

运行耗时与 token，位于运行目录内。

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.332,
  "recorded_at": "2026-09-22 10:35"
}
```

> 注意：token 与耗时只出现在任务完成通知里，不会持久化，**必须收到通知时立刻落盘**。

## benchmark.json

由 `benchmark` 命令生成，位于 `<workspace>/iteration-N/`。

```json
{
  "skill_name": "my-skill",
  "iteration": "iteration-1",
  "generated_at": "2026-09-22 10:40",
  "configs": [
    {
      "config": "with_skill",
      "runs": 3,
      "pass_rate": 0.92,
      "pass_rate_stddev": 0.058,
      "mean_tokens": 84210,
      "mean_duration_ms": 23100
    },
    {
      "config": "without_skill",
      "runs": 3,
      "pass_rate": 0.61,
      "pass_rate_stddev": 0.11,
      "mean_tokens": 91500,
      "mean_duration_ms": 25400
    }
  ],
  "delta": {
    "baseline_config": "without_skill",
    "pass_rate": 0.31,
    "mean_tokens": -7290,
    "mean_duration_ms": -2300
  },
  "evals": [
    {
      "eval": "eval-1-add-profit-margin",
      "configs": {
        "with_skill": { "passed": 2, "total": 2, "pass_rate": 1.0, "tokens": 84000, "duration_ms": 23000 },
        "without_skill": { "passed": 1, "total": 2, "pass_rate": 0.5, "tokens": 91000, "duration_ms": 25000 }
      }
    }
  ],
  "notes": ["with_skill：通过率标准差 0.058，结果稳定"]
}
```

## signals.json

信号事件流，位于 `<workspace>/signals.json`。

```json
{
  "events": [
    { "type": "user_correction", "weight": 3, "kind": "degrade", "note": "表格样式又错了", "timestamp": "2026-09-22 10:20" },
    { "type": "clarification", "weight": 2, "kind": "degrade", "note": "我再说一遍……", "timestamp": "2026-09-22 10:22" }
  ],
  "updated": "2026-09-22 10:22"
}
```

## evolution-memory.md

每个技能目录下的记忆文件（Markdown）。

```markdown
# Evolution Memory: my-skill

## 进化日志

### [2026-09-22] FIX - 修正表格样式丢失问题
- **触发**：信号积分 5 分（用户纠正 + 用户澄清）
- **五维评分**：有效性=3、性能=4、稳定性=2、可测试性=3、体验=2
- **根因**：SKILL.md 未说明样式继承规则，模型每次自由发挥
- **修改**：新增「样式继承」章节，明确必须从源文档读取样式
- **验证**：3 个场景全通过
- **结果**：已应用
- **教训**：涉及格式的任务必须显式写死规则，不能靠模型推断

## 已知缺陷（未修复）

- [稳定性] 超大表格（>1万行）处理会超时（2026-09-22）

## 优化模式库

- **显式化隐性规则**：模型会自由发挥的地方，必须写死规则
  - 适用场景：格式、样式、命名约定类任务
  - 修改方式：新增独立章节，给出正反例
```

## feedback.json

用户反馈，位于 `<workspace>/iteration-N/feedback.json`。

```json
{
  "reviews": [
    { "run_id": "eval-1-with_skill", "feedback": "图表缺少坐标轴标签", "timestamp": "2026-09-22 11:00" },
    { "run_id": "eval-2-with_skill", "feedback": "", "timestamp": "2026-09-22 11:01" }
  ],
  "status": "complete"
}
```

空字符串表示用户认为没问题。改进应聚焦在有具体意见的用例上。
