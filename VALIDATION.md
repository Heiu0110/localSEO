# Sửa callback/Windows Vault ChatGPT · 30/10/2026

Ảnh người dùng cho thấy callback localhost trả lỗi chung; nút làm mới chưa giúp xác định nguyên nhân. Chưa có mã lỗi của lần live đó nên không gán nguyên nhân chắc chắn cho tài khoản người dùng.

| Kiểm tra thực thi | Kết quả |
|---|---|
| Toàn bộ backend pytest | **271 passed**: 254 cũ + 9 OAuth/diagnostic + 8 OS-vault storage cases; một cảnh báo Starlette/httpx giống baseline |
| AI Workspace + ChatGPT Playwright | **18 passed**: thêm manual-refresh feedback và failure-stage/retry UI; các test khác của module SEO không chạy lại trong lượt này |
| TypeScript/Vite production build | **Passed**, không thêm dependency hoặc đổi lockfile |
| Windows credential-size contract | Mô phỏng giới hạn2560byte UTF-16: cách ghi một blob cũ bị từ chối; token dài chia phần roundtrip, refresh ghi lỗi giữ bộ cũ, legacy read, thiếu/sai checksum bị chặn, Disconnect quét cả slot và phần dư |
| OAuth error diagnostics | Missing issued client, invalid grant/client/request/scope và lỗi không biết được phân loại an toàn; không echo provider description/code/token; state/PKCE/JWT validations giữ nguyên |
| Restart | Metadata chỉ chứa mã lỗi/tên bước; đọc lại lỗi sau restart, pending OAuth bị hủy có thông báo bắt đầu lượt mới |
| Callback browser smoke | Chromium mở **listener thật với mock issuer**, lỗi đăng ký động hiển thị mã/bước, History API loại query khỏi URL, không pageerror; capture1100×800 và390×844 tại `/tmp/localSEO-callback-diagnostic{,-mobile}.png` |

