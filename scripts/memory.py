"""进化记忆（evolution-memory.md）读写。

进化记忆是跨会话、跨 Agent 的经验载体：它只是普通 Markdown 文件，因此任何能读写
文件的 Agent 都能共享同一份记忆。每个被管理的技能目录下各有一份。
"""

import datetime
import os
import re

MEMORY_FILENAME = "evolution-memory.md"

TEMPLATE = """# Evolution Memory: {name}

## 进化日志

（暂无记录）

## 已知缺陷（未修复）

（暂无）

## 优化模式库

（暂无）
"""

# 退化信号积分表（与 signals.py 保持一致，供报告生成时展示）
SIGNAL_WEIGHTS = {
    "user_correction": 3,
    "ambiguity": 3,
    "clarification": 2,
    "retry": 2,
    "missing_context": 2,
    "negative_sentiment": 2,
    "redundant_call": 1,
    "topic_drift": 1,
    "positive_feedback": -1,
}


def _today():
    return datetime.date.today().isoformat()


def memory_path(skill_path):
    return os.path.join(skill_path, MEMORY_FILENAME)


def ensure(skill_path, name=None):
    """确保技能目录下存在进化记忆文件。"""
    path = memory_path(skill_path)
    if not os.path.exists(path):
        os.makedirs(skill_path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(TEMPLATE.format(name=name or os.path.basename(os.path.abspath(skill_path))))
    return path


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def _write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def _section_bounds(lines, heading):
    """返回 (start, end) 行号区间，end 为下一个同级标题或文件末尾。"""
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## "):
            if start is not None:
                return start, i
            if line.strip()[3:].strip().startswith(heading) or heading in line:
                start = i
    return (start, len(lines)) if start is not None else (None, None)


def append_entry(skill_path, mode, summary, trigger="", scores=None, root_cause="",
                 change="", verification="", result="", lesson=""):
    """追加一条进化日志。scores 形如 {"有效性":3,"稳定性":4}。"""
    path = ensure(skill_path)
    lines = _read_lines(path)
    start, end = _section_bounds(lines, "进化日志")
    if start is None:
        lines += ["", "## 进化日志", ""]
        start, end = len(lines) - 2, len(lines)

    scores = scores or {}
    score_text = "、".join("%s=%s" % (k, v) for k, v in scores.items()) or "未评估"

    entry = [
        "",
        "### [%s] %s - %s" % (_today(), mode.upper(), summary),
        "- **触发**：%s" % (trigger or "手动触发"),
        "- **五维评分**：%s" % score_text,
        "- **根因**：%s" % (root_cause or "—"),
        "- **修改**：%s" % (change or "—"),
        "- **验证**：%s" % (verification or "—"),
        "- **结果**：%s" % (result or "—"),
        "- **教训**：%s" % (lesson or "—"),
    ]
    # 日志插到「进化日志」标题之后，保证最新一条在最上面
    insert_at = start + 1
    while insert_at < len(lines) and not lines[insert_at].strip().startswith("### "):
        if lines[insert_at].strip().startswith("## "):
            break
        insert_at += 1
    lines[insert_at:insert_at] = entry + [""]
    _write_lines(path, lines)
    return "\n".join(entry)


def read_entries(skill_path):
    path = memory_path(skill_path)
    if not os.path.exists(path):
        return []
    entries = []
    for line in _read_lines(path):
        m = re.match(r"^###\s*\[([^\]]+)\]\s*([A-Za-z]+)\s*-\s*(.*)$", line.strip())
        if m:
            entries.append({"date": m.group(1), "mode": m.group(2).upper(), "summary": m.group(3)})
    return entries


def read_defects(skill_path):
    path = memory_path(skill_path)
    if not os.path.exists(path):
        return []
    lines = _read_lines(path)
    start, end = _section_bounds(lines, "已知缺陷")
    if start is None:
        return []
    defects = []
    for line in lines[start + 1:end]:
        m = re.match(r"^-\s*\[([^\]]+)\]\s*(.*?)(?:（([^）]*)）)?\s*$", line.strip())
        if m:
            defects.append({
                "dim": m.group(1),
                "desc": m.group(2).strip(),
                "date": m.group(3) or "",
            })
    return defects


def _write_defects(skill_path, defects):
    """用给定缺陷列表重写「已知缺陷」段落。"""
    path = memory_path(skill_path)
    lines = _read_lines(path)
    start, end = _section_bounds(lines, "已知缺陷")
    if start is None:
        lines += ["", "## 已知缺陷（未修复）", ""]
        start, end = len(lines) - 2, len(lines)
    body = ["- [%s] %s（%s）" % (d["dim"], d["desc"], d.get("date") or _today()) for d in defects]
    if not body:
        body = ["（暂无）"]
    lines[start + 1:end] = body
    _write_lines(path, lines)


def add_defect(skill_path, dim, desc):
    defects = read_defects(skill_path)
    defects.append({"dim": dim, "desc": desc, "date": _today()})
    _write_defects(skill_path, defects)
    return defects[-1]


def remove_defect(skill_path, index):
    """按序号（从 1 开始）移除一条已知缺陷，通常在它已转成回归测试后调用。"""
    defects = read_defects(skill_path)
    if index < 1 or index > len(defects):
        raise IndexError("缺陷序号越界：%s（共 %d 条）" % (index, len(defects)))
    removed = defects.pop(index - 1)
    _write_defects(skill_path, defects)
    return removed


def summary(skill_path):
    entries = read_entries(skill_path)
    defects = read_defects(skill_path)
    return {
        "memory_exists": os.path.exists(memory_path(skill_path)),
        "entry_count": len(entries),
        "last_entry": entries[-1] if entries else None,
        "open_defects": len(defects),
        "defects": defects,
    }
