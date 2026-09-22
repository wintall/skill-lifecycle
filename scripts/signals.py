"""退化信号与捕获信号的积分监测。

说明（诚实标注）：本模块是「事后/按需记录」的工具，真正的实时监测依赖 Agent 在
推理过程中主动调用它。它不提供后台推送能力 —— 这是当前 Agent 协议（含 MCP）
的固有限制：只能由 Agent 拉取，不能由服务端打断 Agent。
"""

import datetime
import json
import os

SIGNALS_FILENAME = "signals.json"

# 退化信号权重
DEGRADE_WEIGHTS = {
    "user_correction": (3, "用户纠正：说「不对/错了/不是这样」"),
    "ambiguity": (3, "指令歧义：同一指令有多种理解，走了错误分支"),
    "clarification": (2, "用户澄清：换一种方式重述同一请求"),
    "retry": (2, "反复重试：同类操作尝试 ≥3 次仍未成功"),
    "missing_context": (2, "缺失上下文：反问了本应由技能提供的信息"),
    "negative_sentiment": (2, "负面情绪：不满、催促、放弃当前路径"),
    "redundant_call": (1, "冗余调用：调用无关工具或重复调用同一工具"),
    "topic_drift": (1, "话题偏离：对话偏离技能的既定目标"),
    "positive_feedback": (-1, "正面反馈：说「很好/正确/就是这样」"),
}

# 捕获信号（用于 CAPTURED 模式）
CAPTURE_SIGNALS = {
    "multi_step_solution": ("高", "通过 ≥3 轮交互解决了一个完整问题，且无已有技能覆盖"),
    "new_domain_knowledge": ("高", "涉及所有已注册技能中没有的领域知识"),
    "reusable_pattern": ("高", "出现通用操作模式，未来大概率再次用到"),
    "tool_combination": ("中", "发现了多个工具/MCP 的有效协作方式"),
    "edge_case": ("中", "遇到并解决了非显而易见的边界情况"),
}

FIX_THRESHOLD = 5


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def signals_path(workspace):
    return os.path.join(workspace, SIGNALS_FILENAME)


def load(workspace):
    path = signals_path(workspace)
    if not os.path.exists(path):
        return {"events": [], "updated": ""}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {"events": [], "updated": ""}


def save(workspace, data):
    os.makedirs(workspace, exist_ok=True)
    with open(signals_path(workspace), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add(workspace, signal_type, note=""):
    """记录一条信号，返回 (事件, 汇总)。"""
    is_capture = signal_type in CAPTURE_SIGNALS
    weight = 0 if is_capture else DEGRADE_WEIGHTS.get(signal_type, (0, ""))[0]
    data = load(workspace)
    event = {
        "type": signal_type,
        "weight": weight,
        "kind": "capture" if is_capture else "degrade",
        "note": note,
        "timestamp": _now(),
    }
    data.setdefault("events", []).append(event)
    data["updated"] = _now()
    save(workspace, data)
    return event, summarize(workspace)


def summarize(workspace):
    """汇总积分并给出模式建议。"""
    data = load(workspace)
    events = data.get("events", [])
    degrade = [e for e in events if e.get("kind") != "capture"]
    capture = [e for e in events if e.get("kind") == "capture"]
    total = sum(int(e.get("weight", 0)) for e in degrade)
    types = {e.get("type") for e in degrade}

    fatal = {"user_correction", "clarification"}.issubset(types)
    high_capture = sum(1 for e in capture if CAPTURE_SIGNALS.get(e.get("type"), ("中", ""))[0] == "高")

    if fatal:
        mode = "FIX"
        reason = "致命组合：用户纠正 + 用户澄清 同时出现"
    elif total >= FIX_THRESHOLD:
        mode = "FIX"
        reason = "退化积分 %d ≥ 阈值 %d" % (total, FIX_THRESHOLD)
    elif high_capture >= 2:
        mode = "CAPTURED"
        reason = "检测到 %d 个高价值捕获信号" % high_capture
    elif total >= 2:
        mode = "MONITOR"
        reason = "退化积分 %d，尚未达到修复阈值，继续观察" % total
    else:
        mode = "NONE"
        reason = "信号不足，无需进化"

    return {
        "total": total,
        "degrade_events": len(degrade),
        "capture_events": len(capture),
        "high_value_capture": high_capture,
        "recommended_mode": mode,
        "reason": reason,
        "events": events,
    }


def reset(workspace):
    save(workspace, {"events": [], "updated": _now()})
    return summarize(workspace)
