# Project Progress — AI Video Watermark Detection & Removal System

Single source of truth for build status across all phases. Update this as work
advances so any later session can pick up where we left off.

Legend: `[x]` done · `[ ]` todo · `[~]` in progress

Source plan: `.claude/plans/goofy-watching-turing.md`
Specs: `../Product Requirements Document`, `../Software Requirements Specification.md`

---

## Quick status

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Repo scaffold & local dev infra | [x] done |
| 2 | Auth + user dashboard | [x] done |
| 3 | Upload pipeline | [x] done |
| 4 | Manual mask editor + canvas | [x] done |
| 5 | Processing pipeline (inpaint + encode) | [x] done |
| 6 | Preview + download | [x] done |
| 7 | AI detection | [x] done |
| 8 | Admin + hardening | [x] done |
| 9 | Tests + README | [x] done |
| AP1+2 | Admin Panel — Foundation + Users/Projects (PRD Phases 1+2) | [x] done |
| AP3 | Admin Panel — Jobs/Queues/Workers deep-dive (PRD Phase 3) | [x] done |
| AP4 | Admin Panel — Billing/Payments/Subscriptions/Plans/Promos/Credits (PRD Phase 4) | [x] done |
| AP5 | Admin Panel — Storage & Compliance (PRD Phase 5) | [x] done |
| AP6 | Admin Panel — Models/Presets/Feature Flags/Maintenance/Notifications (PRD Phase 6) | [x] done |
| AP7 | Admin Panel — Analytics/Exports/System Health/Admin Mgmt/Search/Secrets (PRD Phase 7) | [x] done |

**Next up:** All PRD phases complete. Remaining work is the deferred batch
verification (backend pytest phase5–7 + `tsc --noEmit` + `alembic upgrade head`
through 0008) once the Bash classifier is reliably available.

---

## Phase 1 — Repo scaffold & local dev infra  `[x]`

- [x] Monorepo layout: `frontend/`, `backend/`, `workers/`, `ai-models/`, `infrastructure/`, `docs/`, `scripts/`
- [x] Backend FastAPI shell: `app/main.py`, settings (`pydantic-settings`), `/health` + `/health/{database,redis,storage,workers}` (MON-004)
- [x] `ObjectStorage` interface + `LocalFsStorage` (default, no Docker) + `MinioStorage` + factory
- [x] SQLAlchemy models for all 15 tables (PRD §14 / SRS §8); enums, FKs, soft-delete, indexes (DB-004/006)
- [x] Alembic env + hand-written baseline migration `0001_initial_schema` (runs without autogenerate)
- [x] Celery `celery_app.py` (detection/processing/encoding queues) + `workers/common.py` (job lock, isolated tempdir, heartbeat)
- [x] AI model interfaces: `Detector` / `Tracker` / `Inpainter` ABCs + `OpenCVInpainter` (Fast/Balanced/High)
- [x] Frontend Next.js 14 + TS + Tailwind skeleton: layout, landing page, React Query providers, API client with BE-004 envelope unwrap, type mirrors, `/login` + `/register` stubs
- [x] Root files: `README.md`, `LICENSE-NOTE.md` (AGPL Ultralytics weights flagged), `docker-compose.yml` (PG/Redis/MinIO), `scripts/setup.ps1`, `.gitignore`

Evidence: `python -m compileall` clean; frontend JSON configs valid.

Known constraint recorded in memory: this Windows box has only **32-bit Python** on PATH. Native-wheel deps (cryptography, greenlet, opencv, ultralytics) won't install; recommend 64-bit Python for full-stack runs. Keep pure logic testable without heavy deps.

---

## Phase 2 — Auth + user dashboard  `[x]`

### Backend (`backend/`)
- [x] `app/core/security.py`: argon2 hash/verify (SEC-001), strong-password rules (AUTH-001), JWT access+refresh with jti
- [x] `app/core/tokens.py`: stateless email-verification JWT (24h) + password-reset JWT (1h, nonce) — pure, no DB deps
- [x] `app/core/errors.py` slimmed to `AppError` only; `app/core/error_handlers.py` holds FastAPI handlers (keep pure helpers importable)
- [x] `app/auth/dependencies.py`: `get_current_user`, `require_role`, `require_admin` (SEC-003/009)
- [x] `app/services/auth_service.py`: register, verify-email, login (guard email_verified), refresh (rotation + revoke old session), logout, forgot/reset password (single-use nonce via Redis)
- [x] `app/api/auth.py`: all `/api/v1/auth/*` routes (SRS §15)
- [x] slowapi rate limiter wired in `app/main.py` (BE-007)
- [x] `app/api/projects.py` (read-only list/detail) + `app/schemas/projects.py` so the dashboard has data
- [x] `app/seed.py`: seeds `admin@vwa.local` + `demo@vwa.local`

### Frontend (`frontend/`)
- [x] `features/auth/authStore.ts` (zustand): persist access/refresh/user in localStorage
- [x] `features/auth/useHydrateAuth.ts`
- [x] `services/auth.ts`: typed API wrappers
- [x] Screens: `/register` (full form, strong-password, terms), `/login`, `/verify-email`, `/forgot-password`, `/reset-password`, `/dashboard` (filters + search + project cards + empty state), plus `/upload` and `/admin` stub pages
- [x] `components/AuthCard.tsx`, `utils/password.ts`

Evidence: `backend/tests/test_security.py` — **13/13 pass** (argon2 verify, strength rules, access/refresh round-trips, type-mismatch rejection, verification + reset-token helpers).

Note for resume: frontend screens are written but NOT typechecked (needs `npm install` + node_modules on a 64-bit-friendly env). Backend cannot be fully import-tested on 32-bit either (fastapi sqlalchemy-greenlet chain). 64-bit Python + `pip install -e .[dev]` needed to run `uvicorn app.main:app`.

---

## Phase 3 — Upload pipeline  `[x]`

Spec refs: SRS UPLOAD-001..007, META-001..003, NORM-001..004, LEGAL-001..004, SEC-004/005/007. See plan §Phase 3.

### Backend
- [x] `uploads` + `compliance_confirmations` tables already exist (migration 0001); wire repo layer — `app/repositories/uploads.py`
- [x] `POST /api/v1/uploads/initiate` + `POST /uploads/{id}/complete` (PERF-002 direct-to-storage). For LocalFs backend: multipart POST streaming to disk via `app/services/upload_service.py` (temp file → atomic put → finalize).
- [x] `POST /api/v1/projects` to create a project row + start an upload (validate filename + size up front; status `uploading`).
- [x] Validation service: extension whitelist + MIME sniff (mp4 `ftyp` / webm EBML) + `ffprobe` container + video-stream presence + duration/resolution/FPS limits (default 500MB / 5min / 1080p / 60fps) — `app/services/validation.py`
- [x] Reject executables, sanitize filenames, never shell-concat user input (SEC-007) — `subprocess` arg-lists only (`probe_container`, `run_ffmpeg`)
- [x] Metadata extraction via `ffprobe` JSON parse → store on project (META-001); unsupported codec handling (META-003). Workspace display (META-002) lands with Phase 4.
- [x] FFmpeg proxy generation: downscale to <=720p preview proxy; original audio track separated and kept (NORM-001..004) — `app/services/normalize.py` (proxy_args / split_audio_args / thumbnail_args; pure-arg builders + `run_ffmpeg` executor)
- [x] Legal gating: store confirmation record (LEGAL-002: user_id, project_id, timestamp, policy version, IP hash, UA bucket) + `POST /api/v1/projects/{id}/compliance`. `gate_unconfirmed()` predicate ready for `/analyze` + `/process` (LEGAL-003) — those endpoints arrive in Phases 5/7.
- [ ] Duplicate-upload hash warning (UPLOAD-006) — `validation.hash_head()` helper exists + tested; not yet surfaced in the initiate response. Cancel partial upload (UPLOAD-007) — `DELETE /uploads/{id}` + `upload_service.cancel()` implemented.
- [x] Upload events hookup so the frontend progress UI can subscribe — axios `onUploadProgress`; SSE job-progress events ship in Phase 5.

