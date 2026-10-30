# Sử dụng AI Visibility / GEO

1. Chạy backend và frontend theo README; mở **AI Visibility → Dự án Visibility mới**, chọn website đã có. Một website có thể có nhiều dự án.
2. Ở **Cấu hình**, khai báo một brand chính và các đối thủ. Chỉ khai báo domain/alias được xác nhận. `example.com.vn` khác `example.com`; subdomain chỉ có ownership khi chọn rõ. Profile xã hội phải có đường dẫn tài khoản, không dùng domain gốc của cả nền tảng.
3. Thêm **Prompt Library**: topic, intent, buyer stage, country/language, priority và cohort. Alias JSON nâng cao hỗ trợ former/product name, từ ngữ cảnh và từ loại trừ. Tên chung cần review. Có thể preview/import CSV/JSON/XLSX prompts hoặc chọn Research keywords/clusters/Tracked keywords đã lưu. Prompt do AI đề xuất phải chọn nguồn “Ứng viên do AI đề xuất”; không phải observed demand. Core không tự sinh/thu thập prompt hàng loạt.
4. **Quan sát → Nhập phản hồi AI**: chọn prompt, nhập provider, dán toàn bộ phản hồi. Thời gian/model/locale/grounding không biết để Unknown. Chỉ chọn citation metadata “đầy đủ” khi thực sự đã giữ đầy đủ annotations/citations, kể cả trường hợp zero. URL trong văn bản không được tự tính thành citation.
5. **Nhập / Xuất**: observation JSON/CSV cần `prompt_id` có sẵn trong project; ID hiển thị tại Prompt Library. Preview kiểm tra mọi dòng; có lỗi thì chặn toàn bộ commit. Nhập trùng bỏ qua; xác nhận commit có thể retry an toàn. File provenance có tên/hash/bytes và job ID. XLSX chỉ dùng cho prompt.
6. **Tổng quan / Đối thủ / Citations**: đọc tử số, mẫu số và scope từng cohort. Không cộng các phần trăm provider/model. Branded prompt bị tách khỏi neutral; thay registry không âm thầm viết lại kết quả cũ.
7. Mở quan sát để đọc nguyên văn, highlight codepoint, citation/URL, annotation/provenance, missing metadata. Review mention có lý do; sửa phản hồi tạo bản mới, giữ bản cũ; phân tích lại nhận diện tạo revision mới và giữ review cũ.
8. **GEO Opportunities → Phát hiện cơ hội từ evidence** chạy 9 rule ngoại tuyến. Đọc fact, hypothesis, counterevidence, missing information và kế hoạch xác minh. Lượt không có rule phù hợp sẽ abstain.
9. Muốn kiểm tra identity/content gap: nhập nguồn thực tại **Ngữ cảnh & nguồn**. Business fields phải có nguyên văn và được người dùng xác minh/duyệt. Content gap cần requirement, nội dung trang thực nhập, approval và coverage review có lý do; không cần/không có fetch URL.
10. Trong drawer cơ hội, chọn **Tạo phân tích ngoại tuyến**, hoặc **Phân tích sâu trong AI Workspace** để dùng provider đã cấu hình và xác nhận gửi dữ liệu theo luồng có sẵn. Mở link không tự gửi inference. Phân tích và evidence nằm trong lịch sử Agent hiện có.
11. Human Review cho phép approve/reject/needs evidence/investigate, chỉnh đề xuất và chấm 8 tiêu chí. Approval chỉ lưu quyết định. Nó không sửa website hoặc biến diễn giải thành fact.

Ví dụ JSON observation (thay `prompt_id` bằng ID thật):

```json
[{"prompt_id":"ID_DA_LUU","provider":"manual consumer sample","response_text":"Phản hồi gốc...","collection_method":"IMPORTED_RESPONSE","citation_capability":"unknown","citation_metadata":"missing"}]
```

Ví dụ CSV prompt UTF-8:

```csv
text,topic,category,intent,cohort_type,source
"Những tiêu chí chọn xưởng may balo?","may balo","Supplier Discovery",commercial,neutral,import
```

Xuất JSON/CSV bằng bộ lọc hiện tại; CSV escape formula injection. Artifact reference chỉ là nhãn provenance, không đọc đường dẫn file. Không nhập token, private credentials hay nội dung chưa được phép lưu/chia sẻ.
