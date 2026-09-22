"""测试用例（evals）管理。

evals.json 是纯文本 JSON，可被任何 Agent 读写，是与进化记忆并列的另一份核心资产。
缺陷 -> 回归测试 的转换（defect_to_eval）是本模块的关键能力：线上翻的车会沉淀成
永久的测试用例，避免同一个坑摔第二次。
"""

import datetime
import json
import os
import re

EVALS_FILENAME = "evals.json"


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _slug(text, maxlen=32):
    s = re.sub(r"[^0-9A-Za-z]+", "-", text or "").strip("-").lower()
    return s[:maxlen].strip("-") or "case"


def load(evals_path):
    """读取 evals.json，不存在时返回空结构。"""
    if not os.path.exists(evals_path):
        return {"skill_name": "", "evals": []}
    try:
        with open(evals_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return {"skill_name": "", "evals": []}
    data.setdefault("skill_name", "")
    data.setdefault("evals", [])
    return data


def save(evals_path, data):
    directory = os.path.dirname(os.path.abspath(evals_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(evals_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_id(data):
    ids = [int(e.get("id", 0)) for e in data.get("evals", []) if str(e.get("id", "")).isdigit()]
    return (max(ids) + 1) if ids else 1


def add_eval(evals_path, prompt, expected_output="", files=None, assertions=None,
             name=None, source="manual"):
    """新增一条测试用例，返回该用例 dict。"""
    data = load(evals_path)
    eid = next_id(data)
    entry = {
        "id": eid,
        "name": name or "%d-%s" % (eid, _slug(prompt)),
        "prompt": prompt,
        "expected_output": expected_output,
        "files": list(files or []),
        "assertions": list(assertions or []),
        "source": source,
        "created_at": _now(),
    }
    data["evals"].append(entry)
    save(evals_path, data)
    return entry


def from_defect(defect, prompt=None, expected_output=None):
    """把一条已知缺陷转成测试用例（回归测试）。"""
    desc = defect.get("desc", "")
    return {
        "prompt": prompt or ("复现并正确处理：%s" % desc),
        "expected_output": expected_output or ("不得再出现：%s" % desc),
        "source": "defect",
    }


def list_evals(evals_path):
    return load(evals_path).get("evals", [])


def find_eval(evals_path, eval_id):
    for e in list_evals(evals_path):
        if str(e.get("id")) == str(eval_id):
            return e
    return None


def add_assertion(evals_path, eval_id, text, kind="manual"):
    """给测试用例追加一条可客观验证的断言。"""
    data = load(evals_path)
    for e in data.get("evals", []):
        if str(e.get("id")) == str(eval_id):
            e.setdefault("assertions", []).append({"text": text, "kind": kind})
            save(evals_path, data)
            return e
    raise KeyError("eval not found: %s" % eval_id)