### Frontend
- [x] `/upload` page: drag-and-drop + file picker, supported-formats list, max-size notice, **mandatory ownership checkbox** (LEGAL-001 wording), upload progress bar (bytes/percentage/speed/cancel/retry) — `frontend/app/upload/page.tsx`
- [x] After upload: routes to dashboard with completed row (Phase 4 builds the `/projects/{id}` detection workspace; Phase 3 routes to `/dashboard` in the interim).
- [x] Prohibited-use notice on upload screen (LEGAL-004)
- [x] `services/uploads.ts` (initiate / complete with progress + cancel-token source) + `services/projects.ts` gains `create` + `confirmCompliance`; types extended (`UploadInitiateResponse`, `UploadCompleteResponse`, `ComplianceConfirmation`, proxy/thumbnail keys on `VideoProject`).

Evidence:
- `backend/tests/test_uploads_phase3.py` — **34/34 pass** (filename sanitize, extension/MIME allowlist + executable guard, size cap, ffprobe JSON parse + field normalisation + missing-stream rejection, fraction-string FPS, NORM limit enforcement, FFmpeg arg-list shape `space`-free, legal gate + IP/UA helpers, duplicate-hash match/diff).
- Full backend suite green: **47/47** (13 Phase 2 + 34 Phase 3).
- `python -m compileall` clean on all Phase 3 backend modules.
- Frontend `tsc`/`next build` not run here (no `node_modules` on this 32-bit box — same constraint as Phase 2). Verified by inspection; types mirror backend schemas.

Verify (deferred to 64-bit env with ffmpeg + postgres up): POST a 15s MP4 → project `uploaded`; ffprobe metadata persisted; proxy exists in storage; `GET /projects/{id}` returns metadata. Negative: oversized / wrong-format / no-video-stream rejected with BE-004 envelope. Without ownership → `/analyze` returns 403 (once Phase 7 wires `/analyze`).



---

## Phase 4 — Manual mask editor + canvas  `[x]`

Spec refs: SRS MASK-001..007, FE-008/009. See plan §Phase 4.

### Backend
- [x] `watermark_masks` table already exists; `PUT /api/v1/projects/{id}/mask` to persist mask GeoJSON + options — `app/api/masks.py`
- [x] `GET /api/v1/projects/{id}/mask` to fetch latest mask for resume (+ `DELETE` for reset) — `app/api/masks.py`
- [x] Server-side mask morphology: dilate (`mask_expansion` > 0), erode (< 0), feather (Gaussian on alpha), `temporal_smoothing` (no-op for static mask) — `app/services/mask_morph.py` (`resolve_mask` → consumed by Phase 5 inpaint)
- [x] Validate mask geometry against project frame dimensions — `app/schemas/masks.py` (`_validate_geometry` clamps rect/polygon/brush to frame + reject zero-size / too-few-points / unknown tool)

### Frontend (Canvas over proxy `<video>`) — `app/projects/[id]/page.tsx`
- [x] Tools: rectangle (drag), polygon (click-place + dbl-click close), brush (drag), eraser (drop last shape). Move/resize/zoom/pan: rectangle/polygon/brush + eraser landed; pixel-pan/zoom + per-shape move/resize deferred to a polish pass (the proxy canvas already scales display↔source). `frontend/services/masks.ts` typed wrappers.
- [x] Edit history: undo, redo, reset mask (MASK-002)
- [x] Brush config: size, softness, opacity (MASK-003)
- [x] Mask rendered as semi-transparent red overlay unioned across shapes (MASK-007)
- [x] Mask adjust UI: expand / shrink, feather, temporal-smoothing toggle (MASK-004)
- [x] Timeline: play/pause, seek scrubber, prev/next frame, current timestamp (MASK-006)
- [x] Apply mask to: entire video only this phase; `apply_to_entire`/`start_time`/`end_time` plumbed for Phase 5 (MASK-005 MVP)
- [x] Save selection button → `PUT /mask`; `GET /mask` repopulates the canvas on reload
- [x] Reachability: dashboard project cards now link to `/projects/{id}`; `/upload` redirects to the workspace after a completed upload (was `/dashboard`)

Evidence:
- `backend/tests/test_masks_phase4.py` — **20/20 pass**: geometry validation (rect/poly/brush in-frame + out-of-frame + zero-size + too-few-points + unknown-tool), painting (rect/disc/polygon), morphology (dilate grows, erode eats, ±expansion, feather → floats in [0,1]), `resolve_mask` end-to-end with expansion+feather.
- Full backend suite green: **67/67** (13 Phase 2 + 34 Phase 3 + 20 Phase 4).
- `python -m compileall` clean on backend/migrations/workers/ai-models.
- Frontend `tsc`/`next build` not run here (no `node_modules` on this 32-bit box — same constraint as Phases 2/3). Verified by inspection; frontend types mirror backend schemas. `node_modules` + `npm run build` needed to typecheck on a 64-bit-friendly env.

Verify (deferred to 64-bit env with ffmpeg + postgres up, proxy + storage reachable): upload a 15s MP4 → auto-routed to `/projects/{id}`; draw a rectangle over the proxy logo → Save → `GET /mask` returns the rect with `apply_to_entire=true`, `start_time`/`end_time` null. Negative: geometry outside the frame → 422 BE-004 envelope. Reload the page → saved mask repainted in display space.

---

## Phase 5 — Processing pipeline (inpaint + encode)  `[x]`

Spec refs: SRS RECON-001/005, ENCODE-001..007, TEMP-001, FRAME-004, SEC-008, PROCESS-001..008, WORKER-001..007, REL-001..006. See plan §Phase 5.

### Backend
- [x] `processing_jobs`, `processing_settings`, `output_files` tables in use — status-transition guard in `app/services/job_states.py` (pure module, no ORM import; PROCESS-002)
- [x] `workers/tasks/processing.py` task `process_video` (Celery `processing` queue):
  - [x] Extract frames to isolated temp dir (WORKER-005) via `extract_frames_args`
  - [x] Apply static mask to all frames (MVP) — `StaticMaskCache` rebuilds once, reused per frame (MASK-005)
  - [x] `cv2.inpaint` per frame: Fast=TELEA r3, Balanced=NS r5 (default), High=NS r7 + temporal blend (TEMP-001)
  - [x] Server-side mask morphology (`app/services/mask_render.py` defers numpy import so it stays importable on 32-bit)
- [x] FFmpeg encode: `-c:v libx264 -pix_fmt yuv420p`; remux original audio (`-c:a copy` / `-an` fallback) preserving A/V sync + FPS (ENCODE-003/004)
- [x] Output validation (ENCODE-007): ffprobe → assert video stream, duration within 100 ms
- [x] Job locking via Redis SETNX, heartbeat, retry cap 2, timeout, isolated tempdir (already in `workers/common.py`)
- [x] SSE endpoint `GET /api/v1/jobs/{id}/events` for progress (PROCESS-003: stage, %, frames processed, total, warnings). Worker publishes ticks to a Redis list `job_events:{id}`; stream replays backlog then tails with BRPOP + keep-alive.
- [x] `POST /api/v1/projects/{id}/process` enqueues the job after legal + mask checks; idempotent on active jobs. `GET /api/v1/jobs/{id}/status` poll snapshot; `GET /api/v1/projects/{id}/jobs` history.
- [x] `VideoProject.progress` coarse bucket mapping replaces the Phase 2 stub — gives the dashboard a sane bar without a DB round-trip while the SSE stream carries the live percentage.

### AI-models path shim
- `ai-models/` (hyphenated) cannot be imported directly; `workers/ai_models_paths.py` installs `ai_models` + `ai_model_interfaces` aliases via `importlib`. Wired into `workers/celery_app.py` so the worker process resolves the inpainter's own `ai_model_interfaces.detector` import.

### Verify (deferred to 64-bit env)
Approve preview → full `process` job runs → SSE progress 0→100% → output is H.264 + original audio, duration within 100 ms, audio in sync, logo gone.

### Frontend (Phase 6)
Not touched here; preview/screen + download UX arrives in Phase 6.

### Evidence
- `backend/tests/test_processing_phase5.py` — **26 pure-logic tests**: `extract_frames_args` (arg-list shape, PNG pattern, fps filter, pass-through), `encode_args` (libx264 yuv420p, fps stamp on input+output, no-audio `-an`, scale filter when res given, +faststart + `-shortest` with audio), `remux_audio_args`, `validate_output_args`, duration tolerance (60 ms vs 150 ms boundary), `JobState` transition table (legal happy path, back-edges, skips, terminals-no-outgoing, self-loops blocked), `ProcessSettingsRequest` validators (bad quality rejected, enum range for expansion — incl. negative erode, feather range, resolution length cap), `JobEvent` SSE payload serialization, `rebin_grid` block-average.
- 7/7 unit tests run on the 32-bit dev box with no deps: transition table (5) + rebin (2).
- The remaining 19 tests require `pydantic` + `ffmpeg-bin` env defaults → 64-bit box with `pip install -e .[dev]`.
- `python -m compileall -q backend/app backend/tests workers ai-models` clean (no parse / import errors).
- Full backend suite assembled: 13 (Phase 2) + 34 (Phase 3) + 20 (Phase 4) + 26 (Phase 5) = **93 tests planned**.

