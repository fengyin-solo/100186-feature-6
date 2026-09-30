"""管段档案业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pipe"
REQUIRED_FIELDS = ["管段编号", "管道类别", "起点井号"]
OPTIONAL_FIELDS = ["终点井号", "管径规格", "管材类型", "埋设深度", "管段状态"]
EDITABLE_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
STATUS_ORDER = ["待移交", "正常运行", "重点观测", "封闭施工"]
ACTION_RULES = {"办理移交": "正常运行", "标记观测": "重点观测", "封闭管段": "封闭施工"}
NEGATIVE_ACTIONS = []


def _norm(value: Any) -> str:
    return str(value or "").strip()


class PipeService:
    def _filter_rows(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        start_manhole: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """按条件逐步收窄：编号、类别、起点井号、状态之间是并列（AND）关系。"""
        rows = store.rows(MODULE)
        keyword = _norm(keyword)
        category = _norm(category)
        start_manhole = _norm(start_manhole)
        status = _norm(status)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("管段编号", ""))]
        if category:
            rows = [row for row in rows if category in str(row.get("管道类别", ""))]
        if start_manhole:
            rows = [row for row in rows if start_manhole in str(row.get("起点井号", ""))]
        if status:
            rows = [row for row in rows if str(row.get("status", "")) == status]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        start_manhole: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter_rows(
            keyword=keyword,
            category=category,
            start_manhole=start_manhole,
            status=status,
        )
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def summarize(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        start_manhole: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """统计概览：与列表共用同一份筛选口径，保证两边条数指向同一批管段。"""
        rows = self._filter_rows(
            keyword=keyword,
            category=category,
            start_manhole=start_manhole,
            status=status,
        )
        return {
            "total": len(rows),
            "observed": sum(1 for row in rows if str(row.get("status", "")) == "重点观测"),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记或更新管段。

        同一管段编号重复提交时覆盖原记录（只保留最新一版），不再追加新行；
        返回值第三项为 True 表示命中了已有编号并做了更新。
        """
        missing = [field for field in REQUIRED_FIELDS if not _norm(values.get(field))]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        pipe_no = _norm(values.get("管段编号"))
        existing = next(
            (row for row in rows if _norm(row.get("管段编号")) == pipe_no),
            None,
        )
        if existing is not None:
            for field in EDITABLE_FIELDS:
                if field in values:
                    existing[field] = values.get(field)
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
