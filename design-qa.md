# LocalSEO — monochrome UI review

Date: 2026-10-29

## Target and evidence

- Source visual truth: the user's latest inline reference image, 1152 × 2048 px, showing a white/silver glass dashboard with black panels and pill navigation. The original attachment is visible in the conversation but is not available as an image file in the execution workspace.
- This is a style adaptation for the existing Vietnamese SEO application. The reference's calendar, people, file preview and French copy are not LocalSEO features.
- Implementation: local Chromium at `http://127.0.0.1:5173`, Dashboard, demo `xuong-may`, 28 days, previous-period comparison enabled, sidebar expanded on desktop and collapsed on mobile.
- Desktop: [full-page capture](docs/ui/monochrome-desktop.png), CSS viewport 1440 × 1000, image 1440 × 2073, deviceScaleFactor 1.
- Mobile: [full-page capture](docs/ui/monochrome-mobile.png), CSS viewport 390 × 1000, image 390 × 3265, deviceScaleFactor 1.
- Other rendered captures: `/tmp/localSEO-monochrome-{settings,gsc,technical,keywords,ai-settings}.png`, corresponding `-mobile.png` captures, and `/tmp/localSEO-monochrome-research-loaded{,-mobile}.png`.
- Focused evidence: `/tmp/localSEO-monochrome-tooltip.png`, a 1440 × 1000 viewport capture with the first KPI tooltip open.
- No density resampling was applied. The source includes a decorative outer stage; its dimensions do not describe the application's CSS viewport. Exact pixel correspondence is not asserted.

## Findings and iteration history

1. [P2, fixed] The privacy-note icon inherited the former dark sidebar's white accent and became faint on the new light sidebar. Changed `.local-note > svg` to `--sidebar-text`. The final desktop capture and focused tooltip capture show a dark, readable icon.
2. [P3, fixed] The Dashboard navigation dot remained visible on other routes. Hide `.nav-active-dot` outside `.active`. The selected navigation item remains a black pill, with a visible keyboard focus outline.
3. [Evidence gap] A normalized, combined source-image/implementation comparison could not be produced because the original inline image has no local file or downloadable identifier. The rendered screens were inspected against the visible design direction in the conversation; this is not a side-by-side or pixel-level verification.

## Required fidelity surfaces

- **Fonts and typography:** retain the existing offline Inter/system sans stack and Vietnamese copy. Desktop headings are 42 px, mobile 28 px; metrics scale between 25 and 38 px. Table values retain tabular numerals, existing truncation, horizontal scrolling and full labels in detail views. Font rendering can vary with installed system fonts; no remote font request was added.
- **Spacing and layout rhythm:** a rounded glass shell, inset light sidebar, 24 px cards, soft shadows and pill controls follow the reference. Tables retain their existing data structure and density. Mobile margins, sidebar width and card padding are reduced to preserve content width. Sidebar position was checked before/after a 700 px page scroll at 1440 and 390 px.
- **Colors and tokens:** shared porcelain `#fcfcfc`, silver/gray surfaces and ink `#111111`. The first KPI and source-status panel use an inverse palette. Chart series retain solid versus dashed strokes. Trends and severity remain explicit in text and direction icons. Tooltip foreground/background were verified as `#fafafa` / `#151515`.
- **Image quality:** one generated 1672 × 941 WebP stone background, 56.1 KB, bundled locally. It preserves the reference's pale sculptural direction without replacing any functional screen with a raster image. Existing Lucide navigation/control icons and Recharts plots remain functional. The favicon was recolored without changing its existing geometry.
- **Copy and content:** Vietnamese labels, SEO terminology, demo/SQLite distinctions, source warnings, offline mode, and SIWC Pending Live Verification are retained. No example team, calendar or fabricated SEO numbers were introduced.

## Interaction and regression checks

- Production build passed: `npm --prefix frontend run build`.
- 62/62 tests outside Research passed in the full regression run.
- Research rerun: 10/10 passed after making two existing test waits explicit: wait for the approval save before reselecting a keyword, and wait for the competitor tab to activate before inspecting its panel. Application business logic was not changed.
- The full run before those wait fixes encountered Research timing failures; it was not a single green 72-test run. All 72 distinct scenarios have passed across the full run and scoped rerun.
- Existing responsive checks cover 1366, 1024, 768 and 390 px where applicable. Additional captures of Settings, GSC, Technical SEO, Keyword Tracking, Research and AI Settings at desktop/mobile widths had no page overflow and no browser page/console errors.
- Table search/sort/pagination/export, chart metric/series selection, source switching, detail sheets, sidebar navigation/collapse, form workflows, AI settings and mocked ChatGPT connection states passed regression checks.
- No live Google or ChatGPT authentication/inference was performed for this presentation change. No backend, database schema, dependency or startup-script changes.

## Implementation checklist

- [x] Apply shared monochrome tokens and reference-inspired surfaces.
- [x] Preserve existing Vietnamese SEO/AI workflows.
- [x] Verify desktop/mobile rendering and key interactions.
- [x] Fix the light-sidebar icon contrast and capture the revised screen.
- [ ] Produce the required combined comparison with the original source image when it is accessible as an image file.

## Follow-up polish

- The screenshot's people/calendar/file imagery is intentionally omitted because it does not represent LocalSEO data.
- Owner review on localhost can assess the visual direction on the target Windows browser.

final result: blocked

The remaining blocker is the source-image comparison artifact, not a known functional or responsive defect. The Product Design QA skill requires source and implementation together in the same comparison input before a visual pass can be declared.
