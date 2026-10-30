"""Deterministic extraction, without DNS, HTTP, an LLM or HTML execution."""

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit, quote

GENERIC = {
    "an",
    "mai",
    "sen",
    "may",
    "việt",
    "viet",
    "nhà",
    "nha",
    "home",
    "best",
    "tốt",
    "tot",
}
UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def normalize_url(value):
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("URL không hợp lệ")
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Chỉ nhận URL HTTP(S) không chứa credentials")
    host = parsed.hostname.encode("idna").decode().lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
        raise ValueError("Hostname không hợp lệ")
    port = parsed.port
    netloc = host + (
        ":" + str(port)
        if port and (parsed.scheme.lower(), port) not in (("https", 443), ("http", 80))
        else ""
    )

    def percent(text):
        if re.search(r"%(?![0-9a-fA-F]{2})", text):
            raise ValueError("Percent encoding không hợp lệ")
        text = re.sub(
            r"%([0-9a-fA-F]{2})",
            lambda m: (
                chr(int(m[1], 16))
                if chr(int(m[1], 16)) in UNRESERVED
                else "%" + m[1].upper()
            ),
            text,
        )
        return quote(text, safe="/%:@!$&'()*+,;=-._~?[]%")

    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            percent(parsed.path or "/"),
            percent(parsed.query),
            "",
        )
    )


def domain_name(value):
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.port:
        raise ValueError("Domain registry chỉ nhận hostname; profile xã hội lưu riêng")
    return urlsplit(normalize_url(parsed.geturl())).hostname


def folded_map(text, accents=False):
    """Map normalized characters back to original Unicode codepoint offsets."""
    chars, positions = [], []
    index = 0
    while index < len(text):
        end = index + 1
        while end < len(text) and unicodedata.combining(text[end]):
            end += 1
        fragment = unicodedata.normalize("NFC", text[index:end]).casefold()
        if accents:
            fragment = "".join(
                c
                for c in unicodedata.normalize("NFD", fragment)
                if not unicodedata.combining(c)
            ).replace("đ", "d")
        chars.extend(fragment)
        positions.extend([(index, end)] * len(fragment))
        index = end
    return "".join(chars), positions


def terms_present(text, terms):
    folded, _ = folded_map(text)
    return any(
        term
        and re.search(r"(?<!\w)" + re.escape(folded_map(term)[0]) + r"(?!\w)", folded)
        for term in terms
    )


def mentions(text, entities):
    rows = []
    for entity in entities:
        aliases = [
            {
                "name": entity["name"],
                "ambiguous": entity["config"].get("ambiguous", False),
            },
            *entity["config"].get("aliases", []),
        ]
        emitted = []
        for accent_mode in (False, True):
            buffer, mapping = folded_map(text, accent_mode)
            for alias in sorted(aliases, key=lambda a: -len(a["name"])):
                term = folded_map(alias["name"], accent_mode)[0]
                if not term.strip():
                    continue
                pattern = (
                    r"(?<!\w)"
                    + r"\s+".join(re.escape(x) for x in term.split())
                    + r"(?!\w)"
                )
                for match in re.finditer(pattern, buffer):
                    start, end = mapping[match.start()][0], mapping[match.end() - 1][1]
                    if any(start < b and end > a for a, b in emitted):
                        continue
                    context = text[max(0, start - 100) : min(len(text), end + 100)]
                    ambiguous = (
                        alias.get("ambiguous")
                        or term in GENERIC
                        or len(term.strip()) < 3
                    )
                    if terms_present(context, alias.get("negative_terms", [])):
                        status, reason = (
                            "REJECTED_MATCH",
                            "Có ngữ cảnh loại trừ đã cấu hình.",
                        )
                    elif accent_mode:
                        status, reason = (
                            "POSSIBLE_MATCH",
                            "Chỉ khớp khi bỏ dấu; cần xác minh để tránh nhầm thực thể.",
                        )
                    elif ambiguous and not terms_present(
                        context, alias.get("context_terms", [])
                    ):
                        status, reason = (
                            "NEEDS_REVIEW",
                            "Tên/alias chung hoặc có khả năng mơ hồ; chưa tính là mention xác nhận.",
                        )
                    else:
                        status, reason = (
                            "CONFIRMED_MATCH",
                            "Khớp tên/alias đã cấu hình theo ranh giới Unicode"
                            + (" và ngữ cảnh được duyệt." if ambiguous else "."),
                        )
                    rows.append(
                        {
                            "entity_id": entity["id"],
                            "start": start,
                            "end": end,
                            "matched_text": text[start:end],
                            "alias": alias["name"],
                            "status": status,
                            "reason": reason,
                        }
                    )
                    emitted.append((start, end))
    for row in rows:
        if any(
            other["entity_id"] != row["entity_id"]
            and row["start"] < other["end"]
            and row["end"] > other["start"]
            and other["status"] != "REJECTED_MATCH"
            for other in rows
        ):
            if row["status"] != "REJECTED_MATCH":
                row.update(
                    status="NEEDS_REVIEW",
                    reason="Alias/range chồng lấn giữa các thực thể; không tự gán cho brand hoặc đối thủ.",
                )
    return rows


