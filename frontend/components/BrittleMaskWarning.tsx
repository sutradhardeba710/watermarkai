"use client";

/**
 * RECON-008 — brittle-inpaint warning.
 *
 * Inpaint masks that cover faces/hands/high-variance regions produce visible
 * artifacts. The backend flags a mask "brittle" when it covers a large
 * fraction of the frame (the conservative MVP heuristic in
 * `app.services.admin_service.is_brittle_region`); this banner surfaces that
 * to the user so they can shrink the mask or drop the quality mode.
 *
 * `brittle` is computed by the caller (the mask editor derives it from the
 * current geometry + frame size) so this component stays presentational.
 */
export function BrittleMaskWarning({ brittle }: { brittle: boolean }) {
  if (!brittle) return null;
  return (
    <div
      role="alert"
      className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
    >
      <p className="font-semibold">Heads up — large inpaint region</p>
      <p className="mt-0.5">
        This mask covers a large part of the frame. Inpainting over faces,
        hands, or detailed texture can leave visible artifacts (RECON-008).
        Consider shrinking the mask or switching to <em>High</em> quality for
        the best result.
      </p>
    </div>
  );
}