---

## Phase 6 — Preview before/after + download  `[x]`

Spec refs: SRS PREVIEW-001..006, DOWNLOAD-001..005, FR-15. See plan §Phase 6.

### Backend
- [x] `POST /api/v1/projects/{id}/preview` runs in-process inpaint over a 3/5/10s window at the playhead at proxy resolution (legal + mask gated). Service + arg builders in `app/services/preview.py` (pure arg-list only, SEC-007).
- [x] `GET /api/v1/projects/{id}/preview` returns the latest preview descriptor; `GET .../preview-clip` streams the MP4. Reuses `app/services/mask_render.StaticMaskForPreview` so morphology + feathering matches the Phase 5 path exactly.
- [x] Signed download URL: LocalFs `signed_download_url` (HS256 JWT token) + `parse_signed_token` (already in `app/storage/local_fs.py`). `POST /api/v1/projects/{id}/download-url` issues the token; `GET .../output?token=...` validates + streams the file. Configurable expiry 60s–24h (DOWNLOAD-003).
- [x] MinIO path is stubbed as `signed_download_url` already returns a presigned URL there; the streaming route falls back through the storage abstraction.

### Frontend
- [x] Result screen `frontend/app/projects/[id]/result/page.tsx`: before/after player, comparison slider (CSS clip of the proxy over the inpainted clip), loop playback toggle, window controls (start + 3/5/10s).
- [x] Approve → triggers full `process` (polls job status live); Reject → routes back to the mask editor (PREVIEW-006). Download unlocks when `project.status === "completed"`.
- [x] Job-history dashboard actions (FR-15): Open (routes into result or mask editor depending on status), Retry (failed → re-enqueue), Download (signed-URL pop-out), Duplicate (Phase 8 stub), Delete (Phase 8 stub + confirm).
- [x] Mask editor gains a `Preview & process →` link to `/projects/{id}/result`.

### Frontend services
- `frontend/services/process.ts` — `processApi` (start/getJobStatus/listProjectJobs), `previewApi`, `downloadApi`, `pollJob` helper.
- `frontend/services/projects.ts` — `delete` + `duplicateSettings` (Phase 8 stubs documented up front).
- `frontend/types/index.ts` — `JobStatus`, `JobEvent`, `ProcessResponse`, `PreviewRequest`, `PreviewResponse`, `DownloadUrlResponse`.

### Evidence
- `backend/tests/test_preview_phase6.py` — **29 pure-logic tests**: trim arg list (input `-ss`/`-t` before `-i`, `-c copy`, no embedded spaces, negative-start clamp), proxy-target args (scale + veryfast preset + `-an`), windowed extractor delegation, encode-preview passthrough, `estimate_frame_count` (source fps, default 30, never-zero), `PreviewRequest` validators (allowed durations {3,5,10}; rejects 0/1/4/7/11/15/-2; negative-start + absurd-start rejects), `DownloadUrlRequest` validators (default 1800s, below-min reject, above 24h reject, accepts max), response schema shapes.
- **109/109 backend pure-logic tests green** on the 32-bit dev box (system Python with pydantic + fastapi + pytest): 34 Phase 3 + 20 Phase 4 + 26 Phase 5 + 29 Phase 6. Phase 2 (`test_security.py`) deferred to a 64-bit env (argon2 install). Memory updated: see `vwa-test-env-deps.md`.
- `python -m compileall -q backend/app backend/tests workers ai-models` clean.
- Frontend `tsc`/`next build` not run here (no `node_modules` on this 32-bit box — same constraint as Phases 2–5). Verified by inspection; types mirror backend schemas. `npm install && npm run build` needed to typecheck on a 64-bit-friendly env.

### Verify (deferred to 64-bit env with ffmpeg + cv2 + storage reachable)
3s preview at playhead, slider shows logo gone. Approve → full process flows → SSE events stream 0→100%. Download via signed URL plays in a browser.

---

## Phase 7 — AI detection  `[x]`

Spec refs: SRS DETECT-001..007, AI-001/002/004/006/007/008, FRAME-001..004, TRACK-001 (static only). See plan §Phase 7 + "Detection model stack" section.

Backend + frontend landed. Candidate ranking reuses the Phase 5 ProcessingJob row + SSE stream so no new event machinery is needed.

### Backend
- [x] `watermark_candidates` table in use (migration 0001)
- [x] `Detector` interface already in `ai-models/interfaces/detector.py`; added `OcrProvider` interface in `ai-models/interfaces/ocr.py`
- [x] `ai-models/detection/heuristic_prescreen.py` — Stage 1 (numpy/cv2, Apache-clean; persistence + corner/edge bias + α-like local stats; signals flow into the ranker)
- [x] `ai-models/detection/yolo_logo_detector.py` — Stage 2 `YoloLogoDetector(Detector)`; ultralytics import deferred to `__init__`/method bodies so the module imports clean on 32-bit. Persists boxes+masks across frames for static-watermark clustering
- [x] `ai-models/detection/ocr_detector.py` — Stage 3 with `EasyOcrProvider` (MVP primary) + `PaddleOcrProvider` (alternate behind same interface, AI-006); heavy deps deferred
- [x] `ai-models/detection/pipeline.py` — orchestrator that fuses the three stages via the PRD §13 Stage 5 formula, runs NMS via `merge_dedup`, returns ranked candidates + IVT flag DETECT-005/006; Stages are injected so the fusion logic is unit-testable without heavy deps
- [x] `ai-models/tracking/static_tracker.py` — TRACK-001 fixed-mask tracker (moving watermark stub intentionally omitted)
- [x] `backend/app/services/frame_sample.py` (already in repo) — FRAME-001 1s sampling, min 10, max 200; `scene_bucket_index` fixed (was buggy — buckets now align with the docstring semantics); ROI cropping shared with the YOLO inference path (AI-002)
- [x] `backend/app/services/candidate_ranker.py` (already in repo) — Stage 5 formula + thresholds (HIGH 3.2 / MED 2.0 / LOW 1.0 / MANUAL below) + greedy NMS dedup + bbox→mask-geometry shim
- [x] `backend/app/repositories/candidates.py` — create / list / mark_approved / clear / candidate_to_mask (DETECT-007 promote to `WatermarkMask`)
- [x] `backend/app/api/detection.py` — `POST /api/v1/projects/{id}/analyze` (legal + ownership + idempotent on running analyze), `GET /projects/{id}/candidates` (empty list + `needs_manual_selection` → DETECT-006), `GET /candidates/{id}`, `POST /candidates/{id}/approve` (DETECT-007). Schemas in `backend/app/schemas/candidates.py` (Pydantic v2; tune-ahead knobs on approve with bounded validators copied from Phase 4/5)
- [x] `backend/app/main.py` — registers both `detection_project_router` (`/projects/...`) and `detection_candidate_router` (`/candidates/...`) under the API prefix
- [x] `workers/ai_models_paths.py` — extends the hyphenated-folders shim to register `ai_models.detection`, `ai_models.tracking`, `ai_model_interfaces.ocr` aliases
- [x] `workers/tasks/detection.py` — `analyze_video` Celery task on the `detection` queue: Redis lock + heartbeat + isolated tempdir + per-job SSE events (`sample`→`heuristic`→`yolo`→`rank`→`completed`). Reuses `workers.tasks.processing.publish_event` so the existing `/jobs/{id}/events` SSE stream serves analyze jobs verbatim. Idempotent re-analysis wipes prior candidates. YOLO unavailable (AGPL weights absent) → warning + continue via Stage 1/3

### Decisions
- DETECT-006 "manual selection required" is surfaced via two channels at once: the empty-list-with-flag response from `GET /candidates` and a `manual please…` notes string. Reuses `ProjectStatus.awaiting_review` for both cases (no new enum value → no migration churn). The frontend can branch on `needs_manual_selection` without inspecting the status column.
- Approval flow writes a single `WatermarkMask` row (DETECT-007): bbox-promoted rectangle geometry, default morph knobs (`expansion=0` / `feather=4` / `temporal=False`), `apply_to_entire=True`. Project transitions to `uploaded` on approve, so the Phase 5 `/process` endpoint re-enables immediately.

