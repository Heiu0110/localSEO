# LocalSEO v0.8 Core · Báo cáo nghiệm thu 30/10/2026

## A. Implemented capabilities

AI Visibility được thêm vào sidebar/router hiện có. Có website-scoped projects; một primary brand và nhiều competitor; aliases former/product/context/negative/ambiguity, domain/subdomain/profile ownership tường minh. Prompt Library có topic, intent, buyer stage, category/priority/locale/source và references Phase 7/Tracking.

Manual observation và CSV/JSON imports giữ nguyên raw response, prompt snapshot, native annotation/grounding metadata, collection context, original citation và provenance. Prompt import thêm XLSX. Preview kiểm tra toàn bộ, commit có xác nhận/expiry/stale guard/idempotence, tệp có SHA256 và import job ID. Sửa response append bản mới; re-extract append revision. Manual mention review và lịch sử review được lưu. AI-suggested prompt drafts có nhãn nguồn riêng và được nhập/review; chưa có batch prompt generator riêng.

Overview/citation/competitor reports có cohort filters, counts, tử số/mẫu số và exclusions; brand-containing prompts tách khỏi neutral. Unknown capability/metadata không là zero. Có evidence detail, source/coverage approvals, JSON/CSV exports an toàn, pagination và responsive UI theo theme monochrome hiện có. [Ảnh desktop](ui/visibility-overview-desktop.png), [mobile](ui/visibility-overview-mobile.png).

## B. GEO Opportunity Finder

9 rule thực thi: GEO-MENTION-001; GEO-CITE-001/002/003; GEO-TOPIC-001; GEO-TECH-001; GEO-ENTITY-001; GEO-SOURCE-001; GEO-CONTENT-001. Chi tiết điều kiện, source/action/prerequisite trong [catalog](GEO_OPPORTUNITY_ENGINE.md).

Mỗi candidate có evidence pointers, actual observation scope, facts, hypotheses, counterevidence, missing information, evidence/interpretation/action confidence riêng, priority reason và verification plan. Absence không thành P0. Stale/ambiguous/missing evidence có thể Investigate hoặc abstain. Citation không có mention có thể No Action; nguồn đối thủ chưa nhập không bị bịa nội dung. Content gap cần actual page + requirement + human coverage review; identity conflict cần approved verified sources và giá trị nguyên văn.

## C. AI Agent integration

9 read-only visibility tools gắn vào AIManager/ToolRegistry có sẵn (catalog tổng 29). GEOAnalysisContext và GEOOpportunityAnalysis là schema thật; khóa website/project/opportunity và known evidence IDs. Giữ provider/vault/consent/budget/model approval/history/review hiện có. Không có AI stack mới hoặc live collector.

Verifier chặn evidence ID giả, targets ngoài scope, sources/revisions stale và các mẫu cam kết/causality không được hỗ trợ; kiểm tra narrow predicates nhưng không khẳng định hiểu/kiểm chứng toàn bộ free semantics. Action thiếu prerequisites bị hạ thành investigation, cả action text và generic task/review recommendations được đồng bộ từ output đã gate. No Action không tạo task thay đổi. Phân tích giữ Needs Human Verification; approval không thực thi website changes. [Chi tiết](GEO_AGENT_INTEGRATION.md).

## D. Accuracy evaluation

26 reference examples được gắn nhãn: 14 text examples +12 scenario examples. Scenarios gồm import duplicate, provider/date/branded cohorts, incomplete observation, technical current/stale, invented evidence, valid-ID unsupported causality, third-party source repetition, identity conflict và no meaningful opportunity despite sufficient fixture observations.

Entity classification trên 27 quyết định xác định: **7 TP,20 TN,0 FP,0 FN**, precision=1.0, recall=1.0; **1 ambiguous entity decision abstained**. Citation attribution: **3 TP,0 FP,0 FN**, **1 wrong-domain example abstained**. Đây là bộ synthetic nhỏ, không là production accuracy hoặc xác minh nội dung/availability của nguồn citation. Các scenario được chạy bằng pytest riêng; script không tự suy ra chúng đã pass. [Nhãn](../backend/tests/fixtures/visibility/reference_cases.json), [kết quả máy đọc](AI_VISIBILITY_REFERENCE_RESULTS.json), [rubric/verifier](GEO_EVIDENCE_VERIFICATION.md).

## E. Source availability

| Nguồn | Trạng thái thực tế |
|---|---|
| Manual / JSON/CSV observations, CSV/JSON/XLSX prompts | Implemented; nguyên bản do người dùng cung cấp |
| OpenAI URL annotations / Gemini grounding payload | Imported parsing only; không live call |
| GSC | Existing SQLite property data khi đã sync; Mock/fixture có nhãn riêng; không tạo AI traffic |
| Technical SEO | Existing stored audit/URL/issues/links, explicit related URL và freshness; không crawl mới |
| Keyword Research / Tracking | Existing stored references, approved mapping/target và source prompt preview |
| Business/page/requirement | User-imported documents, approval/verification và coverage review riêng |
| Topical Map | Unavailable trong repo; không tạo service/tool giả |
| OpenAI web-search / Gemini live grounding | Not connected; future typed adapter contract, chưa có implementation/eligibility test |
| ChatGPT SIWC | Pending Live Verification như trước; không dùng credentials/code trong ảnh, không live auth/inference |