def ownership(url, entities):
    parsed = urlsplit(url)
    matches = []
    for entity in entities:
        matched = any(
            parsed.hostname == rule["domain"]
            or rule.get("include_subdomains")
            and parsed.hostname.endswith("." + rule["domain"])
            for rule in entity["config"].get("domains", [])
        )
        for profile in entity["config"].get("social_profiles", []):
            p = urlsplit(profile)
            matched |= parsed.hostname == p.hostname and (
                url == profile
                if p.query
                else parsed.path == p.path
                or parsed.path.startswith(p.path.rstrip("/") + "/")
            )
        if matched:
            matches.append(entity)
    if len(matches) > 1:
        return "AMBIGUOUS", None
    if not matches:
        return "THIRD_PARTY", None
    return ("OWNED_BRAND" if matches[0]["kind"] == "brand" else "COMPETITOR"), matches[
        0
    ]["id"]


def native_citations(raw):
    """Recognize explicit URL annotations and grounding support→chunk relations.

    Malformed, unsupported or truncated structures cannot establish a zero-citation
    response. Originals remain stored, while completeness is conservatively withheld.
    """
    result, warnings = [], []

    def section(container, key, limit=100):
        value = container.get(key, [])
        if not isinstance(value, list):
            warnings.append("Cấu trúc metadata citation không hợp lệ: " + key)
            return []
        if len(value) > limit:
            warnings.append("Metadata vượt giới hạn phân tích: " + key)
        return value[:limit]

    annotations = list(section(raw, "annotations"))
    for output in section(raw, "output", 30):
        if not isinstance(output, dict):
            warnings.append("Output không có cấu trúc hợp lệ.")
            continue
        for content in section(output, "content", 30):
            if not isinstance(content, dict):
                warnings.append("Output content không có cấu trúc hợp lệ.")
                continue
            annotations.extend(section(content, "annotations"))
    if len(annotations) > 100:
        warnings.append(
            "Annotations vượt giới hạn phân tích; chưa xác nhận completeness."
        )
    for index, annotation in enumerate(annotations[:100]):
        if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
            warnings.append(
                "Annotation không hợp lệ hoặc chưa hỗ trợ; cần review nguồn gốc."
            )
            continue
        value = annotation.get("url_citation", annotation)
        if not isinstance(value, dict) or not isinstance(value.get("url"), str):
            warnings.append("Annotation URL citation thiếu URL.")
            continue
        result.append(
            {
                "url": value["url"],
                "source_type": "provider_annotation",
                "annotation_id": str(annotation.get("id", index)),
                "start": value.get("start_index"),
                "end": value.get("end_index"),
                "offset_unit": "unicode_codepoint",
                "source_verification": "provider_reported",
            }
        )
    grounding = raw.get("groundingMetadata", raw.get("grounding_metadata", {}))
    if not isinstance(grounding, dict):
        warnings.append("Grounding metadata không có cấu trúc hợp lệ.")
    else:
        chunks = section(grounding, "groundingChunks")
        used = set()
        for support in section(grounding, "groundingSupports"):
            if not isinstance(support, dict):
                warnings.append("Grounding support không hợp lệ.")
                continue
            segment = support.get("segment", {})
            if not isinstance(segment, dict):
                warnings.append("Grounding segment không hợp lệ.")
                continue
            for index in section(support, "groundingChunkIndices"):
                if (
                    type(index) is not int
                    or not 0 <= index < len(chunks)
                    or not isinstance(chunks[index], dict)
                ):
                    warnings.append("Grounding support tham chiếu chunk không hợp lệ.")
                    continue
                web = chunks[index].get("web", {})
                if not isinstance(web, dict) or not isinstance(web.get("uri"), str):
                    warnings.append("Grounding chunk thiếu web URI.")
                    continue
                used.add(index)
                result.append(
                    {
                        "url": web["uri"],
                        "source_type": "grounding_metadata",
                        "annotation_id": str(index),
                        "start": segment.get("startIndex"),
                        "end": segment.get("endIndex"),
                        "quote": segment.get("text"),
                        "offset_unit": "unicode_codepoint",
                        "source_verification": "provider_reported",
                    }
                )
        if chunks and len(used) < len(chunks):
            warnings.append(
                "Có grounding chunk không có support reference; không tự coi chunk đó là citation."
            )
    if len(result) > 100:
        warnings.append("Citation vượt giới hạn phân tích; chưa xác nhận completeness.")
    return result[:100], warnings


