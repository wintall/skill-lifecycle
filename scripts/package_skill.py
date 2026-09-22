"""把技能目录打包为可分发的 .skill 文件（本质是 zip）。"""

import os
import zipfile

SKIP_DIRS = {".git", "__pycache__", ".skill-lifecycle", "node_modules", ".venv"}


def package(skill_path, out_dir=None, validate=True):
    skill_path = os.path.abspath(skill_path)
    if not os.path.isdir(skill_path):
        raise NotADirectoryError("技能目录不存在：%s" % skill_path)
    if validate and not os.path.exists(os.path.join(skill_path, "SKILL.md")):
        raise FileNotFoundError("缺少 SKILL.md，拒绝打包：%s" % skill_path)

    name = os.path.basename(skill_path)
    out_dir = out_dir or os.path.dirname(skill_path)
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "%s.skill" % name)

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(skill_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith((".skill", ".pyc")):
                    continue
                full = os.path.join(root, f)
                arcname = os.path.join(name, os.path.relpath(full, skill_path))
                zf.write(full, arcname)
    return target
