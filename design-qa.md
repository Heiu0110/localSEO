# Kiểm tra bảng màu theo ảnh tham chiếu

Phạm vi: yêu cầu đổi màu UI ngày 21/10/2026. Ảnh nguồn là ảnh người dùng đính kèm trong cuộc trò chuyện (736 × 1349 px, không có đường dẫn file local). Chỉ tham chiếu bảng màu kem/be/nâu đồng/nâu espresso. Bố cục landing page, serif display font và hình nội thất trong ảnh nằm ngoài phạm vi; không thay thế Dashboard bằng landing page.

## Bằng chứng giao diện

- Browser-rendered captures bằng Playwright/Chromium trên ứng dụng local, không chỉ kiểm tra HTTP/build.
- Desktop CSS viewport 1440 × 1080, deviceScaleFactor 1; ảnh full-page giữ chiều rộng 1440 px: `/tmp/seo-copper-dashboard.png`, `/tmp/seo-copper-settings.png`, `/tmp/seo-copper-analytics.png`, `/tmp/seo-copper-analytics-urls.png`.
- Mobile CSS viewport/ảnh 390 × 844, density 1: `/tmp/seo-copper-mobile-dashboard.png`, `/tmp/seo-copper-mobile-settings.png`, `/tmp/seo-copper-mobile-analytics.png`.
- Vùng chart, tab, nút và focus ring: `/tmp/seo-copper-controls.png` (1180 × 550 px, crop desktop).
- Đã xem ảnh tham chiếu trong cuộc trò chuyện và các ảnh giao diện render. So sánh ở cấp palette; không chuẩn hóa hai bố cục khác nhau để tuyên bố khớp pixel. Ảnh chụp nội bộ ở `/tmp`, không chứa Google credentials.

## Đánh giá

- **Typography:** giữ font sans-serif, phân cấp KPI và tiếng Việt hiện tại; serif của ảnh không được áp dụng vì yêu cầu chỉ đổi màu.
- **Spacing/layout:** giữ nguyên spacing, lưới, border radius và responsive. Không phát hiện overflow ở các breakpoint đã kiểm tra.
- **Colors:** nền `#e9e1d7`, thẻ `#fffdf9`, primary `#895537`, sidebar `#472b1e`; tương ứng màu be, trắng ngà, nâu đồng và nâu sẫm trong ảnh. Hover, focus, selected, tooltip, warning, progress, biểu đồ, theme-color và favicon dùng màu đồng bộ.
- **Contrast:** muted text trên nền be 4,69:1; subtle text 4,66:1; chữ nút 6,05:1; chữ badge 4,74:1; sidebar secondary 6,79:1. Xu hướng vẫn có mũi tên/dấu số; biểu đồ kỳ trước vẫn nét đứt.
- **Assets:** giữ bộ icon và cấu trúc favicon hiện có, chỉ đổi fill/stroke của favicon; không cần ảnh trang trí cho tác vụ đổi màu.
- **Copy/content:** không sửa nội dung báo cáo, số liệu, nhãn nguồn dữ liệu hoặc hành vi đồng bộ.

## Lịch sử kiểm tra và xác minh

Trước capture, đã làm đậm muted/subtle text để đạt tối thiểu 4,5:1 trên nền be. Lượt capture Analytics đầu còn skeleton; đã chụp lại sau khi bảng có dữ liệu. Không phát hiện P0/P1/P2 trong phạm vi đổi màu sau kiểm tra cuối.

`npm run build`: passed. Toàn bộ 26 Playwright tests: passed, bao gồm chọn website/kỳ, chart/compare, tìm kiếm/sort/pagination, panel, CSV, Settings→Sync→Analytics và responsive 1366/1024/768/390 px. Các phiên browser chụp ảnh không có pageerror. Không chạy lại backend tests vì không sửa backend.

Checklist hoàn tất: palette chung; trạng thái tương tác; ảnh desktop/mobile; bảng đã tải xong; tương phản chữ chính; regression tests và build.

final result: passed