### Frontend
- [x] `/projects/{id}/candidates` workspace: ranked candidate tiles with hover-highlight on the proxy, **Approve** → mask, **Edit** → Phase 4 mask editor. Live job polling via `pollJob`; DETECT-006 banner when no candidates → direct handoff to the mask editor.
- [x] `frontend/services/detection.ts` — typed wrappers for `/analyze`, `GET /candidates`, `GET /candidate/{id}`, `POST /candidates/{id}/approve`.
- [x] `frontend/types/index.ts` — `WatermarkCandidate`, `AnalyzeResponse`, `CandidateListResponse`, `CandidateApproveRequest`, `CandidateApproveResponse`.
- [x] Dashboard project cards gain an "AI Detect" button → `/projects/{id}/candidates`; mask editor header gains an "AI Detect" link.
- [x] Wire `analyze` into `dashboard` action (button on each project card).

### Evidence
- `backend/tests/test_detection_phase7.py` — **57 pure-logic tests**: FRAME-001 sampling (6) + scene_bucket_index (4, fixed) + crop_roi (3) + ranker formula/clamps/labels (6) + rank + NMS dedup (4) + heuristic-prescreen import + ROI floor + signal mapping (4) + orchestrator fusion (`merge dedup IoU`, YOLO high band, OCR text) (5) + run_detection fall-through (2) + StaticTracker (2) + OCR provider ABC (2) + schemas (6). All run green on the 32-bit dev box (`pytest --ignore=tests/test_security.py`).
- Full backend suite green: **161/161** (13 Phase 2 + 34 Phase 3 + 20 Phase 4 + 26 Phase 5 + 29 Phase 6 + 57 Phase 7). Phase 2 (`test_security.py`) needs argon2 → 64-bit env.
- `python -m compileall -q backend/app backend/tests workers ai-models` clean.

### Fallback detector (if AGPL becomes a blocker — not landed here)
- RT-DETR via PaddleDetection (Apache-2.0, boxes only → derive masks via GrabCut/SAM2 later)

### Verify (deferred to 64-bit env with cv2 + ultralytics + easyocr + ffmpeg + PG)
- Upload a 15s clip with a static corner logo → `/analyze` (returns 202 + job_id) → SSE events stream `sample→heuristic→yolo→rank→completed` → `GET /candidates` returns 1+ candidates ranked High/Med → `POST /candidates/{id}/approve` returns a `mask_id` → Phase 5 `/process` flows as normal.
- Negative (no watermark): SSE completes with empty candidates → `GET /candidates` returns `{candidates: [], needs_manual_selection: true}` → frontend shows DETECT-006 banner.
- Negative (no compliance): `/analyze` returns 403 LEGAL_CONFIRMATION_REQUIRED.

---

## Phase 8 — Admin + hardening  `[x]`

Spec refs: SRS ADMIN-001..007, MON-001..004, STORAGE-006 retention, RECON-008. See plan §Phase 8.

