# Kết nối ChatGPT Plan Usage trên localhost

Tích hợp theo bản **Official Implementation Handoff** người dùng cung cấp, đối chiếu ngày29/10/2026. Bốn URL chính thức bị Tunnel403 trong môi trường phát triển; không tuyên bố đã tự đọc lại đầy đủ Preview Limitations hoặc đã đăng nhập thật.

## Eligibility và tình trạng hiện tại

Luồng triển khai là **Open-source / Locally Hosted Client**, dynamic registration; không phải OAuth của website thương mại. LocalSEO hiện chưa có LICENSE cho chính dự án ở thư mục gốc (license của thư viện Swagger không phải license của LocalSEO). Repo public không tự chứng minh đủ điều kiện OSS. Không thêm hoặc thay đổi license trong lần tích hợp này.

**Eligibility và đăng nhập/inference thật: Pending Live Verification.** Người sở hữu cần xác nhận quyền sử dụng mã nguồn và tính phù hợp với điều kiện preview trước khi thử OAuth. Checkbox trong app chỉ ghi nhận đã rà soát, không cấp license hoặc bảo đảm OpenAI chấp thuận. Nếu chưa đáp ứng điều kiện, giữ hai checkbox chưa chọn và tiếp tục dùng API Key Provider hoặc báo cáo ngoại tuyến.

Có scope `chatgpt.tokens.use.direct` chỉ chứng minh quyền đã được cấp trong token response; không chứng minh gói Plus, số dư hạn mức hoặc model đang sẵn sàng. OpenAI có thể từ chối403 hoặc giới hạn429/503. App không tự mua API credits hoặc chuyển sang API Key Provider.

## Các bước kiểm chứng trên máy cá nhân

1. Cập nhật source và chạy `run-backend.bat`, `run-frontend.bat` như README. Mở `http://127.0.0.1:5173` trên cùng máy backend, không dùng preview cloud hoặc trình duyệt ở máy khác.
2. Vào **AI Workspace → AI Settings → ChatGPT Connection**. Cần OS Credential Vault khả dụng (Windows Credential Manager). Không có plaintext fallback.
3. Đọc các link điều kiện OpenAI, xác nhận eligibility/quyền sử dụng mã nguồn và trình duyệt cùng máy. Nếu chưa xác nhận được, dừng tại đây.
4. Nhấn **Continue with ChatGPT**. Backend mở listener127.0.0.1 ở port khả dụng trước, rồi trả authorization URL. Nếu popup bị chặn, dùng link tiếp tục được hiển thị trong panel.
5. Đăng nhập và consent tại `auth.openai.com`. Callback quay về `http://127.0.0.1:<port>/auth/callback`. URI được tạo thực tế và dùng y hệt khi exchange; không cấu hình URI minh họa1455 hoặc Client ID tự đặt.
6. Lần đầu dùng `dynamic_agent_client`; callback phải có issued client ID `oaiapp_...`. App lưu registration sau khi xác minh ID token, dùng lại khi đăng nhập sau. Không cần client secret hoặc API key cho flow này.
7. Quay lại panel. Nếu hiện **Connected — ChatGPT Plan Usage Not Authorized**, thiếu direct scope nên inference bị chặn. Đăng nhập thành công không tự chứng minh Plan Usage được cấp.
8. Khi có quyền, danh sách model được lấy từ `/v1/models`. Chỉ hiện `visibility=list`, dùng `display_name` và `slug`. Chọn và **Lưu model ChatGPT**; không lấy mặc định từ API Key Provider.
9. Trong chat, chọn **ChatGPT · Plan Usage**, nhập một câu hỏi ngắn, nhấn **Kiểm tra quyền và model ChatGPT cho lượt này**, rà soát tài khoản/model/số request tối đa rồi xác nhận gửi dữ liệu. Đây mới là hành động inference, có thể sử dụng hạn mức ChatGPT.
10. Chỉ khi nhận `response.completed` mới ghi terminal success cho provider. Câu trả lời còn phải qua kiểm tra JSON/evidence của Agent. Text delta chưa xác minh chỉ hiển thị số ký tự tiến độ, không hiện kết luận chưa kiểm tra.
11. Kiểm tra Usage: token counts nếu OpenAI trả về; billing source là ChatGPT Plan Usage, USD không được suy ra từ bảng giá API. Balance/quota remaining chưa có endpoint được xác minh, nên không bịa số dư.

Các bước trên là quy trình để người dùng xác minh, **chưa được thực hiện live trong cloud**. Không cần gửi token, code callback hoặc client secret vào chat.

## Expiry, disconnect và lỗi

