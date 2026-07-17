# License Notes

This document tracks third-party component licenses relevant to shipping this product.

## AGPL-3.0 — Ultralytics YOLOv8 weights (action required before commercial launch)

The MVP uses `ultralytics` and the `yolov8n-seg.pt` weights for automatic
watermark detection (Phase 7). **Ultralytics YOLOv8/v11 weights and the
`ultralytics` package are released under AGPL-3.0.** AGPL-3.0 is a strong
copyleft license that can require you to release the source of a product that
incorporates these weights to its users over a network.

**Current decision (MVP / prototype):** Use the AGPL-3.0 weights now to get a
working detector fastest. This is acceptable for internal/prototype use.

**Before any commercial launch, pick one:**
1. Purchase a commercial license from Ultralytics for the YOLOv8 weights.
2. Replace the weights with a self-fine-tuned checkpoint trained on a
   **license-clean synthetic watermark dataset** (overlay known watermarks on
   sampled video frames → auto-label masks). Weights you fine-tune yourself
   starting from the AGPL checkpoint remain AGPL-licensed — so start from a
   permissively-licensed base (e.g. RT-DETR under PaddleDetection, Apache-2.0)
   and fine-tune that.
3. Swap the detector implementation for the Apache-2.0 fallback stack:
   RT-DETR via PaddleDetection (boxes only — derive masks via GrabCut/SAM2
   refinement later).

The pluggable `Detector` interface (`ai-models/interfaces/detector.py`) keeps
this a one-file replacement.

## Apache-2.0 (license-clean, safe)
- `opencv-python` — inpainting + image processing
- `paddleocr` (if PaddleOCR is used) — text watermark channel
- `easyocr` (fallback OCR) — text watermark channel
- FastAPI, SQLAlchemy, Celery, Redis, Pydantic, boto3/minio

## Verify before shipping
License terms change. Before any release, re-confirm the current licenses of:
`ultralytics`, `paddleocr`, `easyocr`, `paddlepaddle`, and dataset licenses
(OpenLogo / LogoDet-3K are historically research/non-commercial and should not
be relied upon for licensed product weights — the synthetic-dataset route is
the safe path).
