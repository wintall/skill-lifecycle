"""SKILL.md 结构与规范扫描（免费、无需 LLM 调用）。

检查项覆盖：frontmatter 完整性、描述质量、篇幅、引用资源是否存在、是否缺少
渐进式披露结构等。输出结构化问题列表，供 FIX 诊断和 CI 门禁使用。
"""

import os
import re

MAX_BODY_LINES = 500
MIN_DESCRIPTION_LENGTH = 40

RECOMMENDED_SECTIONS = ["何时使用", "使用", "流程", "模式", "示例", "参考"]


def read_frontmatter(skill_md_path):
    """解析 YAML frontmatter（只取顶层 key: value，支持 > 折叠的续行）。"""
    if not os.path.exists(skill_md_path):
        return {}
    with open(skill_md_path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}
    data = {}
    key = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m and not line[:1].isspace():
            key = m.group(1)
            data[key] = m.group(2).strip()
        elif key:
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


def read_body(skill_md_path):
    with open(skill_md_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1:]
    return lines


def referenced_files(skill_md_path):
    """提取 Markdown 中引用的相对文件路径。"""
    body = read_body(skill_md_path)
    base = os.path.dirname(skill_md_path)
    refs = []
    for line in body:
        for m in re.finditer(r"\]\(([^)]+)\)", line):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            refs.append(os.path.normpath(os.path.join(base, target.split("#")[0])))
    return refs


def scan_skill(skill_path):
    """扫描一个技能目录，返回问题列表 [{level, code, message}]。"""
    issues = []
    skill_md = os.path.join(skill_path, "SKILL.md")

    if not os.path.exists(skill_md):
        return [{"level": "error", "code": "no-skill-md", "message": "缺少 SKILL.md"}]

    front = read_frontmatter(skill_md)
    body = read_body(skill_md)

    if "name" not in front:
        issues.append({"level": "error", "code": "no-name", "message": "frontmatter 缺少 name"})
    if "description" not in front:
        issues.append({"level": "error", "code": "no-description", "message": "frontmatter 缺少 description"})
    else:
        desc = front["description"]
        if len(desc) < MIN_DESCRIPTION_LENGTH:
            issues.append({
                "level": "warn",
                "code": "short-description",
                "message": "description 仅 %d 字，建议 ≥%d 字并覆盖触发场景（当前模型容易「该触发不触发」）"
                           % (len(desc), MIN_DESCRIPTION_LENGTH),
            })
        if "。" in desc and "触发" not in desc and "使用" not in desc and "when" not in desc.lower():
            issues.append({
                "level": "info",
                "code": "description-no-trigger",
                "message": "description 未显式描述触发场景，建议补充「当……时使用」",
            })

    body_lines = len([l for l in body])
    if body_lines > MAX_BODY_LINES:
        issues.append({
            "level": "warn",
            "code": "body-too-long",
            "message": "SKILL.md 正文 %d 行，超过建议的 %d 行，应拆分到 references/"
                       % (body_lines, MAX_BODY_LINES),
        })

    headings = [l.strip("# ").strip() for l in body if l.startswith("#")]
    if len(headings) < 3:
        issues.append({"level": "info", "code": "few-sections", "message": "章节较少，建议补充清晰的流程分段"})
    if not any(k in " ".join(headings) for k in RECOMMENDED_SECTIONS):
        issues.append({"level": "info", "code": "no-usage-section",
                       "message": "未发现「何时使用 / 流程 / 示例」类章节，建议补充"})

    for ref in referenced_files(skill_md):
        if not os.path.exists(ref):
            issues.append({"level": "error", "code": "missing-reference",
                           "message": "引用的资源不存在：%s" % os.path.relpath(ref, skill_path)})

    if not os.path.exists(os.path.join(skill_path, "evolution-memory.md")):
        issues.append({"level": "info", "code": "no-memory",
                       "message": "尚未建立进化记忆（evolution-memory.md）"})

    return issues


def health_score(issues):
    """把问题列表折算成 0-100 的结构健康分。"""
    penalty = {"error": 20, "warn": 8, "info": 2}
    score = 100 - sum(penalty.get(i["level"], 0) for i in issues)
    return max(0, min(100, score))


def format_issues(issues, title="扫描结果"):
    lines = [title, ""]
    if not issues:
        lines.append("未发现问题，结构合规。")
        return "\n".join(lines)
    for i in issues:
        lines.append("[%s] %s: %s" % (i["level"].upper(), i["code"], i["message"]))
    lines += ["", "结构健康分：%d/100" % health_score(issues)]
    return "\n".join(lines)
