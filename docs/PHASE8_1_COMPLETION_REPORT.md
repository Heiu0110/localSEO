# LocalSEO v0.8.1 · Live AI Citation Provider · 30/10/2026

**Implementation Complete. Live Provider: Pending Live Verification.** Không chạy API trả phí thật, không dùng SIWC credentials để thử Web Search. Kết quả mock không được coi là eligibility/live quality.

## A. Completed features

Thêm AI Search trong AI Visibility và action trên Prompt Library. Luồng một prompt có provider/model access check, preflight giá/context, consent theo request, một paid dispatch, polling/history/cancel-before-submit, raw diagnostic, Observation link, clickable native citation titles, Search Sources riêng và human QA. Giữ manual/import, registry, metrics/GEO/Agent và mọi module SEO cũ. Không scheduler, batch monitoring, consumer browser automation hoặc publishing. [Desktop chưa cấu hình](ui/visibility-live-desktop.png), [mobile với provider mock](ui/visibility-live-mobile.png).

## B. Provider / contract

OpenAI Responses API với `web_search`, một tool được yêu cầu bằng `tool_choice=required`, `store=false`, bounded output/tool calls và include action sources. Runtime model do người dùng chọn, không hardcode Sol/Astra. GET model chỉ Model Accessible; Web Search Supported chỉ sau actual qualifying search response theo account/model đó. Live human verification là mức riêng.

Tài liệu guide/Markdown/API reference/pricing bị Tunnel403. Đã đối chiếu SDK chính thức commit `05992039b9f7b78a48cf1e5a35727ba27d96db6e`: request/tool/source/status/citation schema. Không xác minh live pricing/eligibility/Unicode convention. [Contract và nguồn](AI_VISIBILITY_LIVE_PROVIDER.md).

## C. Citation quality

Traversal nhiều output/message/search items, original answer/annotation provenance, source/action/citation separation, duplicate handling, URL validation và conservative span mapping. Search source không tăng citation rate hoặc trigger citation GEO. No-search/incomplete/refusal/failed không thành complete grounded sample. Valid zero khác missing/malformed metadata. Ownership ambiguous không được coi là zero citation.

20 manually-labelled synthetic provider-shaped goldens: **14 citation URL TP,0 FP,0 FN; precision/recall1.0** trên tập này. **11** eligible complete citation samples, **9** partial/ineligible/quarantined examples. Chưa xác minh span Unicode/end convention: giữ indices gốc, references riêng, không highlight sai. Không suy rộng production/live/source-content accuracy. [Results](AI_VISIBILITY_LIVE_REFERENCE_RESULTS.json), [parser](OPENAI_CITATION_PARSING.md).

## D. Financial controls

Reuse `ai_usage_records`, không có ledger/billing stack trùng. Shared daily API budget/lock cùng Agent; explicit per-request reservation. Đủ giá input/output/tool/date trước preflight; search-content unknown được hiển thị và cần consent riêng. Binding gồm prompt revision/config/context/pricing/cap/key fingerprint, expiry10 phút; stale phải tạo lượt mới. Transport pin credential fingerprint trước Authorization. Không retry paid POST, không paid fallback sang SIWC/key khác. Unknown outcomes giữ reservation; token counts hợp lệ được giữ khi normalization lỗi; USD chỉ estimates, không provider actual amount/billing cap. [Chi tiết](AI_VISIBILITY_COST_CONTROL.md).

## E. GEO / Agent

Candidate persist qua `core.ingest`, collection_method PROVIDER_API; extraction/ownership/cohort metrics và 9 GEO rules tái sử dụng. Measurement profile giữ tool context/call/output limits/instruction version riêng, không gộp khác phép đo. Review rejected revision bị loại, có bộ lọc chỉ extraction confirmed; Agent verifier không dùng evidence đã bị từ chối. Original provider response không bị sửa qua correction endpoint. Human approval không publish hoặc sửa website. Existing Agent/offline evidence/history tiếp tục hoạt động; không tạo Agent thứ hai.

## F. Security

Existing OS Credential Vault, không key trong SQLite/log/React responses, không sửa ChatGPT OAuth. POST fixed HTTPS official API, trust_env=false, redirects=false, no retries; bounded timeout/body256KiB/strict JSON. Chặn unsafe/private citation/source URL kể cả legacy numeric IPv4, không DNS/fetch/crawl source. Raw HTML escaped, external link protection, project/prompt/request/source scope và CSRF/Origin giữ nguyên. Sensitive/oversized/malformed payload không được ghi thành success. Secrets bị phát hiện không được giữ plaintext trong raw diagnostics.

## G. Database / files

