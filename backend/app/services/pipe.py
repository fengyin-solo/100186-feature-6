"""管段档案业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pipe"
REQUIRED_FIELDS = ["管段编号", "管道类别", "起点井号"]
STATUS_ORDER = ["待移交", "正常运行", "重点观测", "封闭施工"]
ACTION_RULES = {"办理移交": "正常运行", "标记观测": "重点观测", "封闭管段": "封闭施工"}
NEGATIVE_ACTIONS = []


class PipeService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        start_manhole: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        rows = store.rows(MODULE)
        # 各条件并列收窄：管段编号、管道类别、起点井号同时给出时取交集，互不覆盖。
        keyword = (keyword or "").strip()
        category = (category or "").strip()
        start_manhole = (start_manhole or "").strip()
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("管段编号", ""))]
        if category:
            rows = [row for row in rows if category in str(row.get("管道类别", ""))]
        if start_manhole:
            rows = [row for row in rows if start_manhole in str(row.get("起点井号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        # 统计与列表同口径：基于过滤后、分页前的同一批管段计算。
        summary = {
            "在册管段": total,
            "重点观测管段": sum(1 for row in rows if row.get("status") == "重点观测"),
        }
        start = max(page - 1, 0) * size
        return rows[start:start + size], total, summary

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], bool]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        pipe_no = str(values["管段编号"]).strip()
        existing = next(
            (row for row in rows if str(row.get("管段编号", "")).strip() == pipe_no), None
        )
        if existing is not None:
            # 同一管段编号重复提交只保留最新一版，沿用原 id 与状态，不新增重复行。
            existing.update({field: values.get(field) for field in REQUIRED_FIELDS})
            return existing, [], True
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, [], False

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"管段 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于管段档案可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"管段已{action}"
