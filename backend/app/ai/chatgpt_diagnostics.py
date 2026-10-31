"""Static OAuth diagnostics: never persist or render callback/provider payloads."""

OAUTH_DIAGNOSTIC = "ai.chatgpt.oauth_diagnostic.v1"
# Only these static reasons may cross the callback/API boundary. Never include
# decoded claims, expected/actual values, JWT headers or cryptography exceptions.
ID_TOKEN_REASONS = {
    "missing_token": "OpenAI chưa trả ID token. Cần kiểm tra lại contract hoặc quyền đăng nhập; không dùng access token thay thế.",
    "malformed_token": "ID token không đúng định dạng JWT được hỗ trợ.",
    "unsupported_algorithm": "Thuật toán ký ID token chưa được adapter hỗ trợ; chỉ chấp nhận RS256.",
    "unsupported_header": "ID token có JOSE header không được hỗ trợ; không tải khóa từ URL trong token.",
    "missing_key_id": "ID token thiếu mã khóa ký hợp lệ.",
    "signing_key_unavailable": "Không tìm thấy duy nhất khóa ký phù hợp trong JWKS chính thức. Thử lượt đăng nhập mới; nếu còn lỗi cần đối chiếu khóa/contract OpenAI.",
    "invalid_signing_key": "Khóa ký trong JWKS không đáp ứng yêu cầu RSA xác minh chữ ký.",
    "signature_mismatch": "Chữ ký ID token không khớp khóa OpenAI. Đăng nhập bị chặn.",
    "issuer_mismatch": "Issuer của ID token không khớp issuer OpenAI được cấu hình cố định.",
    "audience_mismatch": "Audience của ID token không khớp issued client ID của lượt đăng nhập. Cần đối chiếu contract đăng ký động; không chấp nhận audience thay thế.",
    "authorized_party_mismatch": "Authorized party của ID token không khớp client đăng nhập.",
    "invalid_timestamp": "ID token thiếu thời hạn hợp lệ hoặc có mốc thời gian không hợp lệ.",
    "token_expired": "ID token đã hết hạn theo đồng hồ backend. Trên Windows bật Set time automatically, chọn đúng múi giờ và nhấn Sync now, rồi đăng nhập lại.",
    "issued_in_future": "Thời điểm phát hành ID token vượt quá 60 giây so với đồng hồ backend. Trên Windows bật Set time automatically, chọn đúng múi giờ và nhấn Sync now, rồi đăng nhập lại.",
    "not_yet_valid": "ID token chưa có hiệu lực theo đồng hồ backend. Trên Windows kiểm tra ngày giờ tự động và nhấn Sync now, rồi đăng nhập lại.",
    "subject_mismatch": "ID token thiếu tài khoản hợp lệ hoặc tài khoản đã đổi khi refresh. Cần đăng nhập lại.",
    "nonce_missing": "ID token không chứa nonce đã yêu cầu trong lượt OAuth. Không hoàn tất đăng nhập khi chưa xác minh được nonce.",
    "nonce_mismatch": "Nonce của ID token không khớp lượt OAuth hiện tại. Đóng callback cũ và bắt đầu lượt đăng nhập mới.",
}
STAGES = {
    "callback_validation": "Kiểm tra callback",
    "client_registration": "Xác nhận client đăng ký động",
    "token_exchange": "Đổi authorization code lấy token",
    "id_token_validation": "Xác minh ID token",
    "credential_storage": "Lưu vào OS Credential Vault",
    "model_listing": "Đọc model được cấp quyền",
}
MESSAGES = {
    "chatgpt_callback": "Callback không hợp lệ; bắt đầu lượt đăng nhập mới từ AI Settings.",
    "chatgpt_callback_host": "Host callback không khớp listener localhost của lượt đăng nhập.",
    "chatgpt_callback_path": "Đường dẫn callback không hợp lệ.",
    "chatgpt_invalid_state": "Phiên callback không khớp, đã dùng hoặc backend đã khởi động lại. Bắt đầu lượt đăng nhập mới; không tải lại URL callback cũ.",
    "chatgpt_oauth_expired": "Phiên đăng nhập đã hết hạn; bắt đầu lượt đăng nhập mới từ AI Settings.",
    "chatgpt_oauth_interrupted": "Backend đã dừng hoặc khởi động lại khi đang chờ đăng nhập. Nhấn Continue with ChatGPT để tạo phiên mới.",
    "chatgpt_consent_denied": "Người dùng hoặc OpenAI chưa cấp quyền đăng nhập.",
    "chatgpt_callback_code": "Callback chưa có authorization code hợp lệ.",
    "chatgpt_invalid_client": "Callback đăng ký động chưa có client_id oaiapp_ hợp lệ. LocalSEO không tự tạo client ID hoặc đổi token bằng dynamic_agent_client.",
    "chatgpt_client_changed": "Client ID không khớp lượt đăng nhập đã bắt đầu.",
    "chatgpt_invalid_id_token": "ID token chưa vượt qua kiểm tra chữ ký, issuer, audience, thời gian, nonce hoặc tài khoản.",
    "chatgpt_invalid_tokens": "OpenAI chưa trả đủ Bearer token, refresh token và thời hạn hợp lệ.",
    "chatgpt_invalid_scope": "OpenAI chưa trả granted scope hợp lệ.",
    "chatgpt_discovery_invalid": "OIDC discovery không khớp endpoints OpenAI đã xác định.",
    "chatgpt_jwks": "JWKS xác minh chữ ký không hợp lệ.",
    "chatgpt_pkce_unsupported": "Issuer chưa công bố PKCE S256.",
    "chatgpt_signing_unsupported": "Thuật toán ID token chưa được adapter hỗ trợ.",
    "secure_storage_unavailable": "Không thể đọc/ghi đầy đủ OS Credential Vault. Kiểm tra Windows Credential Manager; nếu token hỏng, ngắt kết nối và đăng nhập lại.",
    "chatgpt_oauth_invalid_grant": "OpenAI từ chối code/refresh token: đã hết hạn, đã dùng, bị thu hồi hoặc không khớp PKCE/redirect URI. Bắt đầu lượt đăng nhập mới; không dùng lại callback cũ.",
    "chatgpt_oauth_invalid_client": "OpenAI không chấp nhận client đăng ký cho lượt đăng nhập này. Cần kiểm tra issued client ID và điều kiện preview.",
    "chatgpt_oauth_invalid_request": "OpenAI từ chối tham số đổi token; cần kiểm tra contract SIWC/redirect URI. Không tự đổi sang luồng API key.",
    "chatgpt_oauth_invalid_scope": "OpenAI không chấp nhận scope/resource của request token. Cần đối chiếu điều kiện preview.",
    "chatgpt_request_rejected": "OpenAI từ chối request SIWC; kiểm tra contract hoặc điều kiện preview.",
    "chatgpt_reauthorization_required": "Token không hợp lệ hoặc bị thu hồi; cần đăng nhập lại.",
    "chatgpt_not_authorized": "Tài khoản hoặc ứng dụng chưa được OpenAI cho phép dùng ChatGPT Plan Usage.",
    "chatgpt_quota": "ChatGPT đang giới hạn hạn mức/rate limit; không chuyển sang API trả phí.",
    "chatgpt_unavailable": "Dịch vụ OpenAI tạm thời không khả dụng; thử đăng nhập mới sau.",
    "chatgpt_network": "Không kết nối được OpenAI hoặc request hết thời gian; kiểm tra kết nối backend rồi tạo lượt đăng nhập mới.",
    "chatgpt_response_limit": "Phản hồi OpenAI vượt giới hạn cho phép.",
    "chatgpt_models_response_limit": "Danh sách model OpenAI vượt giới hạn 8 MiB sau giải nén. Phiên đăng nhập được giữ; chưa tải được model.",
    "chatgpt_response_timeout": "Đọc phản hồi OpenAI vượt thời gian cho phép. Không tự gửi lại request.",
    "chatgpt_models_invalid": "OpenAI chưa trả danh sách model SIWC hợp lệ. Phiên đăng nhập được giữ; chưa tải được model.",
    "chatgpt_invalid_response": "OpenAI trả phản hồi JSON không hợp lệ.",
    "chatgpt_provider_error": "OpenAI chưa hoàn tất request SIWC; không tự retry hoặc chuyển provider.",
    "chatgpt_oauth_failed": "Chưa hoàn tất đăng nhập ChatGPT. Quay lại AI Settings để tạo lượt đăng nhập mới.",
}


def diagnostic(code, stage="callback_validation", reason=None):
    code = (
        code if isinstance(code, str) and code in MESSAGES else "chatgpt_oauth_failed"
    )
    result = {
        "code": code,
        "detail": MESSAGES[code],
        "stage": (
            stage
            if isinstance(stage, str) and stage in STAGES
            else "callback_validation"
        ),
    }
    if result["stage"] == "model_listing" and code == "chatgpt_network":
        result["detail"] = (
            "Không tải được model do kết nối OpenAI hoặc request hết thời gian. Kiểm tra mạng rồi nhấn Lấy danh sách model ChatGPT để thử lại; không tự gửi lại request."
        )
    if (
        code == "chatgpt_invalid_id_token"
        and isinstance(reason, str)
        and reason in ID_TOKEN_REASONS
    ):
        result["reason"] = reason
        result["detail"] = ID_TOKEN_REASONS[reason]
    return result
