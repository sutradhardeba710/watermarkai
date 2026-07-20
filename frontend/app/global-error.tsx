"use client";

// Top-level fallback for errors thrown in the root layout itself. It must
// render its own <html>/<body> because it replaces the entire document.
// Complements app/error.tsx, which only covers errors below the layout.
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#07080f", color: "#fff", fontFamily: "system-ui, sans-serif" }}>
        <div style={{ minHeight: "100dvh", display: "grid", placeItems: "center", padding: "24px" }}>
          <div style={{ maxWidth: 420, width: "100%", textAlign: "center", border: "1px solid rgba(255,255,255,.1)", borderRadius: 16, padding: 32, background: "rgba(255,255,255,.03)" }}>
            <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Something went wrong</h1>
            <p style={{ marginTop: 8, fontSize: 14, lineHeight: 1.6, color: "rgba(255,255,255,.55)" }}>
              The app hit an unexpected error. Please try again.
            </p>
            {error?.digest && (
              <p style={{ marginTop: 12, fontFamily: "monospace", fontSize: 11, color: "rgba(255,255,255,.3)" }}>Ref: {error.digest}</p>
            )}
            <button
              onClick={reset}
              style={{ marginTop: 24, cursor: "pointer", border: "none", borderRadius: 12, padding: "10px 20px", fontSize: 14, fontWeight: 600, color: "#fff", background: "linear-gradient(to right,#4f7cff,#6d5ef7,#8b5cf6)" }}
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