### Callback báo chưa hoàn tất hoặc nút làm mới không có kết quả

Cập nhật source rồi **dừng và chạy lại cả backend lẫn frontend**. Đóng tab callback cũ, vào AI Settings và bắt đầu một lượt **Continue with ChatGPT** mới. Không tải lại URL callback hoặc gửi authorization code vào chat.

Bản sửa ngày 30/10/2026 bổ sung:

- Trang callback hiển thị **mã lỗi và bước thất bại**, kèm hướng dẫn bắt đầu lại. Với JavaScript hoạt động, code/state được bỏ khỏi thanh địa chỉ bằng History API; không đưa chúng vào HTML, logs hay thông báo lỗi.
- **Làm mới trạng thái ChatGPT** luôn thông báo đang chờ, đã kết nối, thất bại hoặc chưa có kết quả. Nếu backend đã khởi động lại, cần tạo lượt OAuth mới vì state/PKCE của lượt cũ chỉ tồn tại trong RAM.
- Mã lỗi/bước OAuth được lưu làm metadata để có thể đọc lại sau restart; không lưu code/state/token, phản hồi thô của OpenAI hoặc dữ liệu tài khoản vào metadata này.
- Token ChatGPT dài được chia thành các mục nhỏ **trong OS Credential Vault** để đáp ứng giới hạn CredentialBlob của Windows. Không có fallback sang file, SQLite hay frontend. Bản cài cũ vẫn đọc được; lượt ghi mới chỉ thay bộ token đang dùng sau khi ghi đủ các phần.

| Mã/bước | Cách xử lý |
|---|---|
| `secure_storage_unavailable` · Lưu vào OS Credential Vault | Kiểm tra Windows Credential Manager. Sau cập nhật, thử lượt đăng nhập mới. Nếu token bị hỏng, dùng **Disconnect ChatGPT** rồi kết nối lại; thao tác này vẫn có thể xóa bản ghi chia phần bị thiếu. |
| `chatgpt_invalid_client` · Xác nhận client đăng ký động | Callback không có issued client ID hợp lệ. Không tự tạo ID hoặc dùng `dynamic_agent_client` để exchange; cần đối chiếu contract/eligibility SIWC. |
| `chatgpt_oauth_invalid_grant` · Đổi authorization code lấy token | Code/refresh token hết hạn, đã dùng, bị thu hồi hoặc không khớp PKCE/redirect. Tạo lượt đăng nhập mới; không dùng lại callback cũ. |
| `chatgpt_invalid_state`, `chatgpt_oauth_interrupted` | Phiên cũ không còn khớp backend hiện tại. Bắt đầu lại trong AI Settings. |
| `chatgpt_invalid_id_token` · Xác minh ID token | Đọc thêm **Chi tiết kiểm tra** trên callback hoặc AI Settings theo bảng bên dưới. Không bỏ kiểm tra chữ ký, audience hoặc nonce để vượt lỗi. |

### Chi tiết xác minh ID token · cập nhật 31/10/2026

Mã `chatgpt_invalid_id_token` trước đây gộp nhiều lỗi nên không xác định được nhánh thất bại. Bản cập nhật hiển thị thêm **Chi tiết kiểm tra** trên callback và AI Settings; nhấn **Làm mới trạng thái ChatGPT** để đọc lại. Mã chi tiết được giữ sau restart. Chỉ lưu các identifier từ danh mục tĩnh, không lưu JWT, claims, client ID thực tế, nonce, exception hoặc phản hồi OpenAI vào chẩn đoán.

| Chi tiết kiểm tra | Ý nghĩa và bước tiếp theo |
|---|---|
| `issued_in_future`, `not_yet_valid`, `token_expired` | Mốc thời gian không hợp lệ theo đồng hồ backend. Nếu giờ Windows bị lệch, bật Set time automatically, chọn đúng múi giờ và Sync now. Khi giờ đã đúng, không tự kết luận đây là nguyên nhân; đọc mã của lượt mới. |
| `audience_mismatch`, `authorized_party_mismatch` | Client trong ID token không khớp issued client của lượt OAuth. Cần đối chiếu contract đăng ký động OpenAI; không đổi audience sang dynamic_agent_client hoặc thêm client tùy ý để vượt lỗi. |
| `nonce_missing`, `nonce_mismatch` | Token thiếu/không khớp nonce của lượt đăng nhập hiện tại. Đóng callback cũ, bắt đầu lượt mới. Nếu lặp lại cần đối chiếu contract SIWC; không tắt nonce validation. |
| `signing_key_unavailable`, `invalid_signing_key`, `signature_mismatch` | JWKS không có khóa phù hợp hoặc chữ ký không hợp lệ. Không dùng khóa/URL từ JWT để thay JWKS chính thức. |
| `issuer_mismatch`, `unsupported_algorithm`, `unsupported_header` | Token không đáp ứng issuer/JOSE contract hiện được hỗ trợ (RS256). Không tự chấp nhận issuer/thuật toán mới. |
| `missing_token`, `malformed_token`, `missing_key_id`, `invalid_timestamp`, `subject_mismatch` | Phản hồi thiếu hoặc không đáp ứng yêu cầu ID token/tài khoản. Không dùng access token làm ID token. |

