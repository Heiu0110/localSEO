# Native Web Search response parsing

Parser duyệt mọi output item, không dùng output[0]/root output_text làm toàn bộ câu trả lời. Nhận reasoning, web_search_call và assistant message/output_text; kiểm tra status/type/required fields. Các text block nối trực tiếp, không chèn ký tự vào original text; boundaries item/content được lưu để truy vết. Raw provider response giữ trong request, native annotations/IDs/title/order giữ trong immutable observation source metadata.

## Ba khái niệm riêng

| Khái niệm | Dữ liệu | Dùng làm answer citation? |
|---|---|---|
| Search Tool Action | native search/open_page/find_in_page + status | Không |
| SEARCH_SOURCE | action.sources URL, dedupe theo(call_id,normalized URL) | Không |
| ANSWER_CITATION | native url_citation trong output_text annotations | Có, khi URL/annotation được validate; content chưa xác minh |

Cited URL có thể không có trong optional source list. Không có source list không là zero citations. URL thường trong prose vẫn là URL mention. Search-source count là số records theo call×URL, không đồng nghĩa số URL duy nhất hoặc số sources độc lập.

SEARCH_COMPLETED cần qualifying search action completed, các action liên quan không failed/pending, response/message/text hợp lệ. Open_page đơn lẻ không đủ theo measurement contract này. Không có search: NO_SEARCH_EXECUTED; action failed/incomplete: SEARCH_FAILED; state/type không xác định: SEARCH_EXECUTION_UNKNOWN. Tool được khai báo/required không chứng minh provider đã search. Provider trả nhiều call hơn giới hạn đã chấp thuận được ghi nhận usage thực tế nhưng result partial, không đưa vào complete cohort.

Complete capable response có annotation list rỗng hợp lệ là zero citations. Thiếu list, annotations malformed/unsupported, URL/offset không hợp lệ thì citation metadata partial; không biến thành zero. Refusal/incomplete/no-search không vào completed grounded cohort. Optional sources thiếu vẫn cho phép valid citations. Malformed/oversized/sensitive payload có diagnostic an toàn thay vì fabricate observation.

## Offsets và Unicode

SDK gọi start_index/end_index là character indices nhưng không xác định đủ Unicode unit và inclusive/exclusive convention. Chưa có tài liệu/runtime live để khẳng định convention. App giữ nguyên raw indices; kiểm tra shape/bounds bảo thủ theo UTF-16 capacity. **Không tự chọn Python codepoint hoặc JavaScript UTF-16 mapping.**

Canonical CitationInput dùng URL/provider_annotation/annotation_id/source_verification hiện có; start/end mapping để null và offset_unit=unknown. URL attribution có thể xác nhận structurally khi span chưa được verify, nhưng không highlight sai. Raw invalid offsets làm citation completeness partial. Người dùng xem reference có title/domain riêng; metadata ghi rõ span unavailable. Mention highlights độc lập vẫn dùng codepoint mapping của Phase 8.

Native annotation trùng hệt trong cùng text block được dedupe; cùng URL ở vị trí/block khác vẫn là occurrence khác. Title, original annotation, response item/content/order/provider/response ID được giữ. URL normalize qua Core, giữ query/reserved encoding; private/unsafe URLs bị loại khỏi clickable/canonical records, không fetch.

## Fixture evaluation

[20 goldens](../backend/tests/fixtures/visibility/live_reference_cases.json) gồm owned/competitor/third-party, retrieved-not-cited, prose URLs, complete zero/missing list, no-search/open-only/failed/incomplete/refusal, multi-message/search, duplicates, Vietnamese/emoji/supplementary Unicode, invalid URL/offset và malformed output.

[Results](AI_VISIBILITY_LIVE_REFERENCE_RESULTS.json): **14 URL-citation TP,0 FP,0 FN**, precision/recall1.0 trên mẫu synthetic này; **11** mẫu có complete eligible citation metadata; **9** partial/ineligible/quarantined. Đây là URL-annotation parsing accuracy, không là production/live/source-content accuracy. Span mapping vẫn abstained/unverified; không tuyên bố highlight được xác nhận.

Chạy `backend/.venv/bin/python scripts/evaluate_live_visibility.py`. Pytest có assertions độc lập cho từng golden; không gọi provider trả phí.