## F. Database

Migration **006_ai_visibility**, parent005, thêm **15 bảng**, không reset/drop/ALTER các bảng SEO/Agent cũ khi upgrade. Backup qua SQLite backup API trước migration. Đối chiếu count + SHA256 logical rows: **41/41 bảng cũ nguyên vẹn**, integrity_check=ok, foreign_key_check=0 tại migration. Test nâng cấp005→006 lặp lại cũng giữ nguyên mọi bảng/giá trị cũ. Browser tests sau đó tạo thêm fixture có chủ đích. Runtime backups/DB không được commit. [Data model](AI_VISIBILITY_DATA_MODEL.md).

## G. Files changed

- Backend mới: `app/visibility/{models,schemas,core,extraction,files,metrics,evidence,engine,verification,agent_integration,agent_tools,provider_contracts}.py`; `app/api/visibility_routes.py`; migration006.
- Tích hợp: `app/main.py`, health version, `migrations/env.py`, `app/ai/{agent,schemas,tools}.py`. Health/head/tool-count assertions cập nhật theo release; các regression assertions khác giữ nguyên.
- Frontend: `features/visibility/{VisibilityPage,Forms,Drawers,shared}.tsx`, types/API/CSS, lazy router/sidebar và GEO deep-link trong AI Workspace. Frontend package/lock chỉ đổi version sang0.8.0, không đổi dependency graph/launcher.
- Tests: `backend/tests/test_visibility.py`, 26-case reference JSON, `frontend/tests/visibility.spec.ts`, `scripts/evaluate_visibility.py`.
- Documentation: 8 tài liệu Visibility/GEO được yêu cầu + reference results/report/screenshots; README, ARCHITECTURE, VALIDATION, AI_AGENT_ROADMAP và AI_AGENT_TOOLS được cập nhật.

## H. Tests thực thi

| Kiểm tra | Baseline trước Phase 8 | Sau Phase 8 |
|---|---:|---:|
| Backend pytest | 271 passed | **319 passed** (48 bài Phase 8) |
| Playwright Chromium | 74 passed | **79 passed** (5 workflow Phase 8) |
| Frontend launcher Node tests | 22 passed | **22 passed** |
| TypeScript + Vite build | Passed | **Passed** |
| Dependency reuse probe | — | Dùng lại node_modules, bỏ qua npm ci |
| SQLite migration/data integrity | schema005 backed up | 41/41 old tables preserved, integrity/FK checks pass |
| Labelled extraction evaluation | — | 26-case set, text metrics và scenario assertions như mụcD |

Test commands:

```bash
cd backend
.venv/bin/python -m pytest -q
cd ..
npm --prefix frontend run build
node --test scripts/tests/frontend.test.mjs
backend/.venv/bin/python scripts/evaluate_visibility.py
cd frontend
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e
```

Playwright kiểm tra cả Dashboard/GSC/Technical/Tracking/Research/AI/ChatGPT UI. Visibility workflow gồm nhập raw/XSS-safe text, preview/commit/export, denominator Unknown, deterministic evidence/review, existing Agent history và 1440/1024/768/390px không viewport overflow/pageerror. Mock OAuth/provider fixtures không thay thế live validation.

Sau lượt regression toàn bộ, đã sửa race khi mở form tạo project trước khi catalog tải xong. Playwright giữ request catalog để kiểm tra form vẫn mở; focused Visibility smoke **5/5 pass** trên build/backend cuối cùng. Migration smoke sau chuẩn hóa whitespace DDL **1/1 pass**.

Một warning Starlette/httpx deprecation giống baseline; không có test fail còn tồn tại. Windows native runtime/vault, Google/OpenAI live authorization, live model quality, web-search/grounding eligibility và provider-specific license/retention chưa được thử trong môi trường này. Lượt regression không dùng API trả phí.

## I. Known limitations

Chỉ tập quan sát đã lưu, không AI market share/ranking/traffic. Unknown metadata không chứng minh cùng context, duplicate prompt runs không độc lập. Citation attribution không là fact verification. Source confidence/coverage/timestamp có thể thiếu, source URL không được app fetch. Verifier là narrow guards, không chứng minh mọi causal/free-text claim; cần human review. Full raw local retention chưa có auto-expiry scheduler. Có bounded import/storage/tool/context limits; kết quả quá lớn trả lỗi thay vì tự gửi toàn bộ dataset. [Giới hạn đầy đủ](AI_VISIBILITY_LIMITATIONS.md).

## J. Next release

Dừng ở **v0.8 Core**. Đề xuất v0.8.1 OpenAI live provider sau khi người dùng nghiệm thu Core và xác minh quyền web search/tool eligibility, pricing/consent/retention, citations/completeness, retries/cancellation và provenance. Gemini grounding đi sau với contract tương ứng. Chưa triển khai Phase 9/10/11, GEO publishing, Content/Social Automation hoặc unattended changes.