Migration **007_visibility_live_provider**, parent006, thêm **3 bảng** request/consent/search_sources; usage dùng bảng AI cũ. Backup trước upgrade và inventory count+logical SHA256: **56/56 bảng cũ giữ nguyên**, integrity_check=ok, foreign_key_check=0. Backup restore đã thử và so lại toàn bộ56 bảng. Repeat migration/dedicated upgrade test có original settings/visibility review/Agent usage rows đều giữ nguyên. Browser fixtures sau migration là thay đổi có chủ đích, không là migration mutation.

File chính:

- Backend: `visibility/live_{models,schemas,costs,parser,collection,review}.py`, `openai_web_search.py`, existing provider contract, `api/visibility_live_routes.py`, migration007. Runtime/lifespan thêm recovery/close; Core/metrics/verifier thêm live immutability/QA/measurement guards.
- Frontend: `LiveResearchPanel.tsx`, `LiveObservationEvidence.tsx`, VisibilityPage/Drawers, live types và CSS theo theme cũ. Package/lock chỉ bump version0.8.1, không đổi dependencies.
- Tests/reference: `test_visibility_live.py`, 20-case JSON, `visibility-live.spec.ts`, `evaluate_live_visibility.py`. Old test assertions chỉ cập nhật version/head/table count theo migration.
- Documentation: 6 tài liệu được yêu cầu, reference results, README/architecture/validation/roadmap/provider/limits; không thay nội dung historical Phase 8 report.

## H. Actual tests

| Check | Baseline thực chạy | Sau triển khai |
|---|---:|---:|
| Backend pytest |319 passed|**403 passed** (84 bài mới)|
| Playwright Chromium |79 passed|**86 passed** (7 bài mới)|
| Launcher Node suite |22 passed|**22 passed**|
| TypeScript/Vite production build |Passed|**Passed**|
| Launcher dependency reuse |—|Dùng node_modules, bỏ qua npm ci|
| Migration / integrity / restore |schema006 backup|56/56 preserved; integrity/FK/restore pass|
| Provider-shaped evaluation |—|20 goldens; results như mụcC|

403 backend bao gồm provider HTTP fixtures, source/citation distinctions, no-search/zero/missing/refusal, Unicode/multi-output/calls, unsafe/private URLs,400/401/403/429/500, timeout/reset/oversize/invalid JSON, missing prices/usage, shared budget, stale config/prompt/model/key, credential pin, concurrent confirmation, recovery, ingestion failure, ownership ambiguity và QA. Frontend dùng provider/API mocks, không live account; test consent/running/result/reload, no-search/error, citation/source/QA/GEO và mobile. Regression toàn bộ Dashboard/GSC/Technical/Tracking/Research/AI/SIWC/Visibility Core vẫn pass.

Sau backend guards cuối, **12/12 focused Visibility Core + live UI Playwright pass** trên backend đang chạy.

Kiểm tra bổ sung trên source cuối: **1/1 provider fixture → observation → GEO → existing offline Agent → human review smoke passed**; không phát sinh inference trả phí hoặc usage ledger trùng.

Một warning Starlette/httpx deprecation giống baseline. Không có failure/skip còn tồn tại ở các suite được báo. Windows native vault/runtime, actual OpenAI eligibility/model/billing/privacy terms, real citation offsets/source content và live quality chưa thực thi xác minh trong môi trường này.

Commands:

```bash
cd backend
.venv/bin/python -m pytest -q
cd ..
npm --prefix frontend run build
node --test scripts/tests/frontend.test.mjs
backend/.venv/bin/python scripts/evaluate_live_visibility.py
cd frontend
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e
```

## I. Live verification

**Pending Live Verification**. Không có real paid request được cấp phép/chạy. Không yêu cầu secrets trong chat. Cấu hình và xác minh ba lượt đơn trên localhost theo [hướng dẫn](GEO_LIVE_VERIFICATION.md); xác nhận chi phí từng lượt. Implementation/mock success không chứng minh account access, giá hoặc nguồn citation đúng.

## J. Pending items / limitations

Docs/pricing live inaccessible; SDK schema verified nhưng model/tool/account entitlement cần kiểm chứng. Unknown costs/reservations không là provider-side cap. URL annotation không là factual/source-content verification. Inline span mapping chưa được verify nên dùng references. Có bounded response/metadata/storage/context limits; vượt giới hạn giữ failure/diagnostic thay vì giả completed result. store=false không bảo đảm zero retention hoặc retrieve được response; cần kiểm tra điều khoản/provider data policy hiện hành trước gửi nội dung nhạy cảm. Chưa có retention scheduler, recovery fetch hoặc auto monitoring. Gemini/Perplexity và automation ngoài scope.

## K. Single next phase

Sau khi nghiệm thu OpenAI live và xác nhận scope riêng, đề xuất duy nhất **v0.8.2 — Gemini Grounding adapter** với cùng consent/cost/provenance/QA contract. Chưa triển khai provider đó trong lượt này. Trước release tiếp theo, hoàn thành current localhost live verification thay vì tuyên bố OpenAI đã chạy thật từ mocks.