Sửa được tái hiện bằng test: code cũ từ chối token hợp lệ khi `iat` đi trước đồng hồ backend 31–60 giây. Giới hạn lệch giờ hiện là **60 giây**, áp dụng nhất quán cho `exp`, `iat`, `nbf`; token vượt giới hạn vẫn bị từ chối. JWKS có phần tử không hợp lệ không liên quan cũng không làm hỏng bước chọn khóa ký hợp lệ. Đây là các lỗi kiểm thử được, **chưa phải nguyên nhân đã xác nhận của ảnh người dùng**, nhất là khi người dùng xác nhận giờ Windows đang đúng.

Sau cập nhật, dừng/chạy lại backend và frontend rồi tạo lượt **Continue with ChatGPT** mới. Nếu còn lỗi, chỉ cung cấp **mã lỗi + Chi tiết kiểm tra**; không gửi URL callback, code hoặc token. Lỗi cũ chỉ lưu mã chung nên không thể khôi phục chi tiết từ lượt trước.

**Pending Live Verification:** chưa xác minh được lần OAuth thật trên máy người dùng. Truy cập lại official docs, Discovery và JWKS từ môi trường phát triển ngày 31/10/2026 vẫn bị Tunnel403; không có bằng chứng để nới audience/nonce/issuer/thuật toán. Kiểm thử dùng issuer và RSA keys mô phỏng, không chứng minh tài khoản live đã kết nối.

Ảnh callback chung không đủ xác nhận nguyên nhân của một lần đăng nhập thực tế. Lỗi kích thước Windows đã được tái hiện bằng backend mô phỏng giới hạn 2560 byte; đăng nhập thật trên máy cá nhân vẫn **Pending Live Verification**. Nếu lỗi còn, chỉ gửi **mã lỗi và bước**, không gửi URL callback hay token.

- Access token dùng `expires_in` của token response; refresh trước khi còn60giây. Refresh token lưu riêng an toàn, thời hạn30ngày theo handoff, thay cùng access token dưới một khóa để không refresh trùng. Nếu OpenAI thu hồi sớm, đăng nhập lại.
- `401`: token/refresh bị thu hồi hoặc hết hạn → cần kết nối lại. `403`: quyền/eligibility chưa đáp ứng. `429`: rate/quota giới hạn. `503`: dịch vụ hoặc kiểm tra hạn mức chưa khả dụng. Không tự retry inference hoặc fallback trả phí.
- Callback state hết hạn sau10phút; code/state dùng một lần. Restart backend hủy phiên đang chờ, cần bắt đầu lại.
- **Disconnect ChatGPT** xóa tokens và model cache cục bộ. App thử revocation nếu OIDC Discovery cung cấp endpoint hợp lệ; nếu không xác nhận được, UI nói rõ và người dùng có thể quản lý quyền tại tài khoản ChatGPT. Issued client registration không chứa tokens vẫn được giữ để đăng nhập lại.
- Model không còn trong listing → dừng và yêu cầu chọn lại. Không tự dùng model khác.
- Stream failed/incomplete/mất kết nối → thất bại, usage có thể unknown; không tự gửi lại vì hạn mức có thể đã bị sử dụng.
- Nếu không mở được port loopback/kho khóa, hoặc preview chưa cho phép LocalSEO, giữ trạng thái Pending Live Verification. Không sửa OAuth Google hoặc bật API trả phí để che lỗi.

Giới hạn hiện tại: RS256 ID tokens; HTTP Responses SSE; chỉ function tools nội bộ. Full preview allowlist chưa tự đối chiếu lại được. Transport chỉ gửi model/input/store/stream và function tools; không gửi `max_output_tokens`, `max_tool_calls`, `temperature`, `top_p`, `metadata`, `conversation`, `previous_response_id`, `background`, `truncation`, hosted MCP hoặc hosted tools. Structured JSON được yêu cầu qua prompt và kiểm tra ở backend, không forward `text.format` chưa được xác minh trong handoff.

Nguồn chính thức:
- https://developers.openai.com/siwc/quickstart
- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
