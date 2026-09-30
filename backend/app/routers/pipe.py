"""管段档案接口：维护管段，覆盖办理移交、标记观测、封闭管段等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.pipe import PipeService

router = APIRouter(prefix="/api/pipe", tags=["管段档案"])

service = PipeService()

LIST_FIELDS = ["管段编号", "管道类别", "起点井号", "终点井号", "管径规格", "管材类型", "埋设深度", "管段状态"]
STATUSES = ["待移交", "正常运行", "重点观测", "封闭施工"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按管段编号检索"),
    category: str | None = Query(default=None, description="按管道类别过滤"),
    start_manhole: str | None = Query(default=None, description="按起点井号过滤"),
    status: str | None = Query(default=None, description="待移交、正常运行、重点观测、封闭施工"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """管段编号可单独检索，管道类别与起点井号组合使用；各条件并列生效。

    没有命中数据时返回空页，不报错。
    """
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword,
        category=category,
        start_manhole=start_manhole,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def pipe_stats(
    keyword: str | None = Query(default=None, description="按管段编号检索"),
    category: str | None = Query(default=None, description="按管道类别过滤"),
    start_manhole: str | None = Query(default=None, description="按起点井号过滤"),
    status: str | None = Query(default=None, description="待移交、正常运行、重点观测、封闭施工"),
) -> dict[str, Any]:
    """列表概览条数：与列表接口共用同一份筛选口径，指向同一批管段。"""
    return service.summarize(
        keyword=keyword,
        category=category,
        start_manhole=start_manhole,
        status=status,
    )


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出管段档案清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pipe", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条管段明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"管段 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条管段，缺字段时说明原因而不是静默丢弃。

    同一管段编号重复提交时只保留最新一版（覆盖更新），不会新增重复记录。
    """
    entry, missing, updated = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if updated:
        return ActionResult(ok=True, message="管段编号已存在，已按最新提交覆盖更新", entry=entry)
    return ActionResult(ok=True, message="管段已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条管段执行办理移交、标记观测、封闭管段；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
