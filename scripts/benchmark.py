"""评估基准聚合：把各次运行的结果汇总成可比较的量化报告。

目录约定（与官方 skill-creator 一致，保证互操作）：

    <workspace>/iteration-N/
        eval-<name>/
            with_skill/      baseline/without_skill/old_skill/
                outputs/
                eval_metadata.json
                grading.json
                timing.json
        benchmark.json
        benchmark.md
"""

import datetime
import json
import os
import re

BASELINE_ORDER = ["without_skill", "old_skill", "baseline"]


def _read_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def _write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _mean(values):
    values = [v for v in values if v is not None]
    return (sum(values) / len(values)) if values else None


def _stddev(values):
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def _iteration_sort_key(name):
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def collect_runs(iteration_dir):
    """扫描一次迭代下所有运行目录，返回运行记录列表。"""
    runs = []
    if not os.path.isdir(iteration_dir):
        return runs
    for eval_dir_name in sorted(os.listdir(iteration_dir)):
        eval_dir = os.path.join(iteration_dir, eval_dir_name)
        if not os.path.isdir(eval_dir) or not eval_dir_name.startswith("eval-"):
            continue
        for config in sorted(os.listdir(eval_dir)):
            run_dir = os.path.join(eval_dir, config)
            if not os.path.isdir(run_dir):
                continue
            meta = _read_json(os.path.join(run_dir, "eval_metadata.json"))
            grading = _read_json(os.path.join(run_dir, "grading.json"))
            timing = _read_json(os.path.join(run_dir, "timing.json"))
            expectations = grading.get("expectations", [])
            passed = sum(1 for e in expectations if e.get("passed"))
            total = len(expectations)
            runs.append({
                "eval": eval_dir_name,
                "eval_name": meta.get("eval_name") or eval_dir_name,
                "config": config,
                "passed": passed,
                "total": total,
                "pass_rate": (passed / total) if total else None,
                "score": grading.get("score"),
                "tokens": timing.get("total_tokens"),
                "duration_ms": timing.get("duration_ms"),
            })
    return runs


def _config_stats(runs, config):
    subset = [r for r in runs if r["config"] == config]
    rates = [r["pass_rate"] for r in subset if r["pass_rate"] is not None]
    return {
        "config": config,
        "runs": len(subset),
        "pass_rate": _mean(rates),
        "pass_rate_stddev": _stddev(rates),
        "mean_tokens": _mean([r["tokens"] for r in subset]),
        "mean_duration_ms": _mean([r["duration_ms"] for r in subset]),
    }


def aggregate(iteration_dir, skill_name=""):
    """聚合成 benchmark.json 与 benchmark.md，返回 benchmark dict。"""
    runs = collect_runs(iteration_dir)
    configs = []
    seen = []
    for r in runs:
        if r["config"] not in seen:
            seen.append(r["config"])
    for config in seen:
        configs.append(_config_stats(runs, config))

    with_skill = next((c for c in configs if c["config"] == "with_skill"), None)
    baseline = None
    for name in BASELINE_ORDER:
        baseline = next((c for c in configs if c["config"] == name), None)
        if baseline:
            break
    if baseline is None:
        baseline = next((c for c in configs if c["config"] != "with_skill"), None)

    def _delta(a, b):
        if a is None or b is None:
            return None
        return a - b

    delta = {}
    if with_skill and baseline:
        delta = {
            "baseline_config": baseline["config"],
            "pass_rate": _delta(with_skill["pass_rate"], baseline["pass_rate"]),
            "mean_tokens": _delta(with_skill["mean_tokens"], baseline["mean_tokens"]),
            "mean_duration_ms": _delta(with_skill["mean_duration_ms"], baseline["mean_duration_ms"]),
        }

    evals_summary = []
    for name in sorted({r["eval"] for r in runs}):
        item = {"eval": name, "configs": {}}
        for r in runs:
            if r["eval"] == name:
                item["configs"][r["config"]] = {
                    "passed": r["passed"],
                    "total": r["total"],
                    "pass_rate": r["pass_rate"],
                    "tokens": r["tokens"],
                    "duration_ms": r["duration_ms"],
                }
        evals_summary.append(item)

    benchmark = {
        "skill_name": skill_name,
        "iteration": os.path.basename(os.path.normpath(iteration_dir)),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "configs": configs,
        "delta": delta,
        "evals": evals_summary,
        "notes": _notes(runs, configs),
    }
    _write_json(os.path.join(iteration_dir, "benchmark.json"), benchmark)
    with open(os.path.join(iteration_dir, "benchmark.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(benchmark))
    return benchmark


def _notes(runs, configs):
    """分析聚合数据背后的模式，避免只看均值被误导。"""
    notes = []
    by_assertion = {}
    for r in runs:
        for config, item in [(r["config"], r)]:
            by_assertion.setdefault(r["eval"], {}).setdefault(config, item["pass_rate"])
    for eval_name, cfg_map in by_assertion.items():
        values = [v for v in cfg_map.values() if v is not None]
        if len(values) >= 2 and len(set(round(v, 3) for v in values)) == 1:
            notes.append("%s：各配置通过率完全相同，该用例区分度不足，考虑替换" % eval_name)
    for c in configs:
        if c["pass_rate_stddev"] and c["pass_rate_stddev"] > 0.2:
            notes.append("%s：通过率标准差 %.2f 偏高，结果可能不稳定" % (c["config"], c["pass_rate_stddev"]))
    if not runs:
        notes.append("未找到任何运行记录，请先执行测试并落盘 grading.json / timing.json")
    return notes


def to_markdown(benchmark):
    lines = ["# Benchmark: %s (%s)" % (benchmark.get("skill_name") or "-", benchmark.get("iteration") or "-"), ""]
    lines.append("生成时间：%s" % benchmark.get("generated_at", ""))
    lines.append("")
    lines.append("| 配置 | 运行数 | 通过率 | 标准差 | 平均 tokens | 平均耗时(ms) |")
    lines.append("|---|---|---|---|---|---|")
    for c in benchmark.get("configs", []):
        rate = "—" if c["pass_rate"] is None else "%.0f%%" % (c["pass_rate"] * 100)
        tokens = "—" if c["mean_tokens"] is None else "%.0f" % c["mean_tokens"]
        dur = "—" if c["mean_duration_ms"] is None else "%.0f" % c["mean_duration_ms"]
        lines.append("| %s | %d | %s | %.3f | %s | %s |" % (
            c["config"], c["runs"], rate, c["pass_rate_stddev"] or 0.0, tokens, dur))
    delta = benchmark.get("delta") or {}
    if delta:
        lines += ["", "## 与基线对比", ""]
        for key in ("pass_rate", "mean_tokens", "mean_duration_ms"):
            value = delta.get(key)
            if value is None:
                continue
            if key == "pass_rate":
                lines.append("- 通过率变化：**%+.0f%%**（基线：%s）" % (value * 100, delta.get("baseline_config")))
            else:
                lines.append("- %s 变化：**%+.0f**" % (key, value))
    notes = benchmark.get("notes") or []
    if notes:
        lines += ["", "## 观察", ""]
        lines += ["- %s" % n for n in notes]
    lines.append("")
    return "\n".join(lines)


def latest_iteration(workspace):
    if not os.path.isdir(workspace):
        return None
    iterations = [d for d in os.listdir(workspace)
                  if d.startswith("iteration-") and os.path.isdir(os.path.join(workspace, d))]
    if not iterations:
        return None
    iterations.sort(key=_iteration_sort_key)
    return os.path.join(workspace, iterations[-1])
