# Tích hợp Agent hiện có

Không có engine chat/provider/vault mới. `AIManager` và `ToolRegistry` vẫn giữ hội thoại, evidence envelopes, request idempotence, model approval, data processing consent, daily budget/reservation, tool budget, task history và human review.

9 read-only tools v1.0 được thêm:

- get_ai_visibility_overview
- get_visibility_prompt_cohort
- get_visibility_observation
- get_brand_mentions
- get_brand_citations
- get_competitor_visibility
- get_cited_source_summary
- get_geo_opportunities
- get_geo_opportunity_evidence

Website luôn do server khóa. visibility_id/observation_id/opportunity_id được kiểm tra project membership; không có arbitrary SQL, fetch URL, crawl, write registry hoặc publishing tool. Không có visibility project trả availability=false. Kết quả tối đa 8.000 byte/5 giây theo registry cũ; quá giới hạn báo lỗi, không silently gửi dataset.

`MessageCreate.geo_scope` gắn đúng project/opportunity. `GEOAnalysisContext` chứa objective, candidate, collection cohort, bounded snapshots + known evidence IDs, source provenance/limits. `GEOAgentAnalysis` mở rộng schema Analysis riêng cho lượt GEO, không làm phình schema của lượt SEO thông thường. `GEOOpportunityAnalysis` chứa findings, opportunities, limitations và next investigation; từng opportunity có facts/hypotheses/counterevidence, missing evidence, action/confidences/priority/verification.

Lượt GEO seed get_project_context và get_geo_opportunity_evidence, tính vào tool budget. Cloud chỉ quảng bá 9 visibility tools + các tool SEO liên quan, không toàn bộ catalog không cần thiết. local_report tạo structured offline report từ rule; không giả là suy luận của LLM. Cloud gọi provider đã có, không tự chọn provider trả phí hoặc live visibility collector.

Sau khi model trả, verifier kiểm tra scope/IDs/current sources và action prerequisites rồi lưu `visibility_agent_analyses` gắn ai_messages. Nội dung đã gate cũng lưu trong analysis của message. Generic task/review recommendations chỉ được chiếu từ GEO output đã gate; action thiếu prerequisites đổi cả action type lẫn action text thành investigation. No Action không tạo generic task thay đổi. Errors không được ghi thành successful verified result. UI có link sang hội thoại hiện có và kết quả structured trong opportunity drawer.

Inference live và ChatGPT auth không được chạy để nghiệm thu Core. Test provider giả kiểm tra schema, consent, tool/result/request budget và lifecycle trong cùng Agent; không xác nhận production model quality hoặc eligibility SIWC.
