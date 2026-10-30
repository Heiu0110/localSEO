# GEO Opportunity Finder · Core

Mode A là deterministic candidate detection, không cần API key. Mode B là phân tích có cấu trúc trong Agent hiện có và luôn cần human review. Cơ hội lưu rule/version, evidence IDs, actual observations, facts, explanations/hypotheses, counterevidence, missing info, 3 loại confidence, action/priority reason và verification plan.

| Rule | Điều kiện được triển khai | Hành động ban đầu |
|---|---|---|
| GEO-MENTION-001 | competitor mention xác nhận, brand không confirmed hoặc ambiguous trong cùng observation | Investigate |
| GEO-CITE-001 | provider annotation/grounding citation đúng domain đối thủ đã khai báo | Investigate nguồn, không bịa nội dung |
| GEO-CITE-002 | confirmed brand mention, complete capable citation set, không owned citation | Investigate |
| GEO-CITE-003 | owned citation, không mention brand và không ambiguity | No Action / quan sát source visibility |
| GEO-TOPIC-001 | prompt priority ≥2, không target URL/mapping approved trong references đã lưu | Investigate mapping, không khẳng định thiếu trang |
| GEO-TECH-001 | relevant URL tường minh + stored issue confirmed/strong thuộc allowlist | Review Technical SEO; stale→Investigation |
| GEO-ENTITY-001 | 2 approved user-verified sources có trường business nguyên văn khác nhau | Clarify Business Information, chưa chọn nguồn đúng |
| GEO-SOURCE-001 | cùng third-party domain được cite ở ≥2 prompt khác nhau trong cùng cohort | Investigate chất lượng/liên quan, không sao chép |
| GEO-CONTENT-001 | approved requirement + actual page content + latest human missing-coverage review có lý do | Improve Existing Content, vẫn cần xác minh ngữ nghĩa |

Technical allowlist: INDEX-002, CRAWL-002/004, CAN-003/004/006, LINK-004, ARCH-003. Chỉ issue hiện có thực sự khớp mới tạo candidate; không tạo finding từ rule unsupported hoặc từ thiếu FAQ/schema. Freshness >30 ngày/không rõ ngày phải điều tra lại. Identity conflict không tự chứng minh thông tin sai (chi nhánh/tên cũ có thể là counterevidence). Cơ hội content không được suy ra chỉ do thiếu một cụm từ.

Không có candidate nếu evidence không đáp ứng rule; detection run ghi abstention từng rule. Candidate absence nhỏ không thành P0. P1 chỉ dùng vấn đề cụ thể như Technical fresh hoặc identity conflict có nguồn; content human coverage P2; phần còn lại Investigation. Confidence evidence không đồng nghĩa interpretation/action. Priority có lý do riêng và không là lời hứa AI ranking.

Nguồn SEO đọc từ services/tables hiện có: exact target URL, approved Research mapping, Tracking reference; stored audit có source date; GSC page data đúng scope với provenance. Không ghép query×page không có sẵn, không fetch nguồn citation, không tự crawl. Mock/fixture vẫn có nhãn riêng, không coi là thực.

Human review idempotent detection không bị ghi đè; evidence thay đổi tạo candidate mới. Approved chỉ là quyết định của người dùng, không phát hành hoặc sửa website.
