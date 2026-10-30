# Evidence và giới hạn verifier

Evidence snapshot có ID, project, source type/record ID, source reference, signature và dữ liệu tối thiểu. Observation pointers giữ hash response, extraction revision, collection context, brand match/ambiguity. Mention/citation evidence giữ span/ownership/attribution, không coi existence của URL là proof nội dung.

Trước Agent analysis, server xác nhận website, project, opportunity và evidence IDs; IDs do mô hình trả phải nằm trong packet đã cấp. Evidence từ observation/mention/citation bị supersede/re-extract, review đổi hoặc registry hash cũ bị từ chối. Mapping đã đổi, source document rút approval, coverage review mới hoặc source SEO không còn trong website cũng bị chặn.

Verifier kiểm tra các predicate hẹp: confirmed mention, not-observed với observation complete và không ambiguity, owned/competitor attribution, existing confirmed technical issue, missing mapping, identity conflict và human coverage review. Nó không tự chứng minh phần giải thích tự do là đúng. Mọi phân tích giữ `semantic_assertions_automatically_confirmed=false`; hypothesis/unsupported predicate là Needs Human Verification.

Chặn evidence ID bịa và target prompt/URL ngoài scope. Chặn mẫu cam kết citation/ranking và câu khẳng định noindex/FAQ schema là nguyên nhân duy nhất. Đây là guardrail hẹp, không là bộ chứng minh nhân quả hoặc bộ hiểu ngữ nghĩa toàn diện. ID đúng không chứng minh diễn giải đúng. Các claim chưa được chứng minh phải được con người đọc đối chiếu nguồn.

Action thiếu prerequisite bị hạ xuống Investigate; P0 thiếu căn cứ bị hạ ưu tiên. Evidence confidence không được vượt confidence của candidate gốc; interpretation/action confidence không được nâng thành Verified/Strong do mô hình tự khẳng định. Review không nâng claim thành fact hoặc tự thực thi action.

Rubric độc lập: observation correctness, citation attribution, entity correctness, business relevance, interpretation, action feasibility, evidence completeness và usefulness. Mỗi tiêu chí: correct/partially correct/incorrect/insufficient evidence. Lưu người dùng sửa action riêng; fact/evidence gốc không bị sửa theo action.

Bộ reference: [26 nhãn](../backend/tests/fixtures/visibility/reference_cases.json), 14 text cases +12 scenario cases. Chạy pytest cho cả scenario và script `python scripts/evaluate_visibility.py` cho entity/citation reference scores. [Kết quả máy đọc](AI_VISIBILITY_REFERENCE_RESULTS.json): 7 TP,20 TN,0 FP,0 FN; 1 ambiguous entity decision abstained; precision/recall=1.0 trên những quyết định xác định trong mẫu nhỏ này. Citation attribution 3 TP,0 FP,0 FN,1 wrong-domain example abstained. Đây không là độ chính xác production và không chứng minh URL/claim được kiểm chứng ngoài nguồn nhập.
