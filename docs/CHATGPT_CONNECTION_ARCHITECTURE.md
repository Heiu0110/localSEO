# SIWC adapter trong AI Workspace hiện có

Chỉ thêm một phương thức authentication/inference. Không có Agent mới, GEO, scheduler, automation, thay Dashboard hoặc module SEO. Không thêm dependency: RS256 dùng cryptography đã khóa trong requirements. Không migrate/reset SQLite; dùng app_settings cho metadata công khai và các bảng AI hiện có cho history/usage.

## Luồng

`ChatGPTConnectionPanel → /api/ai/chatgpt → ChatGPTConnection → fixed OpenAI OIDC/OAuth endpoints`

`AIManager → ChatGPTConnection.respond → ChatGPTTransport → /v1/responses SSE → Agent JSON/evidence validation`

Ba lựa chọn tách biệt: local_report, openai (API key), chatgpt (OAuth Plan Usage). Không có nhánh fallback tự động. Model/cost config của API key không bị model picker SIWC ghi đè. Giới hạn context/tool loops chung vẫn được dùng; `max_output_tokens`/giá USD và enabled checkbox của API Key Provider không phải tham số/quyền của SIWC.

## OAuth và bảo vệ callback

- Discovery `https://auth.openai.com/.well-known/openid-configuration`; issuer cố định `https://auth.openai.com`.
- Authorize `/api/accounts/authorize`, token `/api/accounts/oauth/token`, JWKS `/.well-known/jwks.json`, resource `https://api.openai.com/v1`. Discovery phải khớp chính xác; không nhận base_url, issuer, JWKS hoặc redirect URI tùy ý từ frontend.
- Dynamic first login dùng `dynamic_agent_client`, agent_name_hint LocalSEO, host UUID ổn định trong OS Vault (copy SQLite sang host khác không clone định danh máy). Issued client ID phải có dạng oaiapp_, không tự tạo Client ID. Token exchange dùng issued ID.
- Listener IPv4 chỉ bind127.0.0.1, OS chọn port khả dụng, path `/auth/callback`. Listener khởi động trước URL. Check Host/target/path/query, state constant-time, PKCE S256, nonce. Code không ghi log hoặc echo; callback HTML cố định, no-store/CSP/no-referrer. Phiên RAM hết hạn10phút, state tiêu thụ trước exchange.
- ID token kiểm tra RS256 bằng cryptography, chỉ key RSA sig/kid phù hợp, ≥2048bits, không alg none/HMAC/remote jku. Kiểm tra iss/aud/azp/exp/iat/nbf/nonce/sub; leeway cố định60giây cho exp/iat/nbf, không nới các claim định danh. JWKS bỏ qua các phần tử không liên quan không phải object; không chấp nhận hai khóa cùng kid hoặc key_ops không cho verify. Không đọc account từ JWT chưa xác minh. Unsupported signing algorithms bị từ chối.
- Granted scopes từ token response, không từ callback hay scopes đã xin. Initial response không có scope được coi là chưa chứng minh Plan Usage, không giả định scopes đã xin được cấp; refresh không có scope giữ grants đã xác minh trước đó. Chỉ direct grant cho phép model/inference. Refresh có ID token phải giữ subject; không silently đổi tài khoản.

## Storage và vòng đời

OS Credential Vault namespace `ai.chatgpt.tokens.v1` giữ access/refresh tokens, expiry, verified minimal account claims, issued client ID và session generation. `ai.chatgpt.registration.v1` giữ client/account registration sau Disconnect. Không đọc/copy Codex auth hoặc Google credentials. ID token chỉ dùng validation, không lưu raw token. Không có token field trên API/UI, không localStorage/env/file fallback.

SQLite lưu account-bound model listing/cache và selected slug; host UUID giữ trong OS Vault để tách theo máy. Model cache/session generation phải khớp vault session; TTL300giây, model được kiểm tra lại lúc cần. UI chưa có balance/quota endpoint, luôn unknown. OAuth/token endpoints không retry tự động; timeout/size caps và HTTPS/no redirect/trust_env=false.

Catalog `/v1/models` có budget riêng8MiB **decoded**, đọc chunk64KiB và giới hạn1000entries; các JSON OAuth/Discovery/JWKS giữ512KiB, Responses SSE giữ1MiB. Chỉ projection slug/display_name của visibility=list được cache theo session. `model_listing_status` phân biệt unavailable/not_loaded/ready/empty/failed. Lỗi model có stage=model_listing được giữ riêng với OAuth; tải lại thành công chỉ xóa lỗi model, không xóa chẩn đoán OAuth khác. Model mất khỏi listing bị bỏ lựa chọn, không tự thay thế. GET status không gọi OpenAI; retry model là command riêng do người dùng bấm. Kích thước và deadline có mã lỗi riêng; decoded-size bound áp dụng cả gzip và không dựa vào Content-Length.

