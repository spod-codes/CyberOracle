from datetime import datetime, timezone
import statistics
import time
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from lib.db import db
from lib.world_model import run_world_model
from models.evaluation import (
    BriefingSignoff,
    BriefingSignoffUpdate,
    DeleteResponse,
    EvaluationListItem,
    EvaluationRecord,
    KernelTestResult,
    ReplayNote,
    ReplayNoteCreate,
    ReplayNoteUpdate,
)


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationRecord)
async def create_evaluation(
    file: UploadFile = File(...),
    architecture: str = Form("Temporal Transformer"),
    horizon: int = Form(8),
    window_size: int = Form(50),
    explainability: str = Form("Attention weights"),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a CSV telemetry file.")
    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV files must be smaller than 12 MB.")
    try:
        context = await db.model_context.find_one({"id": "active"})
        record = run_world_model(raw, file.filename, architecture, horizon, window_size, explainability, float(context.get("risk_multiplier", 1.0)) if context else 1.0)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.evaluations.insert_one(record.model_dump())
    return record


@router.get("", response_model=list[EvaluationListItem])
async def list_evaluations():
    documents = await db.evaluations.find({}, {"preview": 0, "timeline": 0, "stages": 0, "attributions": 0, "flows": 0}).sort("created_at", -1).to_list(20)
    return [EvaluationListItem(**document) for document in documents]


from fastapi.responses import FileResponse
import os
import glob

@router.get("/datasets")
async def list_datasets():
    base_dir = os.path.join(os.path.dirname(__file__), "..", "datasets")
    files = glob.glob(os.path.join(base_dir, "**", "*.*"), recursive=True)
    datasets = []
    for f in files:
        if f.endswith(".csv") or f.endswith(".binetflow"):
            rel_path = os.path.relpath(f, base_dir)
            datasets.append({"id": rel_path.replace("\\", "/"), "name": os.path.basename(f), "size": os.path.getsize(f)})
    return datasets

@router.get("/datasets/{dataset_id:path}")
async def get_dataset(dataset_id: str):
    base_dir = os.path.join(os.path.dirname(__file__), "..", "datasets")
    file_path = os.path.join(base_dir, dataset_id.replace("/", os.sep))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
    return FileResponse(file_path)


@router.get("/{evaluation_id}", response_model=EvaluationRecord)
async def get_evaluation(evaluation_id: str):
    document = await db.evaluations.find_one({"id": evaluation_id})
    if not document:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return EvaluationRecord(**document)


@router.post("/{evaluation_id}/notes", response_model=ReplayNote)
async def create_replay_note(evaluation_id: str, input: ReplayNoteCreate):
    if not await db.evaluations.find_one({"id": evaluation_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    if not input.text.strip():
        raise HTTPException(status_code=422, detail="Replay notes cannot be empty.")
    note = ReplayNote(
        id=str(uuid4()),
        window_label=input.window_label,
        text=input.text.strip(),
        category=input.category.strip() or "Finding",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    await db.evaluations.update_one({"id": evaluation_id}, {"$push": {"notes": note.model_dump()}})
    return note


@router.put("/{evaluation_id}/notes/{note_id}", response_model=ReplayNote)
async def update_replay_note(evaluation_id: str, note_id: str, input: ReplayNoteUpdate):
    document = await db.evaluations.find_one({"id": evaluation_id, "notes.id": note_id})
    if not document:
        raise HTTPException(status_code=404, detail="Replay note not found.")
    text = input.text.strip()
    category = input.category.strip()
    if not text or not category:
        raise HTTPException(status_code=422, detail="Note text and category are required.")
    existing = next(note for note in document.get("notes", []) if note.get("id") == note_id)
    updated_at = datetime.now(timezone.utc).isoformat()
    await db.evaluations.update_one(
        {"id": evaluation_id, "notes.id": note_id},
        {"$set": {"notes.$.text": text, "notes.$.category": category, "notes.$.updated_at": updated_at}},
    )
    return ReplayNote(**{**existing, "text": text, "category": category, "updated_at": updated_at})


@router.delete("/{evaluation_id}/notes/{note_id}", response_model=DeleteResponse)
async def delete_replay_note(evaluation_id: str, note_id: str):
    result = await db.evaluations.update_one({"id": evaluation_id, "notes.id": note_id}, {"$pull": {"notes": {"id": note_id}}})
    if not result.modified_count:
        raise HTTPException(status_code=404, detail="Replay note not found.")
    return DeleteResponse()


@router.put("/{evaluation_id}/signoff", response_model=BriefingSignoff)
async def update_briefing_signoff(evaluation_id: str, input: BriefingSignoffUpdate):
    allowed_statuses = {"Draft", "In Review", "Approved", "Escalated"}
    if input.status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Choose a valid review status.")
    analyst_name = input.analyst_name.strip()
    if not analyst_name:
        raise HTTPException(status_code=422, detail="Analyst name is required.")
    approval_date = input.approval_date or (datetime.now(timezone.utc).date().isoformat() if input.status == "Approved" else None)
    signoff = BriefingSignoff(
        analyst_name=analyst_name,
        status=input.status,
        approval_date=approval_date,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    result = await db.evaluations.update_one({"id": evaluation_id}, {"$set": {"signoff": signoff.model_dump()}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return signoff


import asyncio

@router.post("/{evaluation_id}/kernel-test", response_model=KernelTestResult)
async def run_kernel_test(evaluation_id: str):
    started = time.perf_counter()
    document = await db.evaluations.find_one({"id": evaluation_id})
    if not document:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    import sys
    from pathlib import Path
    import asyncio
    
    script_path = Path(__file__).parent.parent / "kernel_cli.py"
    
    # Run the kernel_cli python script in the background and capture its stdout
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path), "--evaluation", evaluation_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(script_path.parent)
        )
        stdout, _ = await proc.communicate()
        raw_logs = stdout.decode("utf-8", errors="replace").strip().split('\n')
        # Clean up carriage returns
        real_logs = [line.strip() for line in raw_logs if line.strip()]
    except Exception as e:
        real_logs = [f"[error] Failed to execute kernel diagnostics: {e}"]

    elapsed = max(1, round((time.perf_counter() - started) * 1000))

    return KernelTestResult(
        status="passed" if proc.returncode == 0 else "failed",
        logs=real_logs,
        checks={"native_kernel_spawned": True},
        metrics={},
        duration_ms=elapsed,
        tested_at=datetime.now(timezone.utc).isoformat()
    )


@router.delete("/{evaluation_id}", response_model=DeleteResponse)
async def delete_evaluation(evaluation_id: str):
    result = await db.evaluations.delete_one({"id": evaluation_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return DeleteResponse()