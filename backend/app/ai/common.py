import json
import re
from datetime import datetime, timezone
from uuid import uuid4
from app.gsc.errors import GSCError


def uid():
    return uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


def fail(code, message, status=422):
    raise GSCError(code, message, status)


def view(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def require(session, model, id):
    result = session.get(model, id)
    if not result:
        fail("ai_not_found", "Không tìm thấy dữ liệu AI Workspace.", 404)
    return result


def redact(value):
    if isinstance(value, dict):
        return {
            str(k): (
                "[đã ẩn]"
                if re.search(
                    r"(^|_)(api.?key|access.?token|refresh.?token|authorization|password|secret)($|_)",
                    str(k),
                    re.I,
                )
                else redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(
            r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{12,}|ya29\.[A-Za-z0-9_.-]{10,}|Bearer\s+[A-Za-z0-9_.-]{10,})",
            "[đã ẩn khóa/token]",
            value,
            flags=re.I,
        )
        value = re.sub(
            r"([?&](?:api_key|token|access_token|secret)=)[^&#\s]+",
            r"\1[đã ẩn]",
            value,
            flags=re.I,
        )
        return value
    return value


def limited(value, max_bytes=8000):
    value = redact(value)

    # Bound untrusted text before serializing; never split serialized JSON.
    def trim(v):
        if isinstance(v, str):
            return v[:1200] + "…" if len(v) > 1200 else v
        if isinstance(v, dict):
            return {k: trim(x) for k, x in v.items()}
        if isinstance(v, list):
            return [trim(x) for x in v[:10]]
        return v

    value = trim(value)
    if len(json.dumps(value, ensure_ascii=False).encode()) > max_bytes:
        fail(
            "ai_result_too_large",
            "Kết quả vượt giới hạn an toàn. Thu hẹp câu hỏi hoặc khoảng dữ liệu.",
        )
    return value
