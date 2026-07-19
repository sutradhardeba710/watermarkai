"use client";
import { useEffect, useState } from "react";

export function useScrollSpy(sectionIds: string[]): string {
  const [active, setActive] = useState(sectionIds[0] ?? "top");
  useEffect(() => {
    const nodes = sectionIds.map((id) => document.getElementById(id)).filter((node): node is HTMLElement => Boolean(node));
    if (!nodes.length) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible?.target.id) setActive(visible.target.id);
    }, { rootMargin: "-88px 0px -55% 0px", threshold: [0.1, 0.35, 0.6] });
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [sectionIds]);
  return active;
}
