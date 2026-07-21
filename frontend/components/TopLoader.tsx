"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

// Branded top loading bar shown during client-side navigations.
// Blue→purple gradient matches the ClearFrame brand (see Navbar/logo).
export function TopLoader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };

  const start = () => {
    clearTimers();
    setVisible(true);
    setProgress(8);
    // Ease toward 90% while the next route loads; never reach 100 until done.
    const step = (value: number) => {
      if (value >= 90) return;
      const next = value + (90 - value) * 0.18;
      timers.current.push(
        setTimeout(() => {
          setProgress(next);
          step(next);
        }, 180),
      );
    };
    step(8);
  };

  const done = () => {
    clearTimers();
    setProgress(100);
    timers.current.push(
      setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 260),
    );
  };

  // Complete the bar whenever the resolved route (path or query) changes.
  useEffect(() => {
    if (visible) done();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, searchParams]);

  // Kick the bar off on same-origin link clicks (App Router navigations).
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const anchor = (e.target as HTMLElement)?.closest?.("a");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      const target = anchor.getAttribute("target");
      if (
        !href ||
        href.startsWith("#") ||
        href.startsWith("mailto:") ||
        href.startsWith("tel:") ||
        (target && target !== "_self") ||
        anchor.hasAttribute("download")
      )
        return;
      // External links navigate away; skip.
      try {
        const url = new URL(href, window.location.href);
        if (url.origin !== window.location.origin) return;
        // Same URL (hash-only or identical) — no route change coming.
        if (url.pathname === window.location.pathname && url.search === window.location.search)
          return;
      } catch {
        return;
      }
      start();
    };
    document.addEventListener("click", onClick, { capture: true });
    // Also cover browser back/forward.
    const onPop = () => start();
    window.addEventListener("popstate", onPop);
    return () => {
      document.removeEventListener("click", onClick, { capture: true } as EventListenerOptions);
      window.removeEventListener("popstate", onPop);
      clearTimers();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!visible) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 top-0 z-[9999] h-[3px]"
    >
      <div
        className="h-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] shadow-[0_0_12px_rgba(109,94,247,.7)] transition-[width] duration-200 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