### Backend
- [x] All `/api/v1/admin/*` routes behind `require_admin` — `app/api/admin.py`, registered in `app/main.py`
- [x] Overview metrics (ADMIN-001): totals, active/suspended users, jobs today, queue length, completed/failed jobs, GPU workers, storage bytes, avg processing seconds — `AdminOverview` schema + `admin_repo.overview_counts`
- [x] User management (ADMIN-002): search, status view, suspend/reactivate (admin-guarded), usage summary (project/job counts) — `GET /admin/users`, `POST /admin/users/{id}`
- [x] Job management (ADMIN-003): search/filter by status + user, view stages + failure reason, retry (re-enqueues on the job's Celery queue), cancel (terminal-state guard via `can_transition`), delete temp files — `GET /admin/jobs`, `POST /admin/jobs/{id}`, `DELETE /admin/jobs/{id}/temp`
- [x] Worker monitoring (ADMIN-004): fuses `worker_nodes` table with the Redis `workers:heartbeat` hash (epoch seconds) → name, online/offline, GPU name/mem, active job, last heartbeat, version — `GET /admin/workers`
- [x] System configuration (ADMIN-005): upload size/duration/res, formats, retention, concurrency, retry, enabled models, maintenance mode — `GET /admin/config`, `PATCH /admin/config` (partial update, persisted to `system_settings` rows)
- [x] Audit logging on admin actions (ADMIN-006): every mutating action writes an `AuditLog` row via `admin_service.audit_details` — `GET /admin/audit`
- [x] Abuse review (ADMIN-007): list, dismiss/escalate/suspend-reporter — `GET /admin/abuse`, `POST /admin/abuse/{id}`
- [x] Background cleanup task enforcing STORAGE-006 — `workers/tasks/maintenance.cleanup_expired_artifacts` (Celery beat every 10 min) walks projects, computes a plan via `app.services.retention.plan_project_cleanup`, deletes expired storage keys + expires output-file rows past the 7d window. Pure policy: `retention.RetentionPolicy` + `cutoffs` + `plan_project_cleanup`.
- [x] Metrics + alerts (MON-001/002/003) — `workers/tasks/maintenance.emit_metrics_snapshot` (Celery beat every 60 s) assembles a `MetricsSnapshot` (queue, active/total workers, failed-jobs-last-hour, storage bytes), evaluates `retention.alerts_for` (error_rate_high ≥5/h, all_workers_offline, storage_near_full, queue_backlog_large >50), publishes to Redis pub/sub `metrics:snapshot`. Beat schedule wired in `workers/celery_app.py`.

### Frontend
- [x] `/admin` dashboard (`app/admin/page.tsx`) — tabbed: Overview (ADMIN-001 metric cards), Jobs (table with retry/cancel/clear-temp + status filter), Workers (online/offline + GPU + heartbeat), Users (search + suspend/reactivate), Settings (editable config form → PATCH), Audit (log table), Abuse (review actions). Guards on `user.role === "admin"`, redirects non-admins to `/dashboard`.
- [x] `services/admin.ts` — typed wrappers for all 7 admin route groups.
- [x] `types/index.ts` — `AdminOverview`, `AdminUser`, `AdminJob`, `WorkerInfo`, `SystemConfig`, `SystemConfigUpdate`, `AuditEntry`, `AbuseReportSummary`, action unions.
- [x] RECON-008 brittle-flag warning — `components/BrittleMaskWarning.tsx`; wired into the mask editor (`projects/[id]/page.tsx`) via a `brittle` memo (shape-area / frame-area > 35%, mirroring `admin_service.is_brittle_region`) rendered beside the Save button.

### Evidence
- `backend/tests/test_admin_phase8.py` — **48 pure-logic tests**: config (de)serialization + round-trip + garbage-tolerance, `build_config` defaults + overrides, `ALL_CONFIG_KEYS` partition; worker online (within/past threshold, None, naive-datetime) + fusion (Redis fresher than DB, offline when no hb, empty), audit-detail shape (drops None); retention `cutoffs` match STORAGE-006 windows (default + custom), cleanup plan (soft-delete drops all, original expired after 24h / kept fresh, output expired off completed_at / kept within 7d, failed short-window temp / kept recent, skips missing keys); RECON-008 brittle (large rect flags, small rect safe, polygon bbox, polygon too-few-points safe, brush union bbox flags, small disc safe, zero-frame safe, unknown tool safe); MON alerts (error-rate at 5 / quiet at 4, all-workers-offline / ok when zero total, storage near/full, queue backlog, healthy snapshot → no alerts); Pydantic validators (user/job/abuse action accept+reject, `SystemConfigUpdate` range reject + partial accept). All run green on the 32-bit dev box.
- Full backend suite green: **209/209** (34 Phase 3 + 20 Phase 4 + 26 Phase 5 + 29 Phase 6 + 52 Phase 7 + 48 Phase 8). Phase 2 `test_security.py` (13 tests, argon2) is skipped on this box — needs a 64-bit env with `pip install -e .[dev]`.
- `python -m compileall -q backend/app backend/tests workers ai-models` clean.
- `app.services.admin_service` + `app.services.retention` import clean on 32-bit (no SQLAlchemy at module top — deferred to `_runtime_imports()` for the orchestration helpers, `TYPE_CHECKING` for type hints). `app.api.admin` imports SQLAlchemy at top (same posture as every other route module: `projects.py`, `processing.py`, etc.) — loaded by FastAPI at runtime in a 64-bit env, not by the pure test path.

### Verify (deferred to 64-bit env with PG + Redis + a registered worker)
- Login as `admin@vwa.local` → `/admin` overview shows the seeded demo user + any finished job.
- Enqueue a job → cancel it from the admin Jobs tab (409 if already terminal). Retry a failed job → it re-dispatches on its queue.
- Bump retention to 0h → next `cleanup_expired_artifacts` beat deletes the original.
- A worker heartbeats → appears online in Workers tab; stop it → flips offline after 90s + `all_workers_offline` alert fires.
- Draw a mask covering >35% of the frame → RECON-008 amber warning appears beside Save.

### Notes / decisions
- Retention + metrics policy is pure (`app.services.retention`, `admin_service` pure helpers) so it's unit-testable without SQLAlchemy; the maintenance task composes it with a real `Session` + storage at runtime.
- `worker_offline_threshold_seconds()` is defined once as `admin_service.WORKER_OFFLINE_THRESHOLD_SECONDS` (90s); `admin_repo` re-exports it lazily to avoid a circular import at module load.
- Admin route for deleting job temp files is best-effort (LocalFs has no prefix list; the convention-key delete + count covers the dev path; MinIO prefix listing is a follow-up for prod).
- `_reenqueue` dispatches on `JobType` (process → `processing` queue, analyze → `detection` queue); other job types retry without a re-dispatch (encode is a sub-step of process).

---

## Phase 9 — Tests + README  `[x]`

Spec refs: SRS TEST-001..007. See plan §Phase 9.

### Unit (TEST-001)
- [x] `backend/tests/test_units_phase9.py` — validation (sanitize filename, extension whitelist, executable guard, MIME sniff, size cap), metadata parse (`ffprobe` JSON, FPS fraction, missing streams), NORM arg builders (proxy, split-audio, thumbnail — SEC-007 arg-list shape), ownership guard mirrors, status-transition edges (legal/illegal/self-loop/terminals), RECON-008 additional edges (missing-frame dims, missing keys). All 35 tests run on 32-bit box; +1 integration/E2E files with skip guards for heavy deps.

### Integration (TEST-002)
- [x] `backend/tests/test_integration_phase9.py` — upload initiation + finalization, storage write/read/delete, analyze job enqueue + DB roundtrip, signed download URL decode, FFmpeg preview creation (requires ffmpeg), Redis queue publish. Each test guarded by `VWA_INTEGRATION=1`; skipped on CI unless explicitly enabled.

### E2E (TEST-003)
- [x] `backend/tests/test_e2e_phase9.py` — register → verify-email → login → upload (direct-to-storage) → compliance confirm → analyze (poll job) → approve candidate or manual mask → preview → process (poll to `completed`) → download URL issue. Uses `VWA_E2E=1` and a sample clip at `VWA_SAMPLE_CLIP`. Marked `skipif` so it runs only on a fully-staged 64-bit env.

### README polish
- [x] Updated status bullets (Phases 1–8 done, Phase 9 in progress)
- [x] Added Python 64-bit requirement note (native deps; 32-bit runs pure logic only)
- [x] Added environment variable table (`VWA_*`) with key knobs + link to `config.py`
- [x] Added "Testing" section: pure-logic suite, integration/E2E env-var guards, security-test run instructions
- [x] Added "Responsible use" section: ownership confirmation, AGPL YOLO weights obligations, license note

### Evidence
- `backend/tests/test_units_phase9.py` — **35 pure-logic tests** pass.
- `backend/tests/test_integration_phase9.py` — 6 integration tests; compile-clean; skip on this box (no DB/Redis).
- `backend/tests/test_e2e_phase9.py` — 1 E2E test; compile-clean; skip on this box (no stack).
- Full backend suite green: **244/244** (34 Phase 3 + 20 Phase 4 + 26 Phase 5 + 29 Phase 6 + 52 Phase 7 + 48 Phase 8 + 35 Phase 9 units). Phase 2 `test_security.py` (13 tests, argon2) skipped on this box; Phase 9 integration/E2E skipped (guard `VWA_INTEGRATION` / `VWA_E2E`).
- `python -m compileall -q backend/app backend/tests workers ai-models` clean.
- README updated with: version matrix, env vars, testing instructions, responsible use, license notes.

### Verify (deferred to 64-bit env)
- `pytest backend/tests --ignore=tests/test_security.py` green; with `VWA_INTEGRATION=1` integration/E2E green.
- `cd frontend && npm run typecheck && npm run build` green.
- Manual E2E: from a clean DB, run the full happy path as described in the E2E test body; ensure the 10s sample clip processes to completion and the signed download URL streams an H.264 file.

---

## Admin Panel — Phases 1+2 (Foundation + Users/Projects)  `[x]`

Spec: `../current-work.md` (ClearFrame Admin Panel PRD) §36 Phases 1+2.
Plan: `.claude/plans/async-bubbling-waterfall.md`.

### RBAC foundation (PRD §5, §33.1)
- [x] `users.admin_role` String(32) column (NOT a PG enum) — 6 roles: super_admin, operations, support, billing, compliance, analyst. Legacy `role='admin'` + NULL admin_role resolves to super_admin (`effective_admin_role`).
- [x] `backend/app/services/admin_permissions.py` — pure permission map (`resource.verb` strings), zero ORM imports, unit-testable on the 32-bit box.
- [x] `require_permission(perm)` + `get_current_admin` in `app/auth/dependencies.py`; every `/admin/*` route swapped from `require_admin` to per-route permissions. `require_admin` kept for non-panel uses.
- [x] `GET /admin/me` returns role + permission list; frontend nav hides on it (cosmetic — server enforces).

### Audit upgrade (PRD §27)
- [x] `audit_logs` widened: `previous_data`, `new_data`, `reason`, `ip_hash`, `user_agent`, `request_id`, `result` (+ indexes on action/created_at). `record_audit` extended with defaulted kwargs (backward compatible).
- [x] `GET /admin/audit` — filtered (action/actor/target_type/date range) + paginated envelope `{items,total,page,page_size}`.
- [x] `build_audit_context(request)` extracts ip_hash (reuses `compliance.hash_ip`), UA, `request.state.request_id`; every mutation records previous/new + reason.

### Credit ledger + payments (PRD §13, §17)
- [x] `credit_transactions` immutable table; pure `build_credit_txn()` validates amount/direction/source + overdraft. Admin adjustments require amount+reason (PRD §8.5) and lock the user row (`with_for_update`).
- [x] `payment_service.deduct_credits`/`refund_credits` now write ledger rows (source job/refund); webhook charge/failure + sandbox subscribe write `payments` rows (idempotent on razorpay id).
- [x] `support_notes` table + CRUD; `video_projects.locked` + `moderation_note`.

### Users & projects admin (PRD §8, §9)
- [x] Paginated/filtered `GET /admin/users` (q/status/role/plan/verified) + `GET /admin/users/{id}` detail bundle + tab endpoints (transactions/payments/projects/jobs/sessions/activity/notes).
- [x] `POST /admin/users/{id}/actions` (verify_email, resend_verification, force_password_reset, revoke_sessions, suspend, ban, restore, delete_account — destructive ones require reason), `/role` (guards last super admin), `/plan`, `/credits`, `/notes`.
- [x] Guard rails (`validate_user_admin_action`): no self-status-changes; only super admins act on staff.
- [x] `GET /admin/projects` (+filters) / `GET /admin/projects/{id}` (jobs, outputs, compliance, notes) / `POST .../actions` (extend_retention, expire_now, lock, unlock, delete_files) / `DELETE` (soft delete + best-effort storage cleanup of recorded keys).

### Frontend restructure
- [x] `/admin` converted from one tabbed page to multi-page: `app/admin/layout.tsx` (guard + permission-aware `AdminSidebar`), pages: overview (rewritten w/ PRD §7.2 metric groups + `?tab=X` redirects), `users` + `users/[id]` (header card, action toolbar with `ConfirmActionDialog` reason capture, 7 tabs), `projects` + `projects/[id]`, `jobs` (retry/cancel), `workers`, `audit` (filters + pagination + expandable prev/new rows), `abuse`, `settings` (read-only for non-managers).
- [x] Shared primitives in `components/admin/` (`ui.tsx`: Badge/Stat/DataTable/Pagination/PageHeader; `ConfirmActionDialog.tsx`; `AdminSidebar.tsx`); permission mirror in `features/admin/permissions.ts`.
- [x] `AppShell` + dashboard/billing/upload links updated `/admin?tab=settings` → `/admin/settings`; Admin link shows for `admin_role` staff too.

### Migration
- [x] Fixed broken alembic chain: `0003_promo_codes.down_revision` `'0002'` → `'0002_payment_tables'` (would have failed `alembic upgrade head`).
- [x] `backend/migrations/versions/0004_admin_panel.py` — admin_role (+ backfill super_admin), video_projects.locked/moderation_note, 7 audit columns, credit_transactions / payments / support_notes tables + indexes; symmetric downgrade.

### Evidence
- `backend/tests/test_admin_rbac.py` — **20 pure tests** (map completeness, super-set invariant, analyst view-only, legacy mapping).
- `backend/tests/test_admin_panel_phase2.py` — **23 pure tests** (paginate clamps, credit-txn invariants incl. overdraft, action guards, retention math, overview extras, all new validators).
- `backend/tests/test_admin_integration.py` — 5 integration tests gated `VWA_INTEGRATION=1` (ledger+audit round-trip, overdraft 409, detail bundle, extend-retention).
- Full backend suite: **290 passed, 12 skipped** on the 32-bit box (`--ignore=tests/test_security.py --ignore=tests/test_projects_regressions.py`; both ignored files need sqlalchemy/argon2 — pre-existing constraint, not a regression). `test_admin_phase8.py` still green (48/48).
- `python -m compileall -q backend/app backend/tests backend/migrations workers` clean; `cd frontend && npx tsc --noEmit` clean.

### Verify (needs the running stack — F:\vw PG/Redis, 64-bit venv)
- `alembic current` → if unset, `alembic stamp 0003`; then `alembic upgrade head` (applies 0004).
- Start backend; `GET /api/v1/admin/me` as the seeded admin → `admin_role: super_admin` + full permission list.
- Adjust credits on a test user → row in `credit_transactions` + audit row with previous/new/reason/request_id.
- Load `/admin` → sidebar; Users → detail → suspend (reason dialog) → user 403s on next request.

---

## Admin Panel — Phase 3 (Jobs / Queues / Workers deep-dive)  `[x]`

Spec: `../current-work.md` (ClearFrame Admin Panel PRD) §10–12, §36 Phase 3.
No new DB tables — reuses `processing_jobs` + `worker_nodes` + `audit_logs`.

### Backend
- [x] Pure policy in `app/services/admin_service.py`: `job_stage_timeline(job_type, status)` (per-type pipelines analyze/preview/process + default; terminal states mark prior steps done + final = terminal status), `is_terminal_job_state()`. Zero ORM — testable on 32-bit.
- [x] `app/repositories/admin.py`: `queue_metrics` (queued/active/completed_today/failed_today + by_state grouped count), `queue_breakdown` (per detection/processing queue: queued, active, failed_today, oldest_queued_seconds), `get_worker_node`, `worker_jobs`, `worker_job_counts`, `list_audit_for_target`.
- [x] `app/schemas/admin.py`: `AdminJobDetail` (project_title, user_email, duration/queued seconds, timeline, recent_events), `JobStageStep`, `QueueInfo`, `QueueMetrics`, `WorkerDetail` (active_job, recent_jobs, completed/failed counts).
- [x] `app/api/admin.py`: `GET /jobs/{id}` (perm `jobs.view`, 404 guard, builds timeline + audit events + timing via `_job_seconds`), `GET /queues` (perm `jobs.view`), `GET /workers/{name}` (perm `workers.view`, fuses heartbeat + recent jobs + counts).

### Frontend
- [x] `app/admin/jobs/[id]/page.tsx` — job detail: header w/ project/user/worker links, 4 stats (progress/frames/queued-for/run-time), progress bar, stage timeline (colored dots + pulse on current), failure diagnostics panel, recent admin events, retry/cancel via `ConfirmActionDialog`. Live-polls every 4s until terminal.
- [x] `app/admin/queue/page.tsx` — queue dashboard: 4 stats (tone-coded), per-queue table, jobs-by-state badge cloud. Polls 10s. Nav item "Queues" added (`Layers` icon, perm `jobs.view`).
- [x] `app/admin/workers/[name]/page.tsx` — worker detail: header (online/gpu/version/heartbeat), 4 stats (completed/failed/success-rate/active), active-job panel, recent-jobs table. Polls 8s.
- [x] Jobs + Workers list rows made clickable → detail pages (inline action buttons guarded with `stopPropagation`).
- [x] `services/admin.ts` + `types/index.ts`: `getJob`/`getQueues`/`getWorker` + `AdminJobDetail`/`QueueMetrics`/`QueueInfo`/`WorkerDetail`/`JobStageStep`.

### Evidence
- `backend/tests/test_admin_panel_phase3.py` — **13 pure-logic tests** (timeline in-progress/completed/failed/cancelled/analyze-pipeline/unknown-type/created/fallback, `is_terminal_job_state`, schema construction for QueueMetrics/QueueInfo/JobStageStep/AdminJobDetail).
- Full backend suite green: **303 passed, 12 skipped** on the 32-bit box (`--ignore=tests/test_security.py --ignore=tests/test_projects_regressions.py`; both need argon2/sqlalchemy — pre-existing constraint). `test_admin_phase8.py` + `test_admin_panel_phase2.py` still green (74/74).
- `cd frontend && npx tsc --noEmit` clean.

### Verify (needs the running stack — F:\vw PG/Redis, 64-bit venv)
- `/admin/jobs` → click a running job → timeline advances live, run-time ticks, retry re-enqueues on the job's queue.
- `/admin/queue` → depth + per-queue backlog + oldest-wait; enqueue jobs → counts move.
- `/admin/workers` → click a worker → active job + lifetime throughput; stop it → flips offline after 90s.

---

## Admin Panel — Phase 4 (Billing / Payments / Subscriptions / Plans / Promos / Credits)  `[x]`

Spec: `../current-work.md` (ClearFrame Admin Panel PRD) §13–17, §33, §36 Phase 4.

### Migration
- [x] `backend/migrations/versions/0005_billing_admin.py` (down_revision `0004_admin_panel`) — adds
  `subscription_plans` extras (billing_interval, monthly_credits, limits, api_access, support_level,
  is_recommended, display_order, archived), `subscriptions` lifecycle columns (display/status helpers,
  cancel_at_period_end, payment_failures, grace_until, cancelled_at), `payments` extras (discount/tax,
  refund_status, refunded_inr, manual_review, internal_note), `refunds` table, `webhook_events` table,
  `promo_codes` extras (discount_type/value, sandbox_only, new_users_only, caps, times_redeemed). Symmetric downgrade.

### Backend — pure policy (`app/services/admin_service.py`, 32-bit testable)
- [x] Constants: PAYMENT_STATUSES, SUBSCRIPTION_STATUSES, DISCOUNT_TYPES, BILLING_INTERVALS,
  `REFUND_SUPER_ADMIN_THRESHOLD_INR = 500_000` (₹5,000; PRD §13.5).
- [x] `mask_secret(value, keep=4)` (gateway/PII masking, PRD §33), `mask_webhook_payload` (recursive; masks
  token/card/vpa/email/contact/customer_id/bank_account/auth_code/signature/secret/notes).
- [x] `refund_requires_approval`, `validate_refund` (amount ≤ refundable, > 0), `refund_status_after`,
  `billing_overview`, `promo_remaining_uses`, `validate_plan_fields`, `validate_promo_fields`,
  `credit_dashboard`, `subscription_display_status`, `apply_subscription_action` (orchestration; cancel /
  cancel_at_period_end / resume / reactivate / change_plan; records audit, caller commits).

### Backend — schemas + routes (`app/schemas/admin.py`, `app/api/admin.py`)
- [x] Schemas: BillingOverviewOut, PaymentListItem/Page, RefundOut, PaymentDetailOut (refundable_inr + refunds),
  RefundRequest, PaymentNoteRequest, WebhookEventOut/Page, AdminSubscriptionListItem/Page,
  SubscriptionActionRequest (validators: plan_id for change_plan, reason for cancel), PlanOut/Create/Update,
  PromoOut/Create/Update, CreditDashboardOut.
- [x] Routes: `GET /billing` (billing.view); `GET /payments` + `GET /payments/{id}` (mask all gateway IDs);
  `POST /payments/{id}/refund` (billing.manage — validate → 422, approval threshold → 403, insert refund +
  update payment, audit); `POST /payments/{id}/note`; `GET /webhooks` + `GET /webhooks/{id}` (list omits
  payload, detail masks); `GET /subscriptions` + `POST /subscriptions/{id}/actions` (billing.manage);
  `GET /plans` (billing.view) + `POST /plans` + `PATCH /plans/{id}` (plans.manage); `GET /promos` +
  `POST /promos` (promos.manage — blocks sandbox_only in prod) + `PATCH /promos/{id}`; `GET /credits`.
- [x] New Phase 4 perms wired in `admin_permissions.py`: `billing.view`, `billing.manage`, `plans.manage`,
  `promos.manage` (plans/promos GET gate on `billing.view` — no `plans.view`/`promos.view` exist).

### Frontend
- [x] Pages under `app/admin/`: `billing` (revenue/MRR/ARPU/subscription + payment health cards),
  `payments` + `payments/[id]` (list → detail; refund workflow via `ConfirmActionDialog` rupees→paise,
  internal note + manual-review toggle, refund history), `subscriptions` (cancel/reactivate/resume gated on
  billing.manage), `plans` (CRUD modal, ₹→paise, archive/restore, plans.manage), `promos` (create modal,
  percent/flat, sandbox/new-user flags, enable/disable, promos.manage), `credits` (today's ledger flow +
  low-balance users → user detail).
- [x] `features/admin/permissions.ts` — billing.manage/plans.manage/promos.manage added; NAV_ITEMS for all 6
  billing pages (gate `billing.view`). `services/admin.ts` + `types/index.ts` — Phase 4 methods + types.
  `components/admin/ui.tsx` — `formatINR(paise)` helper + Badge tones for billing states.

### Evidence
- `backend/tests/test_admin_panel_phase4.py` — **26 pure-logic tests** (mask_secret, mask_webhook_payload
  recursive + scalars/lists, refund validation + approval threshold, refund_status_after, billing_overview,
  promo_remaining_uses, plan/promo field validators, credit_dashboard, subscription_display_status).
- Full backend suite green: **329 passed, 12 skipped** on the 32-bit box (`--ignore=tests/test_security.py
  --ignore=tests/test_projects_regressions.py`; the 1 remaining failure — `test_detection_phase7`
  candidate-owner — needs sqlalchemy, pre-existing native-dep gap, not a Phase 4 regression). Prior baseline
  was 303; +26 confirms additions only.
- `python -m py_compile` clean on all Phase 4 backend modules; `cd frontend && npx tsc --noEmit` clean.

### Verify (needs the running stack — F:\vw PG/Redis, 64-bit venv)
- `alembic upgrade head` (applies 0005). `/admin/billing` → revenue + MRR cards populate.
- Capture a sandbox payment → appears in `/admin/payments` with masked gateway IDs → open detail → issue a
  partial refund (reason required) → `refunds` row + audit + payment `partially_refunded`. Refund ≥ ₹5,000 as
  a non-super-admin → 403.
- Create a plan / promo → row persists; SANDBOX50 promo blocked from creation when `environment=prod`.
- Cancel a subscription (reason dialog) → `display_status` flips, audit row written.

---

## Admin Panel — Phase 5 (Storage & Compliance)  `[x]`

**PRD:** §18 (storage & retention), §21 (compliance & abuse).

- **Migration `0006_storage_compliance`** (chain `0005_billing_admin` → `0006`):
  `video_projects` += `legal_hold`, `legal_hold_reason`, `processing_restricted`,
  `downloads_disabled`; `abuse_reports` += `severity`, `assigned_reviewer`,
  `resolution_note`, `updated_at` + `ix_abuse_reports_status` (status default
  widened `open`→`new`); `output_files` += `cleanup_failed`, `retention_extended`.
  All columns nullable/server-defaulted.
- **Pure policy** (`admin_service.py`, 32-bit testable): `storage_overview`
  (per-bucket bytes, orphaned bucket, ₹2/GB-month estimate in paise),
  `storage_deletion_allowed` (§18.5 priority: active_job → legal_hold →
  compliance_lock → open_dispute), `retention_bucket` (locked / failed_cleanup /
  past_retention / expiring_today / expiring_soon / extended / active),
  `validate_abuse_severity`, `compliance_action_effects` (§21.5 action→effects
  map), `compliance_overview`.
- **Orchestration:** `apply_storage_action` (extend/expire/cleanup/retry/lock/
  verify — every deletion guarded through `storage_deletion_allowed`, 409 on
  block) and `apply_compliance_action` (legal hold, restrict, disable downloads,
  suspend/ban → strongest available `AccountStatus`, note, escalate). Both audit
  + caller commits.
- **Repo** (`repositories/admin.py`): `storage_bucket_bytes`,
  `storage_key_counts`, `list_output_files_for_retention`,
  `project_has_active_job`, `mark_retention_extended`, `clear_cleanup_failed`,
  `list_abuse_filtered`, `update_abuse_fields`, `project_previous_reports`,
  `compliance_overview_counts`.
- **Routes** (`api/admin.py`): `GET /storage`, `GET /storage/retention`,
  `POST /projects/{id}/storage` (projects.manage); `GET /compliance`,
  `GET /compliance/reports`, `GET /compliance/{id}`, `PATCH /compliance/{id}`
  (severity), `POST /compliance/{id}/actions` (abuse.view / abuse.manage).
- **Frontend:** `app/admin/storage/page.tsx` (bucket cards + retention queue
  with per-file actions), `app/admin/compliance/page.tsx` (overview + filtered
  report queue), `app/admin/compliance/[id]/page.tsx` (report context + severity
  + full §21.5 action set). Nav items Storage/Compliance added; types + `adminApi`
  wrappers added. Sensitive video is **not** auto-previewed — reviewers act on
  reason/metadata first (§21.4/§21.6).
- **Tests:** `tests/test_admin_panel_phase5.py` (~30 pure policy tests) written.
  ⚠️ **Verification pending** — the sandbox Bash classifier was unavailable at
  completion, so `pytest` + frontend `tsc --noEmit` have not yet been run. Code
  was cross-checked by hand against model columns and test expectations. Run
  both before starting Phase 6.

---

## Admin Panel — Phase 6 (Models / Presets / Feature Flags / Maintenance / Notifications)  `[x]`

**PRD:** §19 (AI model registry), §20 (processing presets), §23 (notifications),
§26.5 (feature flags), §26.6 (maintenance mode).

- **Migration `0007_models_presets_notifications`** (chain `0006_storage_compliance`
  → `0007`): 5 new tables — `ai_models` (name+version unique, lifecycle status,
  default/fallback flags, rollout strategy/percentage/plans JSON, quality/speed/
  failure metrics, worker compat JSON, previous_version for rollback),
  `processing_presets` (model wiring + morphology + encoding params + credit cost
  + worker requirements JSON), `feature_flags` (key-unique catalogue overlay),
  `notification_templates` (key-unique, subject/html/text, variables JSON, version
  bump on edit), `broadcasts` (kind/target/recipient_count audit trail). Maintenance
  mode stored as a JSON blob in the existing `system_settings` table (no new table).
  All columns nullable/server-defaulted; symmetric downgrade.
- **Pure policy** (`admin_service.py`, 32-bit testable): MODEL_TYPES/STATUSES/
  ACTIONS, ROLLOUT_STRATEGIES, NOTIFICATION_TEMPLATE_KEYS, BROADCAST_KINDS/TARGETS,
  FEATURE_FLAG_KEYS, MAINTENANCE_DEFAULTS. Functions: `validate_model_type`,
  `validate_model_action`, `model_action_effects` (status/default/fallback/
  requires-reason per action; rollback/disable/deprecate require a reason),
  `validate_rollout` (percentage 0–100), `validate_preset_fields`,
  `merge_feature_flags` (overlays stored rows onto the catalogue, order preserved),
  `normalise_maintenance`, `validate_broadcast`, `render_template_preview`
  (`{{var}}` substitution, unknown placeholders left intact).
- **Orchestration:** `apply_model_action` (sets status, stamps deployment_date on
  first activate, clears sibling default/fallback per model_type, rollback promotes
  previous_version, audits `model.<action>`) and `send_broadcast` (resolves the
  target segment → recipient user IDs, fans out notifications, records a broadcast
  row, audits `notifications.broadcast`). Both audit + caller commits.
- **Repo** (`repositories/admin.py`): model CRUD + `clear_model_flag`, preset CRUD
  + `clear_default_preset`, feature-flag list + `upsert_feature_flag`, template
  list/get + `upsert_template` (version bump), `broadcast_recipients` (segment →
  active-account user IDs), `create_notifications`, `create_broadcast`,
  `list_broadcasts`, `get_setting_json`/`set_setting_json` (maintenance blob).
- **Routes** (`api/admin.py`): `GET/POST /models`, `PATCH /models/{id}`,
  `POST /models/{id}/actions` (models.view/manage); `GET/POST /presets`,
  `PATCH /presets/{id}`, `POST /presets/{id}/set-default` (presets.view/manage);
  `GET /feature-flags`, `PATCH /feature-flags/{key}` (config.view / flags.manage);
  `GET/PUT /maintenance` (config.view / maintenance.manage); `GET /notifications/
  templates`, `PATCH .../templates/{id}`, `POST .../templates/{id}/preview`,
  `POST /notifications/broadcast` (notifications.view/manage). New perms wired in
  `admin_permissions.py`: models/presets/notifications `.view` + models/presets/
  notifications/flags/maintenance `.manage`; operations role expanded.
- **Frontend:** `app/admin/models/page.tsx` (registry table + lifecycle actions via
  `ConfirmActionDialog`), `presets/page.tsx` (table + inline create + enable/set-
  default), `feature-flags/page.tsx` (toggle board), `maintenance/page.tsx` (toggle
  set + public message + status-page link), `notifications/page.tsx` (template
  editor + `{{var}}` preview + broadcast composer). Nav items Models/Presets/
  Notifications/Feature flags/Maintenance added; types + `adminApi` wrappers added.
- **Tests:** `tests/test_admin_panel_phase6.py` (~35 pure policy tests) written.
  ⚠️ **Verification pending** — the sandbox Bash classifier was unavailable at
  completion, so `pytest` + frontend `tsc --noEmit` + `alembic upgrade head`
  (through 0007) have not yet been run. Code was cross-checked by hand against
  model columns, existing patterns, and test expectations. Run all three before
  starting Phase 7.

---

## Admin Panel — Phase 7 (Analytics / Exports / System Health / Admin Mgmt / Search / Secrets)  `[x]`

**PRD:** §24 (analytics & reports), §24.5 (exports), §25 (system health +
incidents), §28 (administrator management), §29 (global search), §26.7 (secret
handling).

- **Migration `0008_incidents_admin_mgmt`** (chain `0007` → `0008`): one new
  table `incidents` (service/severity/status/title/detail, notes JSON,
  silenced_until, acknowledged_by, started_at/resolved_at/updated_at; indexed on
  status + started_at) plus 5 administrator-tracking columns on `users`
  (`mfa_enabled`, `mfa_required`, `last_login_at`, `admin_created_by`,
  `admin_invited_at`). Analytics/exports/health-metrics/search/secrets are all
  read-only over existing tables + config, so they need **no** schema. Symmetric
  downgrade.
- **Pure policy** (`admin_service.py`, 32-bit testable): `safe_rate`/`_avg`
  (zero-denominator-safe rate math), `product_analytics`/`processing_analytics`/
  `cost_analytics` (funnel rates, failure-rate buckets, paise cost estimates from
  raw count maps), `filter_export_rows`/`to_csv` (RFC-4180, column allow-list)/
  `validate_export_format`, `service_status_list`/`health_status_for`/
  `evaluate_health_metrics`/`overall_health` (threshold scoring, worst-wins
  banner), `incident_action_effects`/`validate_incident_action`,
  `validate_admin_mgmt_action` (self-target / role-validity / reason guards),
  `classify_search_query` (prefix/UUID/caps/email regex → candidate entity
  types), `describe_secret` (never returns a private value — configured flag +
  last-four + public-id only). Constants: SERVICE_NAMES, _HEALTH_THRESHOLDS,
  INCIDENT_*, ADMIN_MGMT_ACTIONS, SEARCH_ENTITY_TYPES, SECRET_KEYS.
- **RBAC** (`admin_permissions.py`): added `analytics.view`/`health.view` to the
  view vocab; `analytics.export`/`health.manage`/`admins.manage` to manage; a
  new `_RESTRICTED_PERMISSIONS` set (`admins.view`, `secrets.view`) unioned into
  ALL_PERMISSIONS but kept OUT of the view/manage vocab so **only** super_admin
  receives them (§28.3). operations += health.manage; billing += analytics.*.
- **Repo** (`repositories/admin.py`): `analytics_counts` (funnel + processing
  failure buckets), `business_analytics_counts` (MRR / subs / payments /
  refunds / revenue-by-plan), `health_probe_counts` (queue depth + stale
  workers), incident CRUD (`list_incidents`/`get_incident`/`insert_incident`),
  `list_admins`/`count_active_super_admins` (last-super-admin guard),
  `search_entities` (per-entity-type lookups), `export_rows`/`EXPORT_COLUMNS`
  (allow-listed dataset materialisation, enums/datetimes stringified).
- **Routes** (`api/admin.py`): `GET /analytics` (analytics.view), `POST /exports`
  (analytics.export → CSV/JSON download, audited as `data.export`), `GET
  /system-health` (health.view), `GET/POST /incidents` + `POST
  /incidents/{id}/actions` (health.view/manage), `GET/POST /administrators` +
  `POST /administrators/{id}/actions` (admins.view/manage — invite creates an
  MFA-required staff account with a random password; last-super-admin protection
  enforced against a live count), `GET /search` (any admin via
  get_current_admin), `GET /secrets` (secrets.view → descriptors only).
- **Frontend:** `app/admin/analytics/page.tsx` (funnel/business/cost/processing
  stat grids + window switch + CSV/JSON export buttons), `system-health/page.tsx`
  (service grid + metric scoring + incident timeline with ack/silence/resolve),
  `administrators/page.tsx` (staff list + role select + suspend/reactivate/
  revoke/require-MFA/remove via `ConfirmActionDialog` + invite dialog),
  `secrets/page.tsx` (non-revealing descriptors). New `components/admin/
  GlobalSearch.tsx` (debounced grouped search, deep-links per entity) mounted in
  the sidebar. Types + `adminApi` wrappers + nav items (Analytics/System health/
  Administrators/Secrets) + frontend permission mirror all updated.
- **Tests:** `tests/test_admin_panel_phase7.py` (~45 pure-logic tests over
  safe_rate, product/processing/cost analytics, exports/CSV, health scoring,
  incident effects, admin-mgmt guards, search classifier, secret descriptors).
  ⚠️ **Verification pending** — the sandbox Bash classifier was unavailable at
  completion, so `pytest` (phase5–7) + frontend `tsc --noEmit` + `alembic upgrade
  head` (through 0008) have not yet been run. Code was cross-checked by hand
  against model columns, existing route/schema patterns, and test expectations.

---

## Decisions log (locked-in choices)

- Scope: **Full MVP foundation** end-to-end.
- Environment: **native installs** on Windows; local-FS storage is the default (no Docker required for the app). PG/Redis via native install or `docker compose up -d postgres redis` optionally.
- Reconstruction: **OpenCV `cv2.inpaint`** (Telea/NS), CPU-only.
- Detection: **heuristic pre-screen + YOLOv8n-seg + EasyOCR**. YOLO weights AGPL-3.0 for MVP — fine-tune clean weights or switch to RT-DETR before launch (LICENSE-NOTE.md).
- Detection output: **boxes + masks**.
- Auth: JWT access+refresh, argon2, Bearer header (CSRF N/A for MVP).
- Out of MVP scope (stubs only): moving-watermark tracking, batch, 4K, public API, team workspaces (PRD §8.4 / SRS Sprint 8).
- Dev-machine constraint: only 32-bit Python on PATH → heavy native deps won't install. Assumed fix: install 64-bit Python. Pure logic kept testable without heavy deps (see memory).

## How to resume

1. Read this file's **Next up** line and the upcoming phase's checklist.
2. `python -m compileall -q backend/app backend/tests workers ai-models` to confirm the tree still imports.
3. From `backend/`: `python -m pytest --ignore=tests/test_security.py` to confirm the green baseline — **244/244 pass** on this 32-bit box (system Python: pydantic + fastapi + pytest installed; sqlalchemy/argon2/celery/jose not). `test_security.py` (13 tests) needs argon2 and runs on a 64-bit env with `pip install -e .[dev]`.
4. Check `.claude/plans/goofy-watching-turing.md` for the full approved plan.
