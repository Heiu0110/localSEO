"""Bounded preview/commit imports. Observation CSV cells retain their exact text."""

import csv
import io
import hashlib
from itertools import islice
import json
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from sqlalchemy import select
from app.ai.common import uid, now, view, fail, redact
from app.keywords.spreadsheets import read_file
from .models import VisibilityImportJob, VisibilityPrompt
from .schemas import PromptInput, ObservationInput
from . import core


def read_rows(content, filename, kind):
    if len(content) > core.LIMITS["file_bytes"]:
        fail("visibility_file_limit", "Tệp tối đa 100 KiB.")
    try:
        suffix = filename.rsplit(".", 1)[-1].lower()
        if suffix == "json":
            rows = json.loads(content.decode("utf-8-sig"))
            if isinstance(rows, dict):
                rows = rows.get(kind, rows.get("data"))
        elif suffix == "csv":
            text = content.decode("utf-8-sig")
            delimiter = (
                ";"
                if text.splitlines()[0].count(";") > text.splitlines()[0].count(",")
                else ","
            )
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            if (
                not reader.fieldnames
                or len(set(reader.fieldnames)) != len(reader.fieldnames)
                or len(reader.fieldnames) > 50
            ):
                raise ValueError()
            rows = list(islice(reader, core.LIMITS["import_rows"] + 1))
        elif suffix == "xlsx" and kind == "prompts":
            _, rows = read_file(content, filename)
        else:
            raise ValueError()
        if (
            not isinstance(rows, list)
            or not 1 <= len(rows) <= core.LIMITS["import_rows"]
        ):
            raise ValueError()
        return rows
    except Exception:
        fail(
            "visibility_file",
            "Nhập tối đa 100 dòng JSON/CSV UTF-8; Prompt hỗ trợ thêm XLSX không macro/công thức. Header dùng tên trường chuẩn.",
        )


def coerce(row, kind):
    values = dict(row)
    nested = (
        ("research_keyword_ids",)
        if kind == "prompts"
        else ("citations", "raw_annotations", "source_metadata")
    )
    for key in nested:
        if isinstance(values.get(key), str):
            values[key] = (
                json.loads(values[key])
                if values[key]
                else ([] if key in ("research_keyword_ids", "citations") else {})
            )
    for key, value in list(values.items()):
        if value == "" and key in (
            "model",
            "observed_at",
            "country",
            "language",
            "location",
            "prompt_snapshot",
            "artifact_reference",
            "research_cluster_id",
            "tracking_keyword_id",
            "target_url",
        ):
            values[key] = None
    return values


def preview(s, p, kind, rows, file=None):
    if kind not in ("prompts", "observations") or not 1 <= len(rows) <= 100:
        fail("visibility_import", "Loại nhập hoặc số dòng không hợp lệ.")
    core.project(s, p.id)
    schema = PromptInput if kind == "prompts" else ObservationInput
    valid, errors = [], []
    for index, row in enumerate(rows, 1):
        try:
            values = coerce(row, kind)
            data = schema.model_validate(values)
            if kind == "prompts":
                core.validate_prompt_refs(s, p, data.model_dump())
            else:
                core.scoped(s, VisibilityPrompt, data.prompt_id, p.id)
            valid.append(data.model_dump(mode="json"))
        except Exception:
            errors.append(
                {
                    "row": index,
                    "detail": "Dòng không hợp lệ hoặc tham chiếu khác project; kiểm tra schema, URL, timezone, metadata và trường bắt buộc. Không có dữ liệu được nhập từ dòng này.",
                }
            )
    if len(json.dumps(valid, ensure_ascii=False).encode()) > 110000:
        fail(
            "visibility_import_limit",
            "Dữ liệu sau phân tích quá lớn; chia thành tệp nhỏ hơn.",
        )
    identity = core.digest({"kind": kind, "rows": rows})
    existing = s.scalar(
        select(VisibilityImportJob).where(
            VisibilityImportJob.project_id == p.id,
            VisibilityImportJob.kind == kind,
            VisibilityImportJob.identity == identity,
        )
    )
    if existing and existing.status == "committed":
        return view(existing)
    payload = {
        "rows": valid,
        "errors": errors,
        "input_rows": len(rows),
        "validated_rows": len(valid),
        "file": file,
        "registry_hash": core.digest(core.entities(s, p.id)),
        "project_updated_at": p.updated_at,
        "note": "Preview không thêm prompt/observation. Commit xác nhận toàn bộ; có lỗi thì không nhập một phần.",
    }
    if existing:
        existing.data, existing.created_at, existing.status = payload, now(), "preview"
        return view(existing)
    job = VisibilityImportJob(
        id=uid(),
        project_id=p.id,
        kind=kind,
        identity=identity,
        status="preview",
        data=payload,
        created_at=now(),
    )
    s.add(job)
    s.flush()
    return view(job)


def commit(s, p, id):
    job = core.scoped(s, VisibilityImportJob, id, p.id)
    if job.status == "committed":
        return view(job)
    if job.data["errors"]:
        fail(
            "visibility_import_errors",
            "Sửa các dòng lỗi và preview lại trước khi commit.",
            409,
        )
    if datetime.fromisoformat(job.created_at) < datetime.now(timezone.utc) - timedelta(
        minutes=30
    ):
        fail(
            "visibility_import_expired", "Preview đã quá 30 phút; tạo preview mới.", 409
        )
    if (
        job.data["registry_hash"] != core.digest(core.entities(s, p.id))
        or job.data["project_updated_at"] != p.updated_at
    ):
        fail(
            "visibility_stale_preview",
            "Cấu hình project/entity đã đổi; preview lại trước khi nhập.",
            409,
        )
    created, duplicate, ids = 0, 0, []
    for row in job.data["rows"]:
        if job.kind == "prompts":
            result, is_new = core.save_prompt(s, p, PromptInput.model_validate(row))
        else:
            result, is_new = core.ingest(
                s, p, ObservationInput.model_validate(row), import_job=job
            )
        ids.append(result.id)
        created += int(is_new)
        duplicate += int(not is_new)
    job.status = "committed"
    job.data = {
        **job.data,
        "created": created,
        "duplicates": duplicate,
        "record_ids": ids,
    }
    return view(job)


def export(data, format):
    safe = redact(data)
    if format == "json":
        return (
            json.dumps(safe, ensure_ascii=False, indent=2).encode(),
            "application/json",
        )
    rows = safe["data"] if isinstance(safe, dict) else safe
    out = io.StringIO()
    keys = (
        list(dict.fromkeys(key for row in rows for key in row)) if rows else ["empty"]
    )
    writer = csv.writer(out)
    writer.writerow(keys)
    for row in rows:
        values = []
        for key in keys:
            value = row.get(key, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            text = str(value) if value is not None else ""
            if text.lstrip().startswith(("=", "+", "-", "@")):
                text = "'" + text
            values.append(text)
        writer.writerow(values)
    return ("\ufeff" + out.getvalue()).encode(), "text/csv; charset=utf-8"
