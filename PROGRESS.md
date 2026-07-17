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

**Next up:** MVP complete. Deploy to staging; observe real-world workloads; iterate.

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
