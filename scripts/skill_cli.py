#!/usr/bin/env python3
"""skill-lifecycle 统一命令行入口。

仅依赖 Python 标准库，Windows / macOS / Linux 通用，可被 Agent 直接调用。

    python scripts/skill_cli.py <command> [options]

命令分组：
    资产搭建   init / capture / package
    健康诊断   scan / health / signals-add / signals-show / report
    评估闭环   eval-add / defect-add / defect-to-eval / run-record / grade-add / benchmark
    自举       self-check
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:  # 避免 Windows 控制台编码问题导致中文输出报错
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import benchmark as bench_mod
import evals as evals_mod
import memory as memory_mod
import package_skill as pkg_mod
import scan as scan_mod
import signals as signals_mod


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _skill_name(skill_path):
    front = scan_mod.read_frontmatter(os.path.join(skill_path, "SKILL.md"))
    return front.get("name") or os.path.basename(os.path.abspath(skill_path))


def _default_workspace(skill_path):
    skill_path = os.path.abspath(skill_path)
    parent = os.path.dirname(skill_path)
    return os.path.join(parent, ".skill-lifecycle", os.path.basename(skill_path))


def _resolve_workspace(args):
    return args.workspace or _default_workspace(args.skill_path)


def _evals_path(workspace):
    return os.path.join(workspace, evals_mod.EVALS_FILENAME)


# --------------------------------------------------------------------------
# 资产搭建
# --------------------------------------------------------------------------

def cmd_init(args):
    skill_path = os.path.abspath(args.skill_path)
    workspace = os.path.abspath(_resolve_workspace(args))
    os.makedirs(workspace, exist_ok=True)
    name = _skill_name(skill_path)

    evals_path = _evals_path(workspace)
    if not os.path.exists(evals_path):
        evals_mod.save(evals_path, {"skill_name": name, "evals": []})

    memory_path = memory_mod.ensure(skill_path, name)
    signals_mod.save(workspace, signals_mod.load(workspace))

    print("技能：%s" % skill_path)
    print("工作区：%s" % workspace)
    print("进化记忆：%s" % memory_path)
    print("测试用例：%s" % evals_path)
    print("信号文件：%s" % signals_mod.signals_path(workspace))
    return 0


def cmd_capture(args):
    """CAPTURED：从对话中捕获新技能，生成骨架。"""
    parent = os.path.abspath(args.dir)
    skill_path = os.path.join(parent, args.name)
    if os.path.exists(skill_path) and not args.force:
        print("目录已存在：%s（如需覆盖加 --force）" % skill_path)
        return 1
    os.makedirs(skill_path, exist_ok=True)

    skeleton = os.path.join(_REPO, "templates", "skill-skeleton.md")
    if os.path.exists(skeleton):
        with open(skeleton, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = "# %s\n\n## 何时使用\n\n## 流程\n" % args.name
    content = content.replace("{{NAME}}", args.name)
    content = content.replace("{{SUMMARY}}", args.summary or "（待补充：这个技能解决什么问题）")
    content = content.replace("{{DATE}}", datetime.date.today().isoformat())
    with open(os.path.join(skill_path, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)

    memory_mod.ensure(skill_path, args.name)
    memory_mod.append_entry(
        skill_path, "CAPTURED", "从对话中捕获创建",
        trigger="捕获信号：%s" % (args.signals or "手动触发"),
        change="生成初始 SKILL.md 骨架", verification="待跑测试用例", result="草稿",
        lesson="捕获后必须补测试用例并做基线对比，确认后再正式启用",
    )

    class _Args:
        pass
    sub = _Args()
    sub.skill_path = skill_path
    sub.workspace = args.workspace
    cmd_init(sub)

    print("已创建草稿技能：%s" % skill_path)
    print("下一步：补充 SKILL.md -> eval-add 添加测试用例 -> 跑评估 -> benchmark")
    return 0


def cmd_package(args):
    target = pkg_mod.package(args.skill_path, args.out)
    print("已打包：%s" % target)
    return 0


# --------------------------------------------------------------------------
# 健康诊断
# --------------------------------------------------------------------------

def cmd_scan(args):
    issues = scan_mod.scan_skill(args.skill_path)
    print(scan_mod.format_issues(issues, "扫描：%s" % args.skill_path))
    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    return 0 if not [i for i in issues if i["level"] == "error"] else 1


def cmd_health(args):
    skill_path = os.path.abspath(args.skill_path)
    workspace = os.path.abspath(_resolve_workspace(args))
    name = _skill_name(skill_path)
    issues = scan_mod.scan_skill(skill_path)
    mem = memory_mod.summary(skill_path)
    sig = signals_mod.summarize(workspace)
    evals_list = evals_mod.list_evals(_evals_path(workspace))
    latest = bench_mod.latest_iteration(workspace)
    bench = bench_mod._read_json(os.path.join(latest, "benchmark.json")) if latest else {}

    report = {
        "skill": name,
        "path": skill_path,
        "workspace": workspace,
        "structure_score": scan_mod.health_score(issues),
        "issues": issues,
        "memory": {"entry_count": mem["entry_count"], "last_entry": mem["last_entry"],
                   "open_defects": mem["open_defects"], "defects": mem["defects"]},
        "signals": {"total": sig["total"], "recommended_mode": sig["recommended_mode"],
                    "reason": sig["reason"]},
        "evals": len(evals_list),
        "latest_iteration": os.path.basename(latest) if latest else None,
        "benchmark": {c["config"]: c["pass_rate"] for c in bench.get("configs", [])},
        "generated_at": _now(),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("技能健康报告：%s" % name)
    print("-" * 60)
    print("结构健康分    ：%d/100" % report["structure_score"])
    print("进化记忆      ：%d 条日志，%d 条已知缺陷" % (mem["entry_count"], mem["open_defects"]))
    for d in mem["defects"]:
        print("   - [%s] %s" % (d["dim"], d["desc"]))
    print("信号积分      ：%d（建议模式：%s —— %s）" % (sig["total"], sig["recommended_mode"], sig["reason"]))
    print("测试用例      ：%d 条" % len(evals_list))
    if report["latest_iteration"]:
        print("最近迭代      ：%s" % report["latest_iteration"])
        for cfg, rate in report["benchmark"].items():
            print("   - %s 通过率：%s" % (cfg, "—" if rate is None else "%.0f%%" % (rate * 100)))
    else:
        print("最近迭代      ：无（尚未运行过评估）")
    if issues:
        print("待处理问题    ：")
        for i in issues:
            print("   [%s] %s" % (i["level"], i["message"]))
    return 0


def cmd_signals_add(args):
    workspace = os.path.abspath(args.workspace)
    event, summary = signals_mod.add(workspace, args.type, args.note or "")
    print("已记录信号：%s（权重 %+d）" % (event["type"], event["weight"]))
    print("累计积分：%d ｜ 建议模式：%s ｜ 理由：%s"
          % (summary["total"], summary["recommended_mode"], summary["reason"]))
    return 0


def cmd_signals_show(args):
    workspace = os.path.abspath(args.workspace)
    if args.list:
        print("退化信号权重表：")
        for k, (w, desc) in signals_mod.DEGRADE_WEIGHTS.items():
            print("  %-18s %+d  %s" % (k, w, desc))
        print("捕获信号：")
        for k, (level, desc) in signals_mod.CAPTURE_SIGNALS.items():
            print("  %-22s [%s] %s" % (k, level, desc))
        return 0
    summary = signals_mod.summarize(workspace)
    print(json.dumps({k: v for k, v in summary.items() if k != "events"}, ensure_ascii=False, indent=2))
    if args.reset:
        signals_mod.reset(workspace)
        print("信号已清零。")
    return 0


def cmd_report(args):
    """生成进化报告（FIX / DERIVED 的诊断文档），回填已知上下文。"""
    skill_path = os.path.abspath(args.skill_path)
    workspace = os.path.abspath(_resolve_workspace(args))
    name = _skill_name(skill_path)
    issues = scan_mod.scan_skill(skill_path)
    mem = memory_mod.summary(skill_path)
    sig = signals_mod.summarize(workspace)
    latest = bench_mod.latest_iteration(workspace)

    template_path = os.path.join(_REPO, "templates", "evolution-report.md")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    defects_text = "\n".join("- [%s] %s（%s）" % (d["dim"], d["desc"], d["date"] or "—")
                             for d in mem["defects"]) or "（暂无）"
    issues_text = "\n".join("- [%s] %s：%s" % (i["level"], i["code"], i["message"])
                            for i in issues) or "（结构扫描无问题）"
    history_text = "\n".join("- %s %s：%s" % (e["date"], e["mode"], e["summary"])
                             for e in memory_mod.read_entries(skill_path)[-5:]) or "（暂无历史）"

    content = (content
               .replace("{{SKILL_NAME}}", name)
               .replace("{{DATE}}", datetime.date.today().isoformat())
               .replace("{{MODE}}", (args.mode or sig["recommended_mode"]).upper())
               .replace("{{TRIGGER}}", sig["reason"])
               .replace("{{SIGNAL_TOTAL}}", str(sig["total"]))
               .replace("{{STRUCTURE_SCORE}}", str(scan_mod.health_score(issues)))
               .replace("{{KNOWN_DEFECTS}}", defects_text)
               .replace("{{STRUCTURE_ISSUES}}", issues_text)
               .replace("{{HISTORY}}", history_text)
               .replace("{{ITERATION}}", os.path.basename(latest) if latest else "无"))

    out = args.out or os.path.join(workspace, "reports")
    os.makedirs(os.path.dirname(os.path.abspath(out)) if out.endswith(".md") else out, exist_ok=True)
    if out.endswith(".md"):
        target = out
    else:
        target = os.path.join(out, "%s-%s-report.md" % (datetime.date.today().isoformat(),
                                                        (args.mode or sig["recommended_mode"]).lower()))
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    print("进化报告已生成：%s" % target)
    print("模式：%s ｜ 触发：%s" % ((args.mode or sig["recommended_mode"]).upper(), sig["reason"]))
    return 0


# --------------------------------------------------------------------------
# 评估闭环
# --------------------------------------------------------------------------

def cmd_eval_add(args):
    workspace = os.path.abspath(args.workspace)
    path = _evals_path(workspace)
    entry = evals_mod.add_eval(path, args.prompt, args.expected or "",
                               files=args.file, name=args.name, source=args.source)
    print("已添加测试用例 #%d：%s" % (entry["id"], entry["name"]))
    print("  文件：%s" % path)
    return 0


def cmd_defect_add(args):
    skill_path = os.path.abspath(args.skill_path)
    memory_mod.ensure(skill_path, _skill_name(skill_path))
    d = memory_mod.add_defect(skill_path, args.dim, args.desc)
    print("已记录已知缺陷：[%s] %s" % (d["dim"], d["desc"]))
    print("建议随后执行 defect-to-eval 把它固化成回归测试。")
    return 0


def cmd_defect_to_eval(args):
    skill_path = os.path.abspath(args.skill_path)
    workspace = os.path.abspath(_resolve_workspace(args))
    epath = _evals_path(workspace)
    defects = memory_mod.read_defects(skill_path)
    if not defects:
        print("没有已知缺陷可转换。")
        return 1
    if args.index < 1 or args.index > len(defects):
        print("序号越界，当前共 %d 条缺陷。" % len(defects))
        return 1
    defect = defects[args.index - 1]
    payload = evals_mod.from_defect(defect, args.prompt, args.expected)
    entry = evals_mod.add_eval(epath, payload["prompt"], payload["expected_output"],
                               name=args.name, source="defect:%d" % args.index)
    if args.resolve:
        memory_mod.remove_defect(skill_path, args.index)
        print("已将缺陷 [%s] %s 转为回归测试 #%d，并标记为已处理。"
              % (defect["dim"], defect["desc"], entry["id"]))
    else:
        print("已将缺陷 [%s] %s 转为回归测试 #%d（缺陷仍保留在记忆中）。"
              % (defect["dim"], defect["desc"], entry["id"]))
    return 0


def cmd_run_record(args):
    if args.run_dir:
        run_dir = os.path.abspath(args.run_dir)
    else:
        parts = [os.path.abspath(args.workspace), args.iteration, args.eval, args.config]
        if any(not p for p in parts):
            print("需提供 --run-dir，或同时提供 --workspace/--iteration/--eval/--config")
            return 1
        run_dir = os.path.join(*parts)
    os.makedirs(run_dir, exist_ok=True)
    timing = {
        "total_tokens": args.tokens,
        "duration_ms": args.duration_ms,
        "total_duration_seconds": round(args.duration_ms / 1000.0, 3) if args.duration_ms else None,
        "recorded_at": _now(),
    }
    with open(os.path.join(run_dir, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)
    print("已记录运行数据：%s" % run_dir)

    meta_path = os.path.join(run_dir, "eval_metadata.json")
    if not os.path.exists(meta_path):
        meta = {"eval_id": args.eval_id or 0,
                "eval_name": args.eval or os.path.basename(run_dir),
                "prompt": args.prompt or "",
                "assertions": []}
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print("已生成 eval_metadata.json（请补充断言）")
    return 0


def cmd_grade_add(args):
    run_dir = os.path.abspath(args.run_dir)
    os.makedirs(run_dir, exist_ok=True)
    gpath = os.path.join(run_dir, "grading.json")
    data = {}
    if os.path.exists(gpath):
        try:
            with open(gpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except ValueError:
            data = {}
    data.setdefault("expectations", []).append({
        "text": args.text,
        "passed": bool(args.passed),
        "evidence": args.evidence or "",
    })
    with open(gpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    passed = sum(1 for e in data["expectations"] if e.get("passed"))
    print("已记录断言：%s -> %s（%d/%d 通过）"
          % (args.text, "PASS" if args.passed else "FAIL", passed, len(data["expectations"])))
    return 0


def cmd_benchmark(args):
    iteration_dir = args.iteration_dir or bench_mod.latest_iteration(os.path.abspath(args.workspace))
    if not iteration_dir:
        print("未找到迭代目录，请指定 --iteration-dir")
        return 1
    bench = bench_mod.aggregate(os.path.abspath(iteration_dir), args.skill_name or "")
    print(bench_mod.to_markdown(bench))
    print("已写入：%s" % os.path.join(iteration_dir, "benchmark.json"))
    return 0


# --------------------------------------------------------------------------
# 自举
# --------------------------------------------------------------------------

def cmd_self_check(args):
    print("skill-lifecycle 自举检查")
    print("-" * 60)
    issues = scan_mod.scan_skill(_REPO)
    print(scan_mod.format_issues(issues, "自身结构扫描"))
    required = [
        "SKILL.md", "README.md", "INSTALL.md", "LICENSE",
        "scripts/skill_cli.py", "scripts/memory.py", "scripts/evals.py",
        "scripts/benchmark.py", "scripts/signals.py", "scripts/scan.py",
        "scripts/package_skill.py", "references/schemas.md", "references/modes.md",
        "references/writing-guide.md", "agents/diagnoser.md", "agents/grader.md",
        "agents/analyzer.md", "templates/evolution-report.md", "templates/skill-skeleton.md",
        "examples/demo-workflow.md",
    ]
    missing = [f for f in required if not os.path.exists(os.path.join(_REPO, f))]
    print("")
    if missing:
        print("缺失文件：%s" % ", ".join(missing))
    else:
        print("关键文件齐全（%d 项）" % len(required))
    return 0 if not missing else 1


# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="skill_cli", description="skill-lifecycle 命令行工具")
    sub = p.add_subparsers(dest="command")

    def add(name, func, help_text):
        s = sub.add_parser(name, help=help_text)
        s.set_defaults(func=func)
        return s

    s = add("init", cmd_init, "初始化技能的生命周期工作区")
    s.add_argument("skill_path")
    s.add_argument("--workspace")

    s = add("scan", cmd_scan, "扫描 SKILL.md 结构合规性")
    s.add_argument("skill_path")
    s.add_argument("--json", action="store_true")

    s = add("health", cmd_health, "输出技能健康报告（结构/记忆/信号/基准）")
    s.add_argument("skill_path")
    s.add_argument("--workspace")
    s.add_argument("--json", action="store_true")

    s = add("capture", cmd_capture, "CAPTURED：从对话捕获新技能草稿")
    s.add_argument("name")
    s.add_argument("--dir", default=".")
    s.add_argument("--summary")
    s.add_argument("--signals")
    s.add_argument("--workspace")
    s.add_argument("--force", action="store_true")

    s = add("package", cmd_package, "打包为 .skill")
    s.add_argument("skill_path")
    s.add_argument("--out")

    s = add("eval-add", cmd_eval_add, "添加测试用例")
    s.add_argument("--workspace", required=True)
    s.add_argument("--prompt", required=True)
    s.add_argument("--expected")
    s.add_argument("--name")
    s.add_argument("--file", action="append")
    s.add_argument("--source", default="manual")

    s = add("defect-add", cmd_defect_add, "记录已知缺陷到进化记忆")
    s.add_argument("skill_path")
    s.add_argument("--dim", default="有效性", help="维度，如 有效性/稳定性/体验")
    s.add_argument("--desc", required=True)

    s = add("defect-to-eval", cmd_defect_to_eval, "把已知缺陷转换为回归测试用例")
    s.add_argument("skill_path")
    s.add_argument("--index", type=int, required=True)
    s.add_argument("--workspace")
    s.add_argument("--prompt")
    s.add_argument("--expected")
    s.add_argument("--name")
    s.add_argument("--resolve", action="store_true", help="转换后从记忆中移除该缺陷")

    s = add("run-record", cmd_run_record, "记录一次运行的耗时与 token")
    s.add_argument("--run-dir")
    s.add_argument("--workspace")
    s.add_argument("--iteration")
    s.add_argument("--eval")
    s.add_argument("--config")
    s.add_argument("--eval-id", type=int)
    s.add_argument("--prompt")
    s.add_argument("--tokens", type=int, default=0)
    s.add_argument("--duration-ms", type=int, default=0)

    s = add("grade-add", cmd_grade_add, "记录一条断言的评分结果")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--text", required=True)
    s.add_argument("--passed", type=int, choices=[0, 1], required=True)
    s.add_argument("--evidence")

    s = add("benchmark", cmd_benchmark, "聚合生成 benchmark.json / benchmark.md")
    s.add_argument("--iteration-dir")
    s.add_argument("--workspace")
    s.add_argument("--skill-name")

    s = add("signals-add", cmd_signals_add, "记录一条退化/捕获信号")
    s.add_argument("--workspace", required=True)
    s.add_argument("--type", required=True)
    s.add_argument("--note")

    s = add("signals-show", cmd_signals_show, "查看信号汇总或信号类型表")
    s.add_argument("--workspace", required=True)
    s.add_argument("--list", action="store_true")
    s.add_argument("--reset", action="store_true")

    s = add("report", cmd_report, "生成进化报告（FIX/DERIVED 诊断文档）")
    s.add_argument("skill_path")
    s.add_argument("--workspace")
    s.add_argument("--mode", choices=["FIX", "DERIVED", "CAPTURED"])
    s.add_argument("--out")

    s = add("self-check", cmd_self_check, "自举检查（扫描自身结构与文件完整性）")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