Ngoài model metadata, SQLite giữ `ai.chatgpt.oauth_diagnostic.v1` với **mã lỗi/tên bước và reason ID token từ danh mục tĩnh** để không mất chẩn đoán khi backend khởi động lại. Không ghi query callback, authorization code/state, exception/provider body, token hoặc account vào bản ghi này. Callback và UI dùng cùng danh mục thông báo tĩnh; reason chỉ tên nhánh kiểm tra, không chứa expected/actual claim, không xác nhận nguyên nhân của lượt live cũ; lỗi token endpoint chỉ nhận diện các OAuth error identifier đã biết, không echo `error_description`.

CredentialVault chia riêng `ai.chatgpt.tokens.v1` thành các mục ASCII tối đa900ký tự (≤1800byte UTF-16, dưới giới hạn2560byte Windows). Root chứa manifest slot/count/SHA-256; token vẫn chỉ ở OS vault. Hai slot a/b và khóa trong process cho phép ghi slot mới rồi publish root sau cùng; lỗi ghi giữ root cũ. Reader kiểm tra số phần/checksum; Disconnect quét cả hai slot, kể cả phần thừa sau ghi gián đoạn. Có giới hạn96phần/slot, không enumerate toàn bộ kho khóa. Google/API-key entries giữ định dạng cũ, token SIWC cũ vẫn đọc được. Tính nguyên tử này áp dụng cho một backend đang chạy, không phải khóa liên process; không chạy nhiều bản backend cùng dùng một vault.

RLock bảo vệ refresh single-flight và atomic token replacement. Refresh dùng client_id/resource/refresh_token, không gửi scopes mới. Theo handoff refresh token30ngày tính từ rotation; server có thể thu hồi sớm. Invalid grant/401/ID-token mismatch xóa token dùng được và yêu cầu reauthorization; lỗi network giữ credentials để không biến mất kết nối khi offline. Disconnect luôn xóa local token, thử revocation chỉ từ metadata issuer đã kiểm tra; báo rõ chưa xác nhận remote revocation nếu lỗi/không có endpoint.

## Inference và usage

Preflight không generate, trả model/session ID/billing source/quota unknown. Mỗi lượt phải consent riêng, approved_model và approved_connection_id khớp hiện tại. Đổi tài khoản/model sau consent hoặc khi đang queue sẽ chặn trước request. Session có request đã gửi có thể vẫn tiêu quota khi disconnect, nhưng round tiếp theo bị chặn.

Transport tạo body mới với allowlist `model`, `input` array, `store=false`, `stream=true`, optional function tools. Không sao chép body API-key. Các hosted tools bị chặn. Giữ tool registry, project isolation, bounded context/loops, history và evidence validation cũ; function outputs nối vào input array, không previous_response_id.

SSE xử lý CRLF/chunk fragmentation/UTF-8, delta, completed, failed, incomplete, error và abrupt EOF. Chỉ response.completed/status completed là terminal success. Tổng stream≤1MiB, event/buffer≤512KiB, idle30s và thời gian stream120s (kiểm tra tại chunk; không phải deadline cứng cho socket đang read). JSON/schema và evidence IDs vẫn phải hợp lệ để analysis thành công. UI chỉ hiển thị progress char count trước validation.

AIUsage provider=chatgpt, input/output token usage nếu có, USD=null/reserved0 chỉ để tách khỏi API-key dollar budget; không khẳng định inference miễn phí. Lỗi để usage unknown vì quota có thể đã dùng. Không tự retry/quota fallback. Giá API không dùng để tính hạn mức ChatGPT.

## API

- GET `/api/ai/chatgpt/status`
- POST `/api/ai/chatgpt/connect`: eligibility_acknowledged + localhost_acknowledged
- POST `/api/ai/chatgpt/models/refresh`
- PATCH `/api/ai/chatgpt/model`: slug
- POST `/api/ai/chatgpt/disconnect`: confirm + revoke

Các command dùng CSRF/Origin hiện có, tất cả responses no-store/no-referrer. Inference dùng API messages hiện có với provider chatgpt và consent gắn session/model, không có endpoint arbitrary requests.

## Trạng thái kiểm chứng

Contract theo handoff chính thức người dùng cung cấp ngày29/10/2026. Truy cập trực tiếp docs bị Tunnel403, nên đầy đủ preview limitations chưa được xác minh độc lập. OSS/license và tài khoản LocalSEO chưa có live approval. Không dùng license của thư viện để giả định license app. OAuth/model/stream test mocks không thay thế kiểm chứng thật trên Windows/localhost. Xem hướng dẫn và validation; dừng ở tính năng này.
