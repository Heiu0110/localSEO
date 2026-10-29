"""Bounded local file interchange, reusing hardened Phase 4 spreadsheet reader."""

import csv, io, json
from openpyxl import Workbook
from app.keywords.spreadsheets import read_file
from app.ai.common import fail
from .schemas import Candidate, MetricInput, SerpInput

FIELDS = [
    "keyword_text",
    "country",
    "language",
    "provider",
    "group_name",
    "intent",
    "target_url",
    "notes",
    "search_volume",
    "cpc",
    "cpc_currency",
    "paid_competition",
    "organic_difficulty",
    "metric_scale",
    "metric_scope",
    "reporting_start",
    "reporting_end",
]
ALIASES = {
    "keyword_text": ["keyword", "từ khóa"],
    "provider": ["source", "nguồn"],
    "group_name": ["group", "nhóm"],
    "target_url": ["url", "target url"],
    "search_volume": ["search volume"],
    "paid_competition": ["competition"],
    "organic_difficulty": ["keyword difficulty"],
}


def read_keywords(content, filename, p, mapping):
    if len(content) > 100 * 1024:
        fail("research_file_limit", "Tệp tối đa 100 KiB.")
    if filename.lower().endswith(".json"):
        try:
            raw = json.loads(content.decode("utf-8-sig"))
            if isinstance(raw, dict):
                raw = raw["keywords"]
            if not isinstance(raw, list) or len(raw) > 1000:
                raise ValueError()
            return [Candidate.model_validate(x).model_dump(mode="json") for x in raw], {
                "format": "json"
            }
        except Exception:
            fail(
                "research_file",
                "JSON cần là danh sách Candidate hợp lệ, tối đa 1.000 dòng.",
            )
    headers, raw = read_file(content, filename)
    detected = {
        k: next((h for h in headers if h.casefold() in [k] + ALIASES.get(k, [])), None)
        for k in FIELDS
    }
    detected.update(mapping)
    if any(k not in FIELDS or v not in headers for k, v in mapping.items()):
        fail("research_mapping", "Ánh xạ cột không hợp lệ.")
    if not detected["keyword_text"]:
        fail("research_mapping", "Cần ánh xạ keyword_text hoặc cột Keyword.")
    rows = []
    for index, row in enumerate(raw, 2):
        values = {k: row.get(v, "") for k, v in detected.items() if v}
        metrics = []
        try:
            for typ in [
                "search_volume",
                "cpc",
                "paid_competition",
                "organic_difficulty",
            ]:
                value = values.get(typ, "")
                if not value:
                    continue
                if not values.get("provider"):
                    raise ValueError("Metric cần provider/source rõ ràng.")
                if typ == "cpc" and not values.get("cpc_currency"):
                    raise ValueError("CPC cần cpc_currency.")
                unit = (
                    "searches/month"
                    if typ == "search_volume"
                    else (
                        "currency/" + values["cpc_currency"]
                        if typ == "cpc"
                        else "provider_scale"
                    )
                )
                metrics.append(
                    MetricInput(
                        metric_type=typ,
                        value=value,
                        unit=unit,
                        scope=values.get("metric_scope") or "user_supplied_locale",
                        reporting_start=values.get("reporting_start") or None,
                        reporting_end=values.get("reporting_end") or None,
                        metadata=(
                            {"scale": values.get("metric_scale", "")}
                            if typ in ("paid_competition", "organic_difficulty")
                            else {}
                        ),
                    )
                )
            fields = {
                k: v
                for k, v in values.items()
                if k in Candidate.model_fields and v != ""
            }
            fields.setdefault("country", p.country)
            fields.setdefault("language", p.language)
            fields.update(method="file_import", metrics=metrics)
            rows.append(Candidate(**fields).model_dump(mode="json"))
        except Exception:
            fail(
                "research_file_row",
                f"Dòng {index} không hợp lệ: kiểm tra keyword, source, số/đơn vị/thang đo, intent và URL.",
            )
    return rows, {"headers": headers, "mapping": detected, "format": "spreadsheet"}


def read_serp(content, filename):
    if len(content) > 100 * 1024:
        fail("research_file_limit", "Tệp tối đa 100 KiB.")
    try:
        if filename.lower().endswith(".json"):
            return SerpInput.model_validate_json(content).model_dump(mode="json")
        headers, rows = read_file(content, filename)
        if not rows:
            raise ValueError()
        keys = [
            "keyword_id",
            "provider",
            "search_engine",
            "country",
            "language",
            "location",
            "device",
            "requested_depth",
            "collected_at",
            "completeness",
        ]
        meta = {k: rows[0][k] for k in keys if rows[0].get(k)}
        if any(any(r.get(k, "") != rows[0].get(k, "") for k in keys) for r in rows):
            raise ValueError()
        meta["results"] = [
            {
                k: r[k]
                for k in [
                    "organic_position",
                    "provider_position",
                    "result_type",
                    "title",
                    "url",
                    "snippet",
                ]
                if r.get(k)
            }
            for r in rows
        ]
        return SerpInput.model_validate(meta).model_dump(mode="json")
    except Exception:
        fail(
            "research_serp_file",
            "SERP cần một snapshot hợp lệ với metadata giống nhau trên các dòng; xem schema trong tài liệu.",
        )


def safe_cell(value):
    text = str(value) if value is not None else ""
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
        else text
    )


def export_file(data, format):
    if format == "json":
        return (
            json.dumps(data, ensure_ascii=False, indent=2).encode(),
            "application/json",
        )
    rows = data if isinstance(data, list) else [data]
    keys = list(dict.fromkeys(k for r in rows for k in r)) or ["empty"]
    table = [keys] + [
        [
            (
                json.dumps(r.get(k), ensure_ascii=False)
                if isinstance(r.get(k), (dict, list))
                else r.get(k)
            )
            for k in keys
        ]
        for r in rows
    ]
    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerows([[safe_cell(c) for c in row] for row in table])
        return out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
    book = Workbook()
    sheet = book.active
    for row in table:
        sheet.append([safe_cell(v) for v in row])
    out = io.BytesIO()
    book.save(out)
    book.close()
    return (
        out.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