Không dùng authorization code trong ảnh, không đăng nhập OpenAI thật hoặc thực hiện inference. Windows Credential Manager native, eligibility và live OAuth vẫn **Pending Live Verification**; bộ giả lập giới hạn kích thước không thay thế xác minh trên máy cá nhân. Dashboard/module SEO không đổi; SQLite không migrate/reset. Xem [hướng dẫn thử lại](docs/CHATGPT_CONNECTION_SETUP.md#callback-báo-chưa-hoàn-tất-hoặc-nút-làm-mới-không-có-kết-quả).

# SIWC — Sign in with ChatGPT validation · 29/10/2026

Bổ sung duy nhất OAuth/Plan Usage và các phụ thuộc trực tiếp vào AI Workspace. Baseline `fef7068`: đã chạy **207 backend tests, 12 AI browser tests và production build passed** trước thay đổi; 68 browser tests trước đó là kết quả Phase7 được lưu trong lịch sử.

| Kiểm tra thực thi trong lượt SIWC | Kết quả |
|---|---|
| Toàn bộ backend pytest | **254 passed**: 207 cũ + 47 SIWC cases; không failed/skipped/xfail |
| Toàn bộ Playwright production preview | **72 passed**: 68 cũ + 4 SIWC UI tests, không failed/skipped |
| TypeScript/Vite build | **Passed**, AI route tải riêng khoảng39,9KB; không thêm dependencies |
| Launcher tests | **17 passed** trên Linux; launcher thực dùng lại node_modules, chuẩn bị0,0s |
| Dependency/persistence | requirements/package lock không đổi; pip check không broken requirements; schema vẫn005, integrity_check=ok, FK không lỗi |
| OAuth | Dynamic client/host UUID, PKCE S256/state/nonce, listener hoạt động trước URL, callback thật qua loopback với mock issuer, issued ID exchange/reuse, expiry/replay/denial/missing client/invalid state |
| OIDC | RSA keys tạo trong tests, RS256 signature/issuer/audience/azp/exp/nbf/sub/nonce; từ chối invalid JWT/discovery/JWKS URI, redirect và token header injection |
| Permission/lifecycle | Missing direct scope hoặc không có initial granted scopes: connected_not_authorized, không lấy models/inference; refresh rotation single-flight, revoked/expired/changed subject/scope removal và disconnect/revocation |
| Host identity | Cùng OS Vault giữ UUID ổn định; dùng SQLite cũ với Vault khác tạo host identity mới, không clone máy qua database backup |
| Models | visibility=list/display_name/slug; không default API model; hidden/unknown/removed model bị chặn; model/session thay sau consent chặn queued inference |
| SSE/inference | Payload allowlist store=false/stream=true/input array; không forward unsupported API-key fields; function-tool roundtrip; delta/UTF-8 chunk fragmentation/completed/incomplete/failed/EOF/size cap; lỗi401/403/429/503 trước và sau mở stream |
| No paid fallback | Mock API-key factory không được gọi khi SIWC lỗi/quota; UI giữ mode chatgpt; USD=null, token usage thuộc provider chatgpt, không cộng hạn mức ChatGPT vào API-key dollar budget |
| UI | Continue button/review/local-browser check, popup/link fallback (mock), account/no-permission state, model picker/save, per-turn consent, quota error và mobile390; key/token không có input trên frontend |
| Regression | Dashboard/GSC/Technical/Keyword Tracking/Research/AI history/evidence/review và startup cùng suite cũ; không sửa code source SEO, OAuth Google hoặc database migrations |

Đã xem ảnh thực tế AI Settings1440×1100 và390×1100, không horizontal overflow/pageerror. Trạng thái thật trong cloud: chưa kết nối, OS Credential Vault chưa khả dụng; ảnh không giả lập tài khoản đã login. AIUsage trong workspace vẫn0, không có inference thật hoặc paid API request. Browser tests có mocking cho trạng thái connected, code callback và model/quota UI; backend dùng MemoryVault chỉ trong tests, không thêm plaintext fallback vào runtime.

Một lượt browser có71passed/1failed do selector dùng nhãn API Provider cũ sau khi đổi thành “OpenAI API Key Provider”; đã cập nhật đúng nhãn mới và thông báo empty usage, giữ nguyên assertions. Lượt cuối **72/72passed**. Không tắt test/SSL/signature assertions để qua kiểm tra. Cảnh báo Starlette TestClient/httpx và NO_COLOR/FORCE_COLOR giống baseline.

**Pending Live Verification:** LocalSEO OSS/locally hosted eligibility và license, dynamic registration thật (chưa có issued ID/redirect đã xác minh), OAuth/permission/models/inference/hạn mức thật, Windows Credential Manager và native Windows. Không thêm LICENSE hoặc mặc định public repo đủ điều kiện. Contract theo official handoff người dùng cung cấp ngày29/10/2026; cả4trang chính thức vẫn Tunnel403 nên full Preview Limitations chưa được đối chiếu độc lập. Chỉ triển khai subset fail-closed (RS256, HTTP SSE, local function tools); không giả lập quota balance/model availability live. Xem [các bước kiểm chứng localhost](docs/CHATGPT_CONNECTION_SETUP.md). Dừng ở tính năng này.

# Validation evidence · v0.7 / Phase 7 Core

## Phase 7 Core — ngày 29/10/2026

Baseline thực thi tại `70a4efb`: **170 backend, 58 Playwright, production build passed**. Đã kiểm tra head004 và backup SQLite trước migration005. Thay đổi giữ Mock/SQLite Analytics/OAuth/crawler/weekly Tracking/AI provider; Research không thêm dependencies hoặc request provider live.

| Kiểm tra thực thi | Kết quả |
|---|---|
| Backend pytest toàn bộ | **207 passed**: 170 cũ + 37 Research tests, không failed/skipped/xfail |
| TypeScript + Vite production build | **Passed**, Research route tải riêng khoảng46,3KB (gzip12,1KB) |
| Playwright production preview toàn bộ | **68 passed**: 58 cũ + 10 Research, không failed/skipped |
| Launcher tests | **17 passed**; launcher thực chuẩn bị0,0s, dependency không đổi và bỏ npm ci |
| Dependencies | Không thêm dependency; lock ngoài root app version giống baseline; pip check không lỗi dependency |
| Migration workspace | Nâng004→005, đối chiếu **toàn bộ giá trị 31 bảng cũ** ngay sau migrate: không bảng nào đổi; integrity_check=ok, FK không lỗi |
| Migration/restore test | DB tạm từ004 có GSC facts và AI conversation: migrate hai lần giữ bảng cũ, backup bằng SQLite và đọc lại đúng dữ liệu/integrity |
| Source integrations | Seed Unicode/NFC/duplicate/locale; demo và SQLite GSC fixture; Tracking import; Technical crawl fixture, không gọi domain thật |
| Data integrity | CTR percent→ratio đúng; impressions không phải volume; paid competition/difficulty có unit/scale; missing values không thành0; GSC observation cùng kỳ/scope |
| Clustering | Manual primary/move/split/merge/delete/review; lexical factors draft; SERP overlap1 và1/3 theo URL; thiếu dữ liệu unavailable |
| SERP | JSON/CSV/XLSX imports; immutable/dedup; depth/completeness; paid/organic khác nhau; từ chối so profile khác; nhiều URL/domain đếm1 lần/SERP |
| Tracking transfer | Approved-only, cùng website, separate preview/confirm, stale preview bị chặn, retry cùng job idempotent, skip duplicates cả trong lựa chọn khác locale; không ghi rank |
| Agent/security | 7 tools mới scope theo conversation; extra SQL/project args bị chặn; snippets là untrusted data; giả reference Tracking khác website không đọc được dữ liệu nguồn; CSRF/Origin, malformed files/formulas/units bị chặn; SERP URLs không fetch |
| UI | Tạo project, seed/GSC preview với đủ metrics/action, keyword edits/history, cluster review, opportunity review, SERP/profile/compare/cohorts, confirmed transfer và JSON download; responsive1366/768/390 |

Đã xem screenshot thực tế ở1440×1000 và390×1000, không pageerror hoặc page overflow. Sửa select project trên mobile để nằm trong card; bảng rộng cuộn bên trong. Bản xem trước render từng object để không che metrics/action do giới hạn8cột của renderer dùng chung. Tests dùng dữ liệu có tên E2E/fixture, không có paid API calls.

Google Ads/SERP API/Trends adapters live **chưa triển khai/kết nối** trong Core, không chỉ là một checkbox credentials còn thiếu. OpenAI/keyring Windows/Google OAuth live vẫn **Pending Live Verification** theo các phase trước. Native Windows chưa được chạy trong cloud; đã kiểm tra README/launcher args và scripts chung. Không claim current pricing, thị phần/traffic đối thủ hoặc rank Google live. AI clustering nâng cao, Topical Map, scheduler và Phase8–11 chưa triển khai. Một cảnh báo deprecation Starlette/httpx và NO_COLOR/FORCE_COLOR vẫn giống baseline, không có test bị tắt để vượt qua.


## Phase 6 — kiểm tra ngày 29/10/2026

Baseline tại `777e2a8`: **130 pytest, 46 Playwright, 17 launcher tests và production build passed**. Repo có GSC, Technical SEO, Keyword Tracking; Topical Map chỉ là placeholder. Đã backup trước migration; không viết lại các provider/crawler đã ổn định.

| Kiểm tra thực thi | Kết quả |
|---|---|
| `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q` | **170 passed**: 130 cũ + 40 Agent tests, không failed/skipped/xfail |
| `node --test scripts/tests/frontend.test.mjs` | **17 passed**, dependency không đổi vẫn bỏ npm ci |
| `npm --prefix frontend run build` | **Passed** TypeScript + Vite; AI Workspace thành chunk riêng khoảng32,8KB |
| Toàn bộ Playwright trên production preview | **58 passed**, không failed/skipped: 12 AI + 18 Dashboard + 8 GSC + 10 Keyword + 10 Technical |
| AI UI | Tạo phiên/chọn website, context missing Topical Map, báo cáo thật từ demo/services, evidence/table/card, history/reload, review và ghi chú, đổi website/kỳ, offline, settings không có key input, provider error mock, usage, responsive |
| UI race/scroll | Estimate không mất khi vừa tạo phiên; retry dùng idempotency key; mở hội thoại dài chỉ cuộn trong chat, không nhảy trang trên mobile |
| Agent security | Tool/SQL/shell/file/external research allowlist, input/output schema, ownership, giới hạn tool/result/time, citation giả, key redaction, CSRF/Origin và validation không echo secret |
| Prompt injection | Title crawl chứa chỉ dẫn độc hại được truyền như dữ liệu tới provider mock; model mô phỏng yêu cầu SQL bị registry từ chối, bảng SEO giữ nguyên |
| Review chỉ đọc | Đối chiếu **toàn bộ giá trị** các bảng SEO trong DB fixture trước/sau phân tích và review, không chỉ đếm dòng; không có execution hook |
| GSC preservation workspace | **777 fact rows**, hash khóa+metric values trước/sau `a783d31370b2f749` khớp; không tính fetched_at được fixture sync lại có chủ ý |
| SQLite | Schema `004_ai_agent`; integrity_check=ok, foreign_key_check không lỗi; 6 bảng Agent thêm vào, không reset SEO data |
| Provider/cost tests | Mock Responses/tool calling, token usage, ước tính/dự phòng/ngân sách, unknown usage khi lỗi, không replay, disable/model change, xóa phiên vẫn giữ usage; xác nhận gắn với model/trần chi phí, đổi giá giữa lượt chặn request tiếp |
| Dependencies | `pip check`: No broken requirements; không thêm dependency frontend/backend |

Ảnh giao diện thực tế đã kiểm tra ở1440×1000 và390×1000; không overflow trang hoặc pageerror. Bản mới giữ các token nâu–kem hiện tại. Sau sửa auto-scroll, scrollY khi mở hội thoại có dữ liệu là0 ở cả hai viewport. Fixtures browser có tên phiên/test rõ ràng; không có paid AI calls trong bộ tests.

Model ID `gpt-4.1-mini` và Responses/function tool contract được đối chiếu SDK chính thức trên GitHub. Trang model/pricing trực tiếp bị tunnel403; **giá hiện hành chưa được xác minh**, không gán mức giá mặc định. Giá trong app là user estimate; model/account/key/capabilities và Windows keyring/OpenAI live còn **Pending Credentials / Pending Live Verification**. Tests OpenAI HTTP dùng httpx.MockTransport; không khẳng định paid API thành công.

Topical Map, External Research, URL Inspection, Server Logs và Phases7–11 chưa triển khai. AI semantic hallucination vẫn có thể xảy ra: citation validation không chứng minh diễn giải đúng. Metric cards từ backend; AI chỉ là diễn giải/giả thuyết, cần human review. Tool timeout không giết SQL thread đang chạy; HTTP đã gửi có thể vẫn hoàn tất/tính phí. Xem7tài liệu AI để biết giới hạn.

## Sửa launcher frontend — 22/10/2026

Ảnh Windows người dùng cho thấy npm cài171gói mất9phút, chuẩn bị551,4giây, trong khi Vite ready263ms. Điều này xác định bước chậm là cài dependency; ảnh không đủ kết luận riêng tốc độ mạng hay antivirus/ổ đĩa.

Đã tìm thấy lỗi tái cài không cần thiết: v0.3→v0.4 chỉ đổi app version trong lockfile nhưng SHA toàn file thay đổi, launcher cũ vẫn gọi npm ci. Chữ ký dependency mới xác nhận hai release này cùng dependency. Bản cài cũ/`npm ci` trực tiếp được đối chiếu hidden lock, file package/version và kiểm tra native một lần trước khi dùng lại. Không thay lockfile hoặc thêm thư viện.

| Kiểm tra thực thi cho bản sửa launcher | Kết quả |
|---|---|
| `node --test scripts/tests/frontend.test.mjs` | **17 passed**, không failed/skipped trên Linux |
| Dùng lại node_modules hiện có từ launcher cũ | Kiểm tra native ngoại tuyến thành công trong **0,3s**, không gọi npm ci |
| Registry giả không truy cập được: `npm_config_registry=http://127.0.0.1:9 node scripts/frontend.mjs` | **Passed**, chuẩn bị **0,0s**, bỏ npm hoàn toàn |
| Cài sạch trong thư mục tạm có khoảng trắng, cache đầy đủ, npm offline=true | npm ci thực cài174packages + native probe **3.899ms**; chạy tiếp dùng lại bản cài |
| Launcher thực `node scripts/frontend.mjs --run` | Chuẩn bị **0,0s**, Vite ready **162ms**, HTTP5173 hoạt động |
| Process timeout và Ctrl+C | Dừng process thực, trả124/130; không đánh dấu cài thành công, giải phóng install lock |
| Windows process termination | Test kiểm tra taskkill.exe/PID/T/F, shell=false; chưa chạy native Windows |
| `npm --prefix frontend run build` | **Passed** TypeScript + Vite, artifacts UI không đổi |
| Browser smoke sau khởi động bằng launcher mới | **2 passed**: Dashboard API→UI 28ngày và Keyword Tracking 1366px |

Tests còn kiểm tra phiên bản app/JSON formatting không gây npm ci, thiếu dependency bắt buộc/sai version không bị bỏ qua, lifecycle/override/Node ABI, sửa bản cài có chủ ý, khóa concurrent và phục hồi khóa cũ. HTTP logs được bật; mặc định request60giây/retry1, toàn lượt180giây; `--install-timeout=600` cho toàn lượt600giây/request120giây. Giữ TLS/integrity và chính sách install scripts của npm.

Số đo là môi trường Linux/Python/Node cloud hiện tại, **không cam kết thời gian tải lần đầu trên Windows**. Cài mới/cache thiếu vẫn phụ thuộc mạng/ổ đĩa. Không thay code giao diện/backend hoặc dữ liệu SQLite; không chạy lại toàn bộ 130 backend và 46 browser vì không có thay đổi liên quan.

## v0.4 — kiểm tra ngày 22/10/2026

Baseline trước thay đổi tại `6bd141b`: **92 backend tests và 36 Playwright tests passed**. Đã sao lưu SQLite trước migration003. Không đổi mã nguồn MockProvider/DashboardService hoặc cơ chế OAuth/token.

| Kiểm tra | Kết quả thực tế |
|---|---|
| Backend `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q` | **130 passed**, không failed/skipped/xfail; gồm 38 test mới |
| `backend/.venv/bin/python -m pip check` | No broken requirements found |
| Frontend `npm run build` (TypeScript + Vite) | **Passed**; route Keyword Tracking thành chunk riêng |
| Toàn bộ Playwright trên production preview | **46 passed**, không failed/skipped; 18 Dashboard + 8 GSC + 10 Keyword + 10 Technical |
| Keyword browser workflow | Tạo bộ/nhóm/keyword, ghi rank/NA/clear/validation, lịch sử, bàn phím Tab, filter/sort/bulk, paste preview, CSV/XLSX export, CSV import lỗi, GSC fixture worker và scope, responsive |
| Grid nhiều dòng | 60 keyword lưu thật, trang25/50/10dòng; đo vị trí6cột khi cuộn ngang và header khi cuộn dọc, đều giữ đúng |
| Migration v0.3→v0.4 | Test nâng từ002, bảo toàn GSC fact values, migrate lại idempotent, FK/integrity hợp lệ |
| SQLite workspace | **518 GSC facts**, hash key+metric values trước/sau **3d72eb75e463ad84** khớp; integrity_check=ok, foreign_key_check không lỗi |
| Rank | 1/100, NA, Not Checked, 0/âm/thập phân/range lỗi; append history/clear, timezone boundary, calendar lock, profile/target changes, missing previous week, chuyển bộ không gộp profile riêng |
| GSC keyword | Equals query/page filters, byProperty/byPage, no rows, cache identity/TTL/reuse, weighted daily cache, thiếu coverage, permission failure giữ cache, recovery và không tạo job trùng |
| Import/export | CSV và XLSX roundtrip tiếng Việt,35tuần/NA/blank, custom mapping, skip/update/separate model, transaction, formula text, zip/upload limits |
| Kiểm tra ảnh thực tế | Desktop1440×1000 và mobile390×1000: không overflow trang/không pageerror; bảng, overview, drawer giữ token nâu–kem |

Dữ liệu browser tests là dữ liệu thử nghiệm có tên bộ rõ ràng và website demo/fixture; không có kết quả rank tự động được bịa cho property thật. Request Google trong tests dùng fixture/mock, không dùng credentials thật. Không khẳng định native Windows, keyring/OAuth live, exact-query live hoặc SERP tự động đã được xác minh. Screenshot evidence, lịch chạy định kỳ và SERP provider chưa triển khai.

Một cảnh báo deprecation Starlette TestClient/httpx vẫn xuất hiện như baseline; không có test lỗi. Core giữ giới hạn an toàn:100KiB/1.000dòng import,500ô batch rank,200keyword batch metadata,5.000keyword/sync hoặc export. Chưa benchmark dataset hàng triệu observation.

## v0.3 — kiểm tra ngày 22/10/2026

Baseline trước thay đổi tại `5188164`: **45 backend tests, 26 Playwright tests và production build đều passed**. Đã tạo backup SQLite trước migration. Thay đổi bổ sung module Technical SEO, giữ MockProvider và DashboardService không đổi mã nguồn.

| Kiểm tra | Kết quả thực tế |
|---|---|
| Backend `.venv/bin/python -m pytest -q` | **92 passed**, không failed/skipped/xfail |
| Backend `.venv/bin/python -m pip check` | No broken requirements found |
| Frontend `npm run build` (TypeScript + Vite) | **Passed** |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e` | **36 passed** trên production preview, không failed/skipped |
| Technical SEO browser suite riêng | **10 passed**; workflow chính dùng crawler/parser/DB thật với HTTP fixture ngoại tuyến |
| Startup helpers và Alembic | Thành công; health `hybrid / 0.3.0`, schema `002_technical_audits` |
| Frontend bootstrap sau version lock change | Cài từ cache 174 packages, lần sau bỏ qua install |
| SQLite integrity / foreign keys | integrity_check = ok; foreign_key_check không lỗi |
| GSC preservation | 518 fact rows trước/sau; hash toàn bộ khóa và metric values khớp, không tính fetched_at được sync lại có chủ ý |
| Mock report | 28-day clicks xuong-may vẫn **44.499** |
| Website production thật, Windows native, Google credentials thật | **Not executed**; không dùng các kiểm thử này để tuyên bố đã xác minh môi trường máy cá nhân |

Backend thêm 47 kiểm thử (kể cả parametrized cases): normalization/trailing slash/query/scope; credentials/private/metadata/action URL rejection; DNS pinning/mixed public-private/rebinding và IPv6 transition rejection; redirect chain/loop/external/robots guard; timeout/rate/cancel/Retry-After/host stop; gzip input/output limits, slow trickle deadline; robots group precedence/wildcards/unknown; extraction/canonical headers/robots/headings/breadcrumb; XML/index/entities/gzip cap/lastmod; indexability states; real graph depth/orphan candidate; persisted history, new/persistent/resolved/reopened findings; incomplete/robots-blocked dependencies không bị xác nhận resolved; checkpoint recovery/cancel/duplicate jobs; SQL paging/sort/search validation; import preview/commit; export formula/XSS defenses; retention; GSC page exposure không cần OAuth; migration 001→002 giữ dữ liệu GSC; Dashboard summary matching và unknown graph values trước finalization.

36 browser tests gồm 18 Dashboard, 8 GSC và 10 Technical SEO. Technical tests thực hiện tạo fixture project, chạy worker, xem tiến độ, URL detail/sort/search/filter, issue evidence, backlog notes/status, recrawl, comparison, CSV/JSON/HTML exports, sitemap/link tables, CSV preview/commit, custom limits/partial comparison, unsafe URL rejection và responsive 1366/768/390 px. **Một test nút hủy UI dùng mock running/cancelled job** để tránh fixture hoàn tất quá nhanh; cancellation backend thật được kiểm tra riêng. URL Inspection và Google OAuth error states dùng giả lập như v0.2; không tiêu tốn quota Google.

Lượt regression đầu phát hiện race ở GSC: UI có thể còn thẻ completed của job cũ khi start job mới. Đã sửa pending state, cập nhật jobs cache ngay bằng response và hủy stale read; test bám đúng job ID. Sau sửa, toàn bộ 36 tests trên production passed; không bỏ assertions hoặc skip test để đạt kết quả.

Đã chụp/xem giao diện nội bộ: `/tmp/seo-v03-technical-overview.png`, `/tmp/seo-v03-technical-issues.png`, `/tmp/seo-v03-technical-evidence.png`, `/tmp/seo-v03-technical-mobile.png`, `/tmp/seo-v03-dashboard.png`. Desktop 1440×1080 và mobile 390×844, density 1; kiểm tra overflow và browser pageerrors. Không tạo PDF/presentation/UI review artifact riêng. Theme kem–be–nâu đồng và Dashboard giữ nguyên bố cục; chỉ hiện thẻ technical summary khi có audit live khớp website.

Môi trường Linux Python 3.12 / Node 24 / Chromium 154 và dependency locks hiện có. Có cảnh báo deprecation Starlette TestClient về httpx và cảnh báo màu terminal NO_COLOR/FORCE_COLOR; không phải failed assertions. Không tắt TLS, package integrity, SSRF hoặc robots guards.

Phạm vi giao: **v0.3 Core**, 39 rule sinh finding trong 63 automated capabilities (gồm signals/workflows), catalog 138 checks có capability và trạng thái dữ liệu riêng. Không tuyên bố hoàn tất v0.3.1–v0.3.3. Xem sáu tài liệu Technical SEO trong docs/ cho kiến trúc, crawler, rule catalog, data model, hướng dẫn và giới hạn.

## Lịch sử v0.2

Các mục bên dưới ghi nhận những lượt xác minh trước khi triển khai Technical SEO.

Chạy trong workspace Linux ngày **21/10/2026**, trên repository hiện có. Trước khi thay đổi, baseline v0.1 tại `f7a0a25` đạt **28 backend tests, 18 browser tests và production build**. Mock Provider và DashboardService v0.1 được giữ nguyên mã nguồn. Dashboard tiếp tục dùng giao diện tiếng Việt và bảng màu đã thống nhất.

## Kết quả v0.2

### Bảng màu theo ảnh tham chiếu (21/10/2026)

Chỉ thay CSS tokens, favicon và browser theme-color: kem/be/nâu đồng/espresso trên Dashboard, Settings và GSC Analytics. Không sửa layout, frontend logic hoặc backend. Đã chạy `npm run build` thành công và toàn bộ **26 Playwright tests passed** trên dev server; đã xem browser screenshots desktop/mobile và focus state. Những cặp chữ chính đã kiểm tra đạt tương phản tối thiểu 4,5:1. Chi tiết phạm vi và ảnh nội bộ trong [design-qa.md](design-qa.md). Backend tests không chạy lại trong lần đổi màu này.

### Cập nhật tốc độ và log khởi động frontend (21/10/2026)

Đã thay npm wrapper ở bước chạy dev bằng gọi Vite trực tiếp qua Node; giữ điều kiện bỏ qua cài đặt khi fingerprint lockfile khớp. Khi cần cài, npm ưu tiên cache, bỏ network audit ở startup và in trạng thái mỗi 15 giây; không thay đổi TLS/integrity. npm CLI được gọi trực tiếp qua Node để hỗ trợ đường dẫn có khoảng trắng, không qua shell Windows.

Xác minh thực tế trên Linux: `node --check scripts/frontend.mjs` đạt; bootstrap với dependencies có sẵn báo chuẩn bị 0,0 giây và Vite Ready sau 172 ms. Cài sạch 174 packages trong thư mục tạm có khoảng trắng, dùng cache và bật npm offline, đạt sau 3,7 giây; chạy lại bỏ qua install. Cố ý tạo dependency không có trong offline cache: script trả exit 1 và không ghi stamp thành công. Gửi SIGINT tới launcher đã dừng cả launcher và Vite child. Hai browser regression tests cho navigation/chart và offline runtime đạt **2/2**. Không chạy lại toàn bộ backend/browser suite vì thay đổi chỉ ở launcher và tài liệu; kết quả đầy đủ v0.2 bên dưới là lượt xác minh trước đó. Chưa đo thời gian hoặc chạy launcher trên Windows thật; số đo Linux không phải cam kết tốc độ máy người dùng.

| Kiểm tra | Kết quả thực tế |
|---|---|
| Backend: `.venv/bin/python -m pytest -q` | **45 passed**, không failed/skipped/xfail |
| Backend: `.venv/bin/python -m pip check` | No broken requirements found |
| Frontend: `npm run build` | **Passed**, bao gồm TypeScript và Vite production build |
| Frontend: `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e` | **26 passed** trên production preview, không failed/skipped; suite cũng đã đạt 26/26 trên dev server |
| Bootstrap `python scripts/backend.py`, migration CLI, `node scripts/frontend.mjs` | Thành công; chạy lại dùng dependencies đã cài khi fingerprint không đổi |
| SQLite backup script | Backup cả dữ liệu trong WAL, integrity check thành công, từ chối ghi đè file đích |
| Live OAuth / Google API với tài khoản thật | **Not executed — Pending Live Verification** |
| Windows `.bat` và Windows Credential Manager trên máy thật | **Not executed — Pending Live Verification** |

Backend tests dùng SQLite tạm riêng và test-only MemoryVault, không đọc credentials thật. Bao phủ migrations/WAL/foreign keys/persistence; property identifiers và chống trùng; sync idempotent/initial/incremental/resume/refresh/cancel/recovery; rollback giữa trang; phân trang 25.000 và giới hạn 50.000; retry/quota/timeout; Google SDK request shape; PKCE/state một lần; token refresh/revoke giả lập; chống ghi token vào SQLite; từ chối plaintext keyring; CSRF/origin; upload cấu hình Desktop JSON; server search/sort/pagination; CSV và backup. KPI được đối chiếu với site facts độc lập, không bằng tổng queries; kiểm tra CTR/weighted position, search type, khoảng thiếu và không dựng mức giảm 100% từ detail row vắng mặt.

Browser suite giữ toàn bộ 18 regression tests cũ và thêm 8 tests: tạo property thử nghiệm SQLite, đồng bộ 14 ngày với tiến độ thực, đổi Mock/SQLite mà không lẫn KPI, 5 tab analytics, server pagination/search/sort, page detail, bốn CSV exports, cached reports khi chặn mạng ngoài loopback, thiếu kỳ so sánh, lỗi OAuth/reauthorization qua API giả lập và responsive. Kiểm tra overflow ở 1366/1024/768/390 px; đã xem screenshot nội bộ Dashboard, Settings, Analytics để kiểm tra sự nhất quán. Không tạo tài liệu review giao diện riêng.

Trong lượt kiểm tra cuối, một selector test khớp cả link sidebar và link trong nội dung; đã giới hạn vào navigation. Một lượt điều hướng bị gián đoạn vì build lại thư mục production đồng thời với tests; đã chạy lại suite sau khi build kết thúc. Kết quả cuối **26/26 passed**, không còn test failed hoặc skipped. Không vô hiệu hóa assertions, TLS hoặc package integrity để đạt kết quả.

Môi trường giữ Python 3.12.14 / Node 24.19.0 / npm 11.9.0 / Chromium 154 / Playwright 1.64.1 và stack v0.1. Dependencies bổ sung đã khóa trong `backend/requirements.txt`. Có một cảnh báo deprecation Starlette TestClient về httpx và cảnh báo màu terminal NO_COLOR/FORCE_COLOR; không có assertion thất bại.

## Phạm vi chưa xác minh

- Cloud headless hiện không có OS keyring phù hợp. Status API trả trạng thái rõ ràng; Demo, SQLite fixture, cached data và các tests vẫn hoạt động. Không thêm fallback token plaintext.
- Chưa dùng Google account/property thật, chưa kiểm tra consent/refresh/revoke/quota thật. Cần chạy luồng trong [Google setup](docs/GOOGLE_GSC_SETUP.md) trên máy cá nhân; không sử dụng ADC của môi trường cloud.
- Chưa chạy native Windows hoặc kiểm tra restore snapshot môi trường trong task mới. Bootstrap Python/Node dùng chung đã chạy trên Linux.
- Giới hạn có chủ ý: một kết nối Google active, một sync worker, bốn search types `web/image/video/news`, chưa có dataset quan hệ query–page. Google có thể giới hạn/ẩn detail rows dù đã phân trang; CSV chỉ xuất dữ liệu đã lưu.
- Đã cập nhật và lưu draft `install_script` / `start_skill` cho v0.2. **Chưa publish** snapshot. Để tái sử dụng cấu hình này, mở Environment settings, review/save rồi Publish; đây không phải triển khai ứng dụng lên cloud.

## Lịch sử xác minh v0.1

Các kết quả bên dưới ghi nhận phiên bản trước khi bổ sung GSC/SQLite, không mô tả phạm vi hiện tại của v0.2.

## Cập nhật giao diện tiếng Việt và bảng màu

Đã chạy lại `npm run build` (bao gồm TypeScript) và toàn bộ **18 Playwright tests: 18 passed**, không skipped/failed. Test tương tác dùng nhãn tiếng Việt và đối chiếu KPI với API theo định dạng `vi-VN`; CSV tiếp tục xuất đủ dữ liệu khớp bộ lọc với tiêu đề tiếng Việt. Đã kiểm tra bố cục ở 1366/1024/768/390 px và xem giao diện desktop/màn hình hẹp. Phát hiện và sửa việc Radix Tooltip chuyển callback `className` của NavLink thành chuỗi khi sidebar thu gọn; test kiểm tra nhãn ẩn và active class sau khi thu gọn.

Màu được quản lý tập trung bằng CSS variables: nền trắng/xám, đường nét bạc, nhấn vàng đậm, nâu đất và sidebar nâu sẫm. Backend/API contracts và mock dataset không thay đổi trong lần cập nhật này.

Chạy thực tế trong workspace Linux ngày 21/10/2026. Không suy diễn rằng đã chạy trên Windows hoặc đã publish/restore môi trường mới.

## Môi trường

- Python 3.12.14, Node.js 24.19.0, npm 11.9.0.
- Chromium 154.0.8037.57, Playwright 1.64.1, headless.
- React 19.3.1, React Router 7.18.4, Vite 7.3.7, TypeScript 5.9.3.
- Tailwind CSS 4.3.3, TanStack Query 5.104.5, Recharts 3.10.1.
- FastAPI 0.156.4, Pydantic 2.14.1, Uvicorn 0.54.0.
- Phiên bản đầy đủ được khóa trong package-lock.json và backend/requirements.txt.

## Kết quả

| Kiểm tra | Kết quả thực tế |
|---|---|
| `.venv/bin/python -m pytest -q` (cwd backend) | **28 passed**, không failed/skipped/xfail |
| `.venv/bin/python -m pip check` (cwd backend) | No broken requirements found |
| `npm run typecheck` (cwd frontend) | Passed |
| `npm run build` (cwd frontend; bao gồm typecheck) | Passed, Vite build production thành công |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e` (cwd frontend) | **18 passed** trên bản production qua `npm run preview`, không failed/skipped |
| Browser suite trên dev server trước khi thêm offline docs test | **17 passed** |
| `npm audit --omit=dev` | 0 vulnerabilities ở dependency production tại thời điểm kiểm tra |
| `python scripts/backend.py`, `node scripts/frontend.mjs` | Cài dependencies thành công, chạy lại bỏ qua cài đặt; fingerprint khớp requirements/lockfile |
| Backend qua `python scripts/backend.py --run --no-reload` | Khởi động và phục vụ health/sites/overview/docs thành công |
| Frontend qua `node scripts/frontend.mjs --run` | Khởi động Vite tại port 5173, proxy API hoạt động |

Backend tests kiểm tra CTR và weighted position bằng ví dụ tính tay; zero baseline; fixture tái lập 200 ngày; 2 websites × 7/28/90 ngày; partition sums theo daily/pages/queries/countries; equal-length, contiguous previous period; page detail/related-query reconciliation; 404, 422, CORS; local API documentation assets.

Browser tests thực hiện thao tác chọn website/ngày và đối chiếu cả 4 KPI với API cho cả 6 context; đổi chart metric; bật/tắt compare/series; table sort/search/pagination/empty state; chọn query; page details; CSV download chứa mọi dòng khớp bộ lọc; URL navigation/reload và sidebar preference; loading/error/retry/invalid-site recovery. Có kiểm tra CSV escaping/formula injection và số âm.

Responsive assertions tại **1366, 1024, 768, 390 px**: không có horizontal page overflow; bảng rộng cuộn trong container. Đã xem screenshot desktop để kiểm tra bố cục. Không tạo tài liệu ảnh review riêng.

Runtime test chặn mọi destination ngoài loopback: Dashboard vẫn hiển thị và không phát sinh request external. Một test riêng mở `/docs`, tải Swagger UI từ project, thực thi GET health trong Swagger và nhận provider=mock mà không dùng CDN.

Các test đối chiếu UI/API kiểm tra `pageerror` và console error: không phát hiện lỗi. Python test runner có **1 cảnh báo deprecation từ Starlette TestClient về httpx**; chưa phải lỗi runtime, toàn bộ assertions vẫn chạy. Node runner có cảnh báo NO_COLOR/FORCE_COLOR từ cấu hình màu terminal của môi trường. Không tắt kiểm tra TLS, package integrity, assertions hoặc test để đạt kết quả.

## Giới hạn xác minh

- Chưa chạy `.bat` trên Windows thật. Các script dùng launcher mỏng và gọi bootstrap Python/Node dùng chung đã chạy trên Linux; vẫn cần Windows smoke test trước khi phân phối rộng.
- Không có ảnh tham chiếu ngoài mô tả văn bản; không tuyên bố clone pixel-perfect.
- Chỉ mock fixture, không có kết nối GSC/GA4 thật; các module tương lai vẫn placeholder có ghi nhãn.
- Kiểm tra offline dùng browser request interception. Không mô phỏng máy mới chưa có dependencies; cài lần đầu vẫn cần Internet.
- Đã lưu draft `install_script` và `start_skill` cho môi trường hiện tại. Chưa publish snapshot hoặc kiểm tra restore trong task mới; publication là thao tác riêng trong Environment settings.
