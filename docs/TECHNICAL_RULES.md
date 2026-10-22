# Danh mục Technical SEO v0.3 Core

Có 138 checks được ghi nhận theo master, không phải 138 kiểm tra đã chạy. Core có 63 capability automated gồm tín hiệu thu thập, service/workflow và 39 rule sinh finding. Các capability còn lại được đánh dấu rõ.

Mỗi rule có ID ổn định, version, required sources, priority group, default severity, confidence policy và recommendation; API `/api/technical/rules` trả metadata. Version hiện tại: `0.3-core-1`. Không đánh dấu Passed khi thiếu dữ liệu.

## Kết quả một audit

- Issue Found: có finding với evidence.
- Passed: automated check đã được đánh giá ít nhất một URL trong run completed/complete. Chỉ có nghĩa trong các URL đã đánh giá; xem evaluated_urls.
- Not Checked: chưa có dữ liệu phù hợp hoặc audit chưa đủ coverage để kết luận.
- Not Available: cần integration chưa có.
- Needs Review: kiểm tra thủ công.
- Not Implemented: chưa triển khai.

Bằng chứng có expected_behavior, actual_behavior, business_impact và rule version. Nếu cùng rule/source URL có nhiều target lỗi, giữ thêm tối đa 50 observations cùng tổng số; Link Explorer vẫn có quan hệ đầy đủ trong giới hạn graph. Không tự xác nhận link/canonical/duplicate finding đã sửa khi URL phụ thuộc bị robots chặn hoặc chưa đo lại.

HTTP-005 dùng chung observation LINK-005 để không tạo hai task cho cùng liên kết redirect; checklist phản ánh cùng finding. Nhóm MONITOR là các workflow history/compare/backlog đã thực hiện, không tự tạo finding per-URL hoặc đánh dấu đạt khi chưa chạy workflow đó.

## Bằng chứng và severity

Observed: HTTP/HTML đo trực tiếp; derived: đối chiếu canonical/links/sitemap/graph; heuristic: soft 404, ít chữ, orphan/duplicate candidate. Confidence: confirmed, strong_evidence, suspected, needs_manual_verification, unknown. HTTP 404 ở crawler không chứng minh Googlebot cũng bị lỗi.

Critical/High/Medium/Low/Informational là severity của finding, khác nhóm công việc P0/P1/P2. Ví dụ noindex homepage được mong muốn index là critical; thiếu canonical chỉ informational; multiple H1 là low và cần xem cấu trúc.

Queue priority nội bộ = severity (100/80/50/20/5) + URL importance (critical_money +30, important +20, supporting 0, low -5) + exposure click đã lưu (min(20, round(3×ln(1+clicks)))) + confidence (+10/+5/0/-5/-10). Có giải thích từng phần; không phải SEO score, không suy ra tác động ranking hoặc quan hệ nhân quả. Không có traffic vẫn đánh giá bằng chứng và mục đích URL.

Ngưỡng heuristic: dưới 100 từ cần xem thủ công, important page sâu hơn 4 HTML hops là candidate, từ 10 biến thể cùng URL family cảnh báo parameter explosion; bằng chứng ghi threshold/coverage. Exact text fingerprint chỉ chứng minh cùng text đã trích xuất, không xác nhận cannibalization.

## Catalog

