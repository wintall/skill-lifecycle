# Changelog

## v0.1.1（2026-09-22）

### 新增

- 支持 QwenPaw（阿里 AgentScope）：`SKILL.md` 增加 `metadata.qwenpaw` 声明，
  `INSTALL.md` 新增「场景零：QwenPaw」章节，含技能池路径、验证方式与 Cron 定时巡检用法
- `SKILL.md` 新增「与同类技能的分工」，明确与 `skill-creator` / `make-skill` 的边界，
  避免在同一技能库里抢触发

## v0.1.0（2026-09-22）

首个可用版本，完成「创建 → 评估 → 进化」闭环。

### 新增

- `SKILL.md` 主技能入口，定义 CREATE / EVALUATE / FIX / DERIVED / CAPTURED 五种模式
- `scripts/skill_cli.py` 统一命令行：`init / scan / health / capture / eval-add /
  defect-add / defect-to-eval / run-record / grade-add / benchmark / signals-add /
  signals-show / report / package / self-check`
- 进化记忆（`evolution-memory.md`）读写：进化日志、已知缺陷、优化模式库
- 退化信号积分与模式判定（FIX 阈值 5 分，致命组合为「纠正 + 澄清」）
- 评估基准聚合：通过率、标准差、token、耗时，并与基线算 delta，附模式观察
- SKILL.md 结构合规扫描与结构健康分（纯代码，零 LLM 成本）
- 已知缺陷 → 回归测试用例转换
- 进化报告模板与技能骨架模板
- 子代理指令：诊断 / 评分 / 基准分析

### 设计取舍

- 全部状态为纯文本文件（Markdown + JSON），保证跨会话、跨 Agent 共享
- 仅依赖 Python 标准库，无第三方依赖
- 主动调用为主、信号触发为辅（当前 Agent 协议无法做到服务端主动推送）

### 已知限制

- 无 Web 门户（规划中）
- 无 MCP Server（规划中，接入后任何支持 MCP 的 Agent 可共享同一技能库）
- 评估的严谨度依赖断言质量，主观类技能建议以人工反馈为主
