# 安装指南

`skill-lifecycle` 的形态是「一个技能目录 + 一组 Python 脚本」，因此安装方式取决于你的 Agent
支持什么。三种场景，任选其一。

## 前置条件

- Python 3.8 或更高版本（脚本只用标准库，无需 `pip install`）
- 一个可写的目录用来放技能资产

```bash
python --version
```

---

## 场景零：QwenPaw（阿里 AgentScope 开源的个人智能体工作台）

QwenPaw 原生支持 Skills、MCP 和 Cron，是本项目的理想运行环境之一。

### 1. 放到技能池

技能池默认在 `%USERPROFILE%\.qwenpaw\skill_pool\`（每个技能一个目录，含 `SKILL.md`）。

```powershell
git clone https://github.com/wintall/skill-lifecycle.git
Copy-Item -Recurse -Force .\skill-lifecycle\* `
  -Destination "$env:USERPROFILE\.qwenpaw\skill_pool\skill-lifecycle"
```

> 也可以直接用 QwenPaw 自带的 `make-skill` / `materialize_skill` 走正规流程，
> 它会跑 Skill Scanner 并自动登记到 `skill_pool/skill.json` 清单。

### 2. 重启并验证

重启 QwenPaw（Console / TUI / 桌面端），然后对它说：

> 用 skill-lifecycle 看看我技能池里哪些技能需要维护

脚本用 QwenPaw 自带的 Python（3.11+）即可运行，无需额外装包：

```powershell
& "C:\Program Files\Python312\python.exe" `
  "$env:USERPROFILE\.qwenpaw\skill_pool\skill-lifecycle\scripts\skill_cli.py" self-check
```

### 3. 用 Cron 做定时巡检（QwenPaw 独有优势）

因为 Agent 协议（含 MCP）都是拉取式的，服务端无法主动打断 Agent。
QwenPaw 的 Cron 正好补上这个缺口——定时体检，结果经频道推送给你：

> 每周一早上 9 点，用 skill-lifecycle 给技能池里所有技能跑一次 health，
> 把健康分低于 80 的、以及有未修复缺陷的列出来发给我

### 4. 注意事项

- **触发重叠**：技能池里通常已有 `skill-creator`、`make-skill`，它们与本技能都能响应
  「做个技能」。分工见 `SKILL.md` 的「与同类技能的分工」一节；若仍抢触发，
  可把本技能的 `description` 收窄，只保留「评估 / 修复 / 进化 / 健康度」相关表述。
- **Skill Scanner**：QwenPaw 会在技能激活前扫描提示词注入、硬编码密钥等风险。
  本项目只读写技能目录内的 Markdown / JSON，若被标 warn，可在 `skill_scanner_blocked.json`
  或控制台里加入白名单。
- **技能资产路径**：建议直接让本技能管理 `skill_pool` 下的技能，工作区（`.skill-lifecycle/`）
  会建在技能池同级目录，QwenPaw 的其他 Agent 也能读到同一份进化记忆。

---

## 场景一：支持 Skills 规范的 Agent（推荐）

适用：Claude Code、CodeBuddy、Cowork、Microsoft Agent Framework 等。

### 1. 放置目录

```bash
# Claude Code
git clone https://github.com/wintall/skill-lifecycle.git ~/.claude/skills/skill-lifecycle

# CodeBuddy（示例路径，以你的实际配置为准）
git clone https://github.com/wintall/skill-lifecycle.git ~/.codebuddy/skills/skill-lifecycle
```

### 2. 验证

对你的 Agent 说一句：

> 用 skill-lifecycle 帮我看看我有哪些技能需要维护

如果它调用了 `skill_cli.py` 或引用了进化记忆，说明安装成功。

### 3. 可选：让它顺便管理已有技能

```bash
python scripts/skill_cli.py init ~/.claude/skills/<你已有的某个技能>
```

---

## 场景二：Claude.ai 网页 / App（无文件系统）

### 1. 打包

```bash
cd skill-lifecycle
python scripts/skill_cli.py package . --out ./dist
```

得到 `dist/skill-lifecycle.skill`。

### 2. 上传

在 Claude.ai 的技能设置里上传该 `.skill` 文件。

### 3. 已知限制

- 脚本无法执行 → benchmark 统计、打包等功能不可用
- 无文件系统 → **进化记忆无法持久化**，需要你手动保存文本内容并在下次对话提供
  （这是本项目最有价值的复利能力，此场景下会失效，请知悉）

---

## 场景三：其他编程 Agent（Cursor / Cline / Windsurf 等）

这类 Agent 通常没有 skills 机制，但有「规则文件」和终端。

### 1. 注入指令

把 `SKILL.md` 的内容放进它的规则机制：

| Agent | 做法 |
|---|---|
| Cursor | 写入 `.cursorrules` 或 Project Rules |
| Cline | 写入 `.clinerules` |
| 其他 | 在对话开头说「先读 `skill-lifecycle/SKILL.md` 并按它执行」 |

### 2. 脚本照常可用

```bash
python /path/to/skill-lifecycle/scripts/skill_cli.py health <技能路径>
```

脚本只依赖标准库，任何能开终端的 Agent 都能调用。

---

## 让多个 Agent 共享同一个技能库（可选）

把技能资产放在一个固定目录，让所有 Agent 都指向它：

```
D:\my-skills\                       ← 共享技能库
├── skill-lifecycle\                ← 管家本身
├── docx-skill\
│   └── evolution-memory.md         ← 进化记忆（谁都能读写）
└── .skill-lifecycle\               ← 工作区（evals / benchmark / signals）
```

在 Agent A 里修好的经验，Agent B 打开同一目录照样能读到——因为记忆就是文件。

配置方式：给每个 Agent 的规则文件里写明这个路径，或在调用时显式传 `--workspace`。

---

## 卸载

直接删除目录即可，所有状态都在目录里，不会在别处留下残留：

```bash
rm -rf ~/.claude/skills/skill-lifecycle
# 以及各工作区目录 .skill-lifecycle/
```

## 常见问题

**Q：脚本输出中文乱码？**
Windows 控制台默认 GBK，脚本已尝试自动切换 UTF-8。若仍异常，执行前设置：
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

**Q：找不到 Python？**
Windows 用户若装了 Python 但命令不可用，试试 `py scripts/skill_cli.py ...`。

**Q：工作区默认建在哪里？**
默认在被管理技能的**同级目录**下：`<技能父目录>/.skill-lifecycle/<技能名>/`。
可用 `--workspace` 显式指定到任意位置。