def citation_rows(text, entries, entities):
    from .schemas import CitationInput

    rows, warnings, seen = [], [], set()
    if len(entries) > 100:
        warnings.append(
            "Citation vượt giới hạn phân tích; không xác nhận completeness."
        )
    for index, entry in enumerate(entries[:100]):
        try:
            value = CitationInput.model_validate(entry).model_dump()
            url = normalize_url(value["url"])
            host = urlsplit(url).hostname
            status, problems = "CONFIRMED_ATTRIBUTION", []
            if (
                value.get("reported_domain")
                and domain_name(value["reported_domain"]) != host
            ):
                problems.append("Domain khai báo không khớp URL citation.")
            start, end = value.get("start"), value.get("end")
            if (start is None) != (end is None):
                problems.append("Thiếu một đầu span citation.")
            elif start is not None:
                if value["offset_unit"] == "utf16":
                    boundaries, units = {0: 0}, 0
                    for i, char in enumerate(text):
                        units += 2 if ord(char) > 0xFFFF else 1
                        boundaries[units] = i + 1
                    start, end = boundaries.get(start), boundaries.get(end)
                if (
                    value["offset_unit"] == "unknown"
                    or start is None
                    or end is None
                    or not 0 <= start < end <= len(text)
                ):
                    problems.append(
                        "Offset citation chưa xác minh được với văn bản đã lưu."
                    )
                elif value.get("quote") and text[start:end] != value["quote"]:
                    problems.append("Quote citation không khớp span.")
            elif value.get("quote") and value["quote"] not in text:
                problems.append("Quote citation không có trong câu trả lời.")
            if problems:
                status = "NEEDS_REVIEW"
                warnings.extend(problems)
            owner, entity = ownership(url, entities)
            identity = (
                url,
                value["source_type"],
                value.get("annotation_id"),
                start,
                end,
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(
                {
                    "raw_url": value["url"],
                    "normalized_url": url,
                    "domain": host,
                    "source_type": value["source_type"],
                    "ownership": owner,
                    "entity_id": entity,
                    "attribution_status": status,
                    "data": {
                        **value,
                        "start": start,
                        "end": end,
                        "display_order": index + 1,
                        "problems": problems,
                        "url_verified": False,
                        "content_verified": False,
                    },
                }
            )
        except (ValueError, TypeError):
            warnings.append(
                f"Citation dòng {index + 1} không hợp lệ; giữ bản gốc, không tính là citation xác nhận."
            )
    return rows, warnings


def url_mentions(text):
    found = []
    for match in re.finditer(r"https?://[^\s<>\"\)\]]+", text):
        try:
            url = normalize_url(match.group().rstrip(".,;!"))
            found.append(
                {
                    "url": url,
                    "start": match.start(),
                    "end": match.end(),
                    "is_citation": False,
                }
            )
        except ValueError:
            pass
    return found[:50]
