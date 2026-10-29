# Phân nhóm và intent

Manual là workflow có thẩm quyền: tạo/đổi tên cluster; gán/bỏ/chuyển keyword; chọn primary trong nhóm; intent/page type/target URL/notes; merge/split/delete; review draft/needs_review/approved/rejected/archived. Một keyword thuộc tối đa một cluster trong cùng Research project. Bulk gán cluster kiểm tra ownership; đổi thành viên yêu cầu rà soát lại. Approved không tự cập nhật Tracking/Topical Map.

Lexical v1: NFC/casefold, tách token Unicode, giữ dấu, bỏ stopwords nhỏ `là/và/của/cho/the/a/and`. Với cùng locale và không mâu thuẫn intent đã chọn, gợi ý khi cùng target URL hoặc có ≥2 tokens chung và Jaccard ≥0,5. Nhóm theo anchor, không nối chuỗi bắc cầu. Tối đa 200 keyword chưa gán, 20 nhóm, 20 keyword/nhóm/lượt. Tất cả draft/low confidence, có shared tokens/Jaccard/URL factors; không phải semantic NLP đầy đủ cho tiếng Việt.

SERP overlap v1: cần imported snapshots thật trong workspace (user-supplied, chưa live-verified). Dùng snapshot mới nhất đủ Top N của từng keyword/profile tương thích; Jaccard URL exact ≥0,5. Giữ snapshot IDs, locale/provider/device/location/depth và timestamps. Không có dữ liệu → unavailable. Các mẫu thời điểm khác nhau chỉ là bằng chứng hỗ trợ, không phải kết luận kiến trúc. Không tạo kết quả SERP giả.

Bấm lưu suggestion tạo cluster draft, ghi phương pháp/factors trong notes và review event. Người dùng xem primary/members/intent/URL và tự review. Không cộng volume các keyword thành unique audience demand vì close variants có thể chồng lấn. Mapping planned chỉ là kế hoạch, không tạo trang.

Intent hỗ trợ informational, commercial, transactional, navigational, local, mixed, unknown. Gợi ý từ modifier là low confidence, có evidence keyword ID và lý do, không tự ghi intent. Intent thủ công vẫn có thẩm quyền; có thể sửa khác gợi ý. Navigational cần người dùng xác nhận trong Core, không tự đoán thương hiệu.

AI-generated clustering nâng cao chưa triển khai. Agent có thể đọc clusters và diễn giải qua provider Phase 6 nhưng không tạo/duyệt cluster hoặc chuyển keyword tự động.
