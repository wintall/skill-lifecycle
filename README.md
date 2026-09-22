# skill-lifecycle

**让 AI 技能像软件资产一样被创建、测试、进化。**

你的 Agent 用着用着，技能是不是会「变笨」？写好的 skill 不知道好不好用，坏了只能手动改，
踩过的坑下次照样踩，经验随着会话结束一起消失。

`skill-lifecycle` 就是为解决这些而生的：**技能的创建、评估与自主进化管家**。
它是 [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
（严谨评估）+ [skill-evolution](https://github.com/swhmonster/skill-evolution)
（自主进化）两套思路的融合实现，并做成了任何人都能装、任何 Agent 都能用的开源项目。

---

## 它解决什么问题

| 没有它 | 有了它 |
|---|---|
| 技能写完靠感觉，不知道好不好用 | 上线前有基线对比的量化 benchmark（通过率 / 耗时 / token） |
| 技能不好用只能手动修，容易越改越坏 | 信号监测自动发现退化，修复方案带回归验证 |
| 经验散落在聊天记录里，会话结束即消失 | 进化记忆是纯文件，跨会话、跨 Agent 永久累积 |
| 同一个坑反复摔 | 每次翻车自动转成回归测试用例 |
| 技能资产只属于某一个 Agent | 文件即数据库，多个 Agent 共享同一个技能库 |

## 核心能力

- **CREATE** — 从零起草技能，写真实测试用例，跑基线对比，量化验证后才算完成
- **EVALUATE** — with_skill vs without_skill / old_skill 双组对比，自动统计通过率、标准差、耗时、token
- **FIX** — 诊断 → 生成 diff 方案 → 三类场景回归验证 → 用户确认后落地，最多迭代 3 轮
- **DERIVED** — 从现有技能衍生窄触发的增强版本，与父技能共存不冲突
- **CAPTURED** — 从对话中捕获可复用流程，四维评估后提炼成新技能
- **进化记忆** — 每个技能一本「病历」：进化日志、已知缺陷、优化模式库
- **缺陷 → 回归测试** — 线上翻的车自动变成永久测试用例
- **自举** — 它自己也是被管理的技能，可以用自己的机制改进自己

## 30 秒上手

```bash
git clone https://github.com/wintall/skill-lifecycle.git
cd skill-lifecycle

# 1. 检查自身是否完整（自举）
python scripts/skill_cli.py self-check

# 2. 捕获一个新技能草稿
python scripts/skill_cli.py capture my-helper --dir ./my-skills --summary "把会议记录整理成周报"

# 3. 初始化它的生命周期资产
python scripts/skill_cli.py init ./my-skills/my-helper

# 4. 加一条测试用例
python scripts/skill_cli.py eval-add \
  --workspace ./my-skills/.skill-lifecycle/my-helper \
  --prompt "把这段会议记录整理成周报" \
  --expected "包含本周进展、风险、下周计划三部分"

# 5. 看看它的健康状态
python scripts/skill_cli.py health ./my-skills/my-helper
```

> 全部脚本只依赖 Python 标准库，无需 pip install，Windows / macOS / Linux 通用。

## 安装到你的 Agent

三种方式，任选其一，详见 [INSTALL.md](INSTALL.md)：

| 环境 | 做法 |
|---|---|
| Claude Code / CodeBuddy 等支持 Skills 的 Agent | 把本目录拷到技能目录（如 `~/.claude/skills/skill-lifecycle/`）即可自动触发 |
| Claude.ai 网页 / App | `python scripts/skill_cli.py package .` 生成 `.skill` 后上传 |
| 其他编程 Agent（Cursor / Cline 等） | 把 `SKILL.md` 内容放进它的规则文件，脚本照常调用 |

## 工作原理

```
        ┌──────── ① 创建 CREATE ────────┐
        │                               │
   起草技能 → 写测试用例 → 跑基线对比 → 看 benchmark → 用户反馈
        │                               │
        └──────────→  技能上线使用  ←────┘
                          │
                  ② 信号监测（纠正/澄清/重试…）
                          │
               ┌──────────┼──────────┐
             FIX        DERIVED    CAPTURED
          （原地修复）  （衍生增强） （捕获新技能）
               └──────────┼──────────┘
                          │
              ③ 回归验证：原始失败场景 + 正常场景 + 边界场景
                          │
              ④ 进化记忆落盘 + 缺陷转回归测试 → 回到①继续迭代
```

**关键设计**：所有状态都是纯文本文件（Markdown + JSON），因此经验不依赖于某个特定 Agent
或某次会话，而是沉淀在磁盘上持续复利。

## 目录结构

```
skill-lifecycle/
├── SKILL.md                  # 主技能入口（Agent 读它就知道怎么用）
├── scripts/                  # 全部可执行逻辑（纯标准库）
│   ├── skill_cli.py          # 统一命令行入口
│   ├── memory.py             # 进化记忆读写
│   ├── evals.py              # 测试用例管理与「缺陷→回归测试」
│   ├── benchmark.py          # 基线对比与统计
│   ├── signals.py            # 信号积分与模式判定
│   ├── scan.py               # SKILL.md 结构合规扫描
│   └── package_skill.py      # 打包 .skill
├── agents/                   # 子代理指令（诊断 / 评分 / 分析）
├── references/               # 数据结构、模式细节、撰写规范
├── templates/                # 进化报告、技能骨架
└── examples/                 # 端到端演示
```

## 与其他项目的关系

| 项目 | 定位 | 本项目如何借鉴 |
|---|---|---|
| [anthropics/skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) | 官方：创建技能 + 严格评估 | 借鉴其评估闭环、基线对比、benchmark 聚合思路 |
| [swhmonster/skill-evolution](https://github.com/swhmonster/skill-evolution) | 社区：技能自主进化守护 | 借鉴其三种进化模式、信号积分、进化记忆机制 |
| [AgentEvalHQ/AgentEval](https://github.com/AgentEvalHQ/AgentEval) | .NET Agent 评估框架 | 参考其门户化思路（本项目当前聚焦文件层，不做 Web 平台） |

本项目的差异化在于：**把「创建」和「进化」合成一条闭环，并且让经验以纯文件形式跨 Agent 累积。**

## 诚实说明（必读）

- 项目处于 **v0.1** 阶段，API 与行为可能调整。
- **「后台自动守护」不可依赖**：技能指令只在被触发时进入模型上下文，因此信号监测依赖
  Agent 在推理过程中主动调用 `signals-add`。设计上以「主动发起」为主，信号负责提示。
  真正的实时推送受限于当前 Agent 协议（包括 MCP 在内的拉取式协议），做不到服务端打断 Agent。
- 评估的严谨度取决于你写的断言质量；主观类技能（文风、审美）建议以人工反馈为主。

## 许可证

MIT License © 2026 wintall
