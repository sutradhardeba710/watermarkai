"use client";

import { useEffect, useState } from "react";

/**
 * SSR-safe media query hook. Returns false during server render and the first
 * client paint (so it never flips layout on hydration), then the real match.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}
