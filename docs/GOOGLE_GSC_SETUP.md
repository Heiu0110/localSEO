# Kết nối Google Search Console trên máy cá nhân

Ứng dụng dùng OAuth **Desktop app**, chỉ scope `https://www.googleapis.com/auth/webmasters.readonly`. Đây không phải Service Account, Web Application OAuth hoặc Google ADC. Không dùng biến `GOOGLE_APPLICATION_CREDENTIALS` của môi trường cho tài khoản cá nhân.

## Chạy thử trước khi kết nối Google

Chạy hai file `.bat` như README. Hai website `[DEMO]` vẫn dùng Mock Provider. Trong **Cài đặt → Properties trong workspace**, chọn **Tạo bộ thử nghiệm SQLite**, thêm `sc-domain:fixture.example` vào workspace, chọn kỳ 28/90/180 ngày hoặc kỳ tùy chỉnh rồi đồng bộ. Các bản ghi này luôn mang nhãn **Thử nghiệm SQLite**, không phải kết nối Google thật.

## Google Cloud

1. Mở [Google Cloud Console](https://console.cloud.google.com/), tạo hoặc chọn project bạn quản lý.
2. Trong **APIs & Services → Library**, tìm **Google Search Console API** (`searchconsole.googleapis.com`) và Enable. OAuth được cấu hình trong cùng project.
3. Trong **Google Auth Platform**, cấu hình **Branding**, tên ứng dụng, email hỗ trợ và thông tin liên hệ. Tên menu có thể thay đổi theo giao diện Google.
4. Chọn **Audience**: Internal chỉ phù hợp với tài khoản trong Google Workspace của tổ chức; với tài khoản cá nhân thường dùng External. Nếu ở trạng thái Testing, thêm chính tài khoản Google của bạn vào Test users.
5. Trong **Data Access**, chỉ khai báo scope Search Console read-only ở trên. Không thêm Gmail, Drive, Ads, `openid`, email/profile chỉ để hiển thị ảnh hoặc địa chỉ email.
6. Trong **Clients → Create client**, chọn loại **Desktop app**. Không chọn Web application. Đặt tên nhận diện, ví dụ SEO Local Workspace Desktop.
7. Tải credentials JSON của Desktop client về một thư mục cá nhân ngoài repository. Không gửi nội dung file, access token hoặc refresh token vào chat/Git.

## Kết nối trong ứng dụng

1. Chạy backend và frontend **trên cùng máy Windows với trình duyệt Google của bạn**.
2. Mở ứng dụng → **Cài đặt → Tích hợp Google Search Console → Nhập tệp OAuth JSON**. Backend xác thực loại client/endpoint và lưu cấu hình vào kho khóa hệ điều hành. JavaScript chỉ chuyển file qua FormData; không đọc hoặc hiển thị nội dung JSON.
3. Nhấn **Kết nối Google**. Nếu trình duyệt chặn cửa sổ, dùng liên kết **tiếp tục kết nối Google** xuất hiện trong Settings.
4. Chọn tài khoản có quyền với property, đọc và chấp nhận quyền Search Console read-only. Không cần quyền vào website thông qua crawling.
5. Google chuyển về callback loopback cố định `http://127.0.0.1:8000/api/integrations/gsc/oauth/callback`. Giữ backend đang chạy. Desktop client dùng loopback redirect; không đăng ký URI như một Web Application client và không dùng out-of-band copy/paste code.
6. Sau khi thành công, đóng tab xác thực và quay lại Settings. Ứng dụng dùng Authorization Code + PKCE (S256), state dùng một lần, hiệu lực 10 phút. Nếu callback bị từ chối hoặc hết hạn, kết nối lại để tạo phiên mới.
7. Danh sách properties được làm mới sau khi kết nối; cũng có nút **Làm mới properties**. Chọn một hoặc nhiều property vào workspace. Domain `sc-domain:...` và URL-prefix `https://.../` được giữ nguyên, không chuyển đổi qua lại.
8. Chọn từng property ở khu vực đồng bộ, chọn lịch sử (khuyến nghị 90 ngày) và **Bắt đầu đồng bộ**. Để so sánh 90 ngày với đủ kỳ trước, cần tối thiểu 180 ngày có bản ghi; ứng dụng không tạo so sánh giả nếu chưa có.
9. Mở **Phân tích GSC** để xem URL/truy vấn/quốc gia/thiết bị; hoặc **Tổng quan** và chọn `[GSC]` property. Mỗi nguồn dùng provider riêng. Các website `[DEMO]` luôn được giữ lại.

Ứng dụng cho phép thêm nhiều properties nhưng mỗi tác vụ đồng bộ chỉ nhắm một property/search type. Một worker chạy tuần tự; có thể xếp hàng tác vụ cho property khác. Không tự tải toàn bộ lịch sử nếu bạn chưa nhấn đồng bộ.

## Token, Testing và kết nối lại

- Token được giữ bằng Python keyring: Windows Credential Manager, macOS Keychain hoặc Linux Secret Service/KWallet được hỗ trợ. Không có fallback dạng plaintext, không lưu refresh token trong SQLite, localStorage, file `.env` hoặc khóa mã hóa cạnh ciphertext.
- Nếu không có kho khóa được hỗ trợ (thường gặp trên Linux headless), ứng dụng thông báo rõ và vẫn chạy Demo/SQLite đã lưu. Không bật `keyrings.alt` plaintext để bỏ qua bảo vệ.
- Credentials tự làm mới khi cần gọi Google. Nếu refresh token bị thu hồi/hết hạn, đồng bộ chuyển sang **Cần xác thực lại**; vào Settings → **Kết nối lại Google**. Dữ liệu đã lưu không bị xóa.
- Với External app ở **Testing**, refresh token cho các scope ngoài thông tin cơ bản thường có giới hạn khoảng **7 ngày**. Còn có thể hết hạn vì người dùng thu hồi quyền, thay đổi chính sách hoặc các giới hạn của Google. Localhost không tự miễn trừ OAuth policies.
- Khi chuyển app sang Production, Google có thể yêu cầu verification tùy audience/scopes/cách phân phối. Tuân theo Google Auth Platform; không tắt kiểm tra bảo mật hoặc giả định ứng dụng cá nhân được miễn mọi điều kiện.
- **Ngắt kết nối Google** xóa token trong kho khóa và thử gọi revoke tại Google. UI phân biệt đã thu hồi thành công với chỉ xóa cục bộ khi mạng/revocation không khả dụng. Cấu hình Desktop client và SQLite được giữ để có thể kết nối lại.
- Không có profile email/avatar vì không yêu cầu scope liên quan. Trạng thái kết nối là trạng thái xác thực cục bộ gần nhất; quyền bị thu hồi có thể chỉ được phát hiện ở lần gọi Google kế tiếp.

## Mạng và kiểm chứng thật

Máy cá nhân cần HTTPS tới `accounts.google.com`, `oauth2.googleapis.com`, `searchconsole.googleapis.com` (cùng các trang Google dùng khi đăng nhập). Không cần mở cổng backend ra Internet. Mặc định backend chỉ bind 127.0.0.1, frontend port 5173; giữ cổng 8000 cho callback.

Trong môi trường cloud phát triển, callback `127.0.0.1` của trình duyệt cá nhân không trỏ vào cloud container. Hãy thực hiện live OAuth trên máy cá nhân theo hướng dẫn trên. **Pending Live Verification**: chưa xác thực tài khoản Google thật, quyền property, refresh/revoke thật hoặc quota mạng thực trong lần triển khai này. Automated tests dùng fixtures/mocks và không tiêu tốn quota Google.

Tham khảo chính thức: [Installed apps OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies), [Search Console authorization](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing), [Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query).