| ID | Check | Capability | Nhóm |
|---|---|---|---|
| TECH-CRAWL-001 | Không xác nhận được robots.txt | Tự động | P0 |
| TECH-CRAWL-002 | URL quan trọng bị robots chặn | Tự động | P0 |
| TECH-CRAWL-003 | Tài nguyên CSS/JS bị robots chặn (mô phỏng) | Tự động | P0 |
| TECH-CRAWL-004 | URL quan trọng trả lỗi HTTP | Tự động | P0 |
| TECH-CRAWL-005 | broken internal links | Chưa triển khai | P0 |
| TECH-CRAWL-006 | JavaScript-only content | Cần tích hợp | P0 |
| TECH-CRAWL-007 | Nhiều biến thể query parameter | Tự động | P0 |
| TECH-CRAWL-008 | crawl diagnostics | Xem thủ công | P0 |
| TECH-INDEX-001 | local indexability assessment | Tự động | P0 |
| TECH-INDEX-002 | Noindex trên URL dự kiến lập chỉ mục | Tự động | P0 |
| TECH-INDEX-003 | URL Inspection comparison | Cần tích hợp | P0 |
| TECH-INDEX-004 | Crawled, currently not indexed | Cần tích hợp | P0 |
| TECH-INDEX-005 | Discovered, currently not indexed | Cần tích hợp | P0 |
| TECH-INDEX-006 | Ứng viên soft 404 | Tự động | P0 |
| TECH-INDEX-007 | Ứng viên nội dung ít chữ — cần xem thủ công | Tự động | P0 |
| TECH-INDEX-008 | duplicate content candidates | Chưa triển khai | P0 |
| TECH-INDEX-009 | index intent classification | Tự động | P0 |
| TECH-INDEX-010 | URL disposition | Tự động | P0 |
| TECH-CAN-001 | declared canonical detection | Tự động | P0 |
| TECH-CAN-002 | Thiếu canonical khai báo | Tự động | P0 |
| TECH-CAN-003 | Canonical mâu thuẫn hoặc không hợp lệ | Tự động | P0 |
| TECH-CAN-004 | Canonical trỏ tới URL lỗi | Tự động | P0 |
| TECH-CAN-005 | Canonical trỏ tới redirect | Tự động | P0 |
| TECH-CAN-006 | Canonical trỏ tới URL noindex | Tự động | P0 |
| TECH-CAN-007 | Google-selected canonical comparison | Cần tích hợp | P0 |
| TECH-CAN-008 | host and protocol variants | Chưa triển khai | P0 |
| TECH-CAN-009 | Biến thể dấu / cùng trả nội dung | Tự động | P0 |
| TECH-CAN-010 | Biến thể parameter có cùng fingerprint nội dung | Tự động | P0 |
| TECH-CAN-011 | Query × Page cannibalization | Cần tích hợp | P0 |
| TECH-SITEMAP-001 | Chưa phát hiện sitemap đọc được | Tự động | P1 |
| TECH-SITEMAP-002 | Không truy xuất được sitemap | Tự động | P1 |
| TECH-SITEMAP-003 | XML sitemap không hợp lệ | Tự động | P1 |
| TECH-SITEMAP-004 | sitemap index support | Tự động | P1 |
| TECH-SITEMAP-005 | URL trong sitemap trả lỗi hoặc redirect | Tự động | P1 |
| TECH-SITEMAP-006 | URL noindex nằm trong sitemap | Tự động | P1 |
| TECH-SITEMAP-007 | URL canonicalized nằm trong sitemap | Tự động | P1 |
| TECH-SITEMAP-008 | URL chỉ được thấy từ một nguồn trong phạm vi crawl | Tự động | P1 |
| TECH-SITEMAP-009 | Lastmod cần kiểm tra | Tự động | P1 |
| TECH-SITEMAP-010 | GSC sitemap status | Cần tích hợp | P1 |
| TECH-HTTP-001 | status classification | Tự động | P0 |
| TECH-HTTP-002 | Chuỗi redirect nhiều bước | Tự động | P0 |
| TECH-HTTP-003 | Vòng lặp hoặc vượt giới hạn redirect | Tự động | P0 |
| TECH-HTTP-004 | Redirect kết thúc lỗi hoặc ngoài scope | Tự động | P0 |
| TECH-HTTP-005 | Liên kết nội bộ đi qua redirect | Tự động | P0 |
| TECH-HTTP-006 | preferred host redirects | Chưa triển khai | P0 |
| TECH-HTTP-007 | HTTP to HTTPS | Chưa triển khai | P0 |
| TECH-HTTP-008 | redirect mapping validation | Chưa triển khai | P0 |
| TECH-HTTP-009 | Lỗi DNS, TLS, timeout hoặc kết nối | Tự động | P0 |
| TECH-ARCH-001 | crawl depth | Tự động | P1 |
| TECH-ARCH-002 | Trang quan trọng sâu hơn 4 liên kết | Tự động | P1 |
| TECH-ARCH-003 | Ứng viên orphan trong phạm vi đã quan sát | Tự động | P1 |
| TECH-ARCH-004 | URL structure | Chưa triển khai | P1 |
| TECH-ARCH-005 | pagination | Chưa triển khai | P1 |
| TECH-ARCH-006 | taxonomy and archive URLs | Chưa triển khai | P1 |
| TECH-ARCH-007 | topic architecture | Chưa triển khai | P1 |
| TECH-ARCH-008 | money page prioritization | Tự động | P1 |
| TECH-LINK-001 | internal link graph | Tự động | P1 |
| TECH-LINK-002 | inbound link counts | Tự động | P1 |
| TECH-LINK-003 | outgoing links | Tự động | P1 |
| TECH-LINK-004 | Liên kết nội bộ trỏ tới URL lỗi | Tự động | P1 |
| TECH-LINK-005 | Liên kết trỏ tới URL chuyển hướng | Tự động | P1 |
| TECH-LINK-006 | anchor text | Tự động | P1 |
| TECH-LINK-007 | links to money pages | Tự động | P1 |
| TECH-LINK-008 | breadcrumb extraction | Tự động | P1 |
| TECH-LINK-009 | BreadcrumbList comparison | Chưa triển khai | P1 |
| TECH-LINK-010 | Liên kết thiếu href có thể crawl | Tự động | P1 |
| TECH-ONPAGE-001 | Title thiếu, trùng hoặc nhiều khai báo | Tự động | P1 |
| TECH-ONPAGE-002 | Meta description thiếu hoặc trùng | Tự động | P1 |
| TECH-ONPAGE-003 | H1 thiếu hoặc có nhiều khai báo | Tự động | P1 |
| TECH-ONPAGE-004 | Cấp heading bị nhảy | Tự động | P1 |
| TECH-ONPAGE-005 | canonical and robots | Tự động | P1 |
| TECH-ONPAGE-006 | raw versus rendered HTML | Cần tích hợp | P1 |
| TECH-ONPAGE-007 | JS-dependent navigation | Cần tích hợp | P1 |
| TECH-ONPAGE-008 | Thiếu thuộc tính ngôn ngữ HTML | Tự động | P1 |
| TECH-ONPAGE-009 | Có lỗi giải mã ký tự | Tự động | P1 |
| TECH-ONPAGE-010 | HTML không đầy đủ để phân tích | Tự động | P1 |
| TECH-CWV-001 | LCP | Cần tích hợp | P1 |
| TECH-CWV-002 | INP | Cần tích hợp | P1 |
| TECH-CWV-003 | CLS | Cần tích hợp | P1 |
| TECH-CWV-004 | device comparison | Cần tích hợp | P1 |
| TECH-CWV-005 | TTFB | Cần tích hợp | P1 |
| TECH-CWV-006 | render-blocking resources | Cần tích hợp | P1 |
| TECH-CWV-007 | image optimization | Cần tích hợp | P1 |
| TECH-CWV-008 | caching and compression | Cần tích hợp | P1 |
| TECH-CWV-009 | LCP resource | Cần tích hợp | P1 |
| TECH-MOBILE-001 | viewport | Chưa triển khai | P1 |
| TECH-MOBILE-002 | responsive rendering | Chưa triển khai | P1 |
| TECH-MOBILE-003 | content parity | Chưa triển khai | P1 |
| TECH-MOBILE-004 | navigation usability | Chưa triển khai | P1 |
| TECH-MOBILE-005 | interstitials | Chưa triển khai | P1 |
| TECH-MOBILE-006 | image dimensions | Chưa triển khai | P1 |
| TECH-MOBILE-007 | lazy loading | Chưa triển khai | P1 |
| TECH-MOBILE-008 | mobile accessibility indicators | Chưa triển khai | P1 |
| TECH-SCHEMA-001 | JSON-LD extraction | Chưa triển khai | P2 |
| TECH-SCHEMA-002 | JSON validity | Chưa triển khai | P2 |
| TECH-SCHEMA-003 | schema type inventory | Chưa triển khai | P2 |
| TECH-SCHEMA-004 | duplicate declarations | Chưa triển khai | P2 |
| TECH-SCHEMA-005 | breadcrumb validation | Chưa triển khai | P2 |
| TECH-SCHEMA-006 | product/article field diagnostics | Chưa triển khai | P2 |
| TECH-SCHEMA-007 | visible-content consistency | Chưa triển khai | P2 |
| TECH-SCHEMA-008 | external validation | Chưa triển khai | P2 |
| TECH-SERVER-001 | response latency | Chưa triển khai | P1 |
| TECH-SERVER-002 | repeated 5xx/429 | Chưa triển khai | P1 |
| TECH-SERVER-003 | server log import | Xem thủ công | P1 |
| TECH-SERVER-004 | Googlebot log verification | Chưa triển khai | P1 |
| TECH-SERVER-005 | CMS detection | Chưa triển khai | P1 |
| TECH-SERVER-006 | cache headers | Chưa triển khai | P1 |
| TECH-SERVER-007 | PHP/server diagnostics | Xem thủ công | P1 |
| TECH-SERVER-008 | CMS/plugin conflicts | Chưa triển khai | P1 |
| TECH-SERVER-009 | backup/update status | Xem thủ công | P1 |
| TECH-SEC-001 | HTTPS availability | Chưa triển khai | P0 |
| TECH-SEC-002 | certificate diagnostics | Chưa triển khai | P0 |
| TECH-SEC-003 | mixed content candidates | Chưa triển khai | P0 |
| TECH-SEC-004 | staging exposure | Chưa triển khai | P0 |
| TECH-SEC-005 | unexpected metadata changes | Chưa triển khai | P0 |
| TECH-SEC-006 | redirect mapping QA | Chưa triển khai | P0 |
| TECH-SEC-007 | suspicious content candidates | Chưa triển khai | P0 |
| TECH-SEC-008 | manual security review | Xem thủ công | P0 |
| TECH-SEC-009 | backup/rollback readiness | Xem thủ công | P0 |
| TECH-LOCAL-001 | organization information extraction | Chưa triển khai | P2 |
| TECH-LOCAL-002 | consistency checks | Chưa triển khai | P2 |
| TECH-LOCAL-003 | LocalBusiness data | Chưa triển khai | P2 |
| TECH-LOCAL-004 | location landing pages | Chưa triển khai | P2 |
| TECH-LOCAL-005 | crawlable organization details | Chưa triển khai | P2 |
| TECH-LOCAL-006 | content accessibility | Chưa triển khai | P2 |
| TECH-LOCAL-007 | semantic data consistency | Chưa triển khai | P2 |
| TECH-LOCAL-008 | AI search readiness | Chưa triển khai | P2 |
| TECH-MONITOR-001 | audit history | Tự động | P1 |
| TECH-MONITOR-002 | issue comparison | Tự động | P1 |
| TECH-MONITOR-003 | new issues | Tự động | P1 |
| TECH-MONITOR-004 | resolved issues | Tự động | P1 |
| TECH-MONITOR-005 | recurring issues | Tự động | P1 |
| TECH-MONITOR-006 | GSC correlation | Tự động | P1 |
| TECH-MONITOR-007 | indexing history | Cần tích hợp | P1 |
| TECH-MONITOR-008 | technical change QA | Tự động | P1 |
| TECH-MONITOR-009 | action backlog | Tự động | P1 |
| TECH-MONITOR-010 | manual GSC checks | Xem thủ công | P1 |
| TECH-MONITOR-011 | alerts | Chưa triển khai | P1 |
