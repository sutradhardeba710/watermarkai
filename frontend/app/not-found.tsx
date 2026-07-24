import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Home, MessageCircle, Sparkles } from "lucide-react";

export const metadata: Metadata = {
  title: "Page not found",
  description: "The requested ClearFrame page could not be found.",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <main className="error-page relative isolate grid min-h-dvh overflow-hidden bg-[#07080f] px-5 py-8 text-[#f5f6fa] sm:px-8 lg:px-10">
      <div className="error-page__glow error-page__glow--blue" aria-hidden="true" />
      <div className="error-page__glow error-page__glow--violet" aria-hidden="true" />
      <div className="error-page__grid" aria-hidden="true" />

      <header className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between">
        <Link href="/" className="inline-flex min-h-11 items-center gap-2.5 rounded-xl pr-3 text-base font-semibold tracking-tight text-white transition-colors hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300" aria-label="ClearFrame home">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] shadow-[0_0_24px_rgba(79,124,255,.38)]"><Sparkles size={18} aria-hidden="true" /></span>
          ClearFrame
        </Link>
        <span className="hidden items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-white/45 sm:flex"><span className="h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,.8)]" />Route unavailable</span>
      </header>

      <section className="relative z-10 mx-auto grid w-full max-w-7xl place-items-center py-12 sm:py-16">
        <div className="grid w-full items-center gap-10 lg:grid-cols-[1.05fr_.95fr] lg:gap-20">
          <div className="error-page__code-wrap relative mx-auto w-full max-w-[36rem] lg:mx-0" aria-hidden="true">
            <div className="error-page__orbit" />
            <div className="error-page__frame">
              <span className="error-page__corner error-page__corner--tl" /><span className="error-page__corner error-page__corner--tr" /><span className="error-page__corner error-page__corner--bl" /><span className="error-page__corner error-page__corner--br" />
              <span className="error-page__code">404</span><span className="error-page__scan" />
            </div>
            <div className="mt-4 flex items-center justify-between px-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-white/35"><span>Frame not found</span><span>00:04:04</span></div>
          </div>

          <div className="error-page__content mx-auto max-w-xl text-center lg:mx-0 lg:text-left">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/[.06] px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">Error 404</div>
            <h1 className="mt-6 text-4xl font-semibold leading-[1.04] tracking-[-.045em] text-white sm:text-5xl lg:text-6xl">This frame slipped<span className="block bg-gradient-to-r from-cyan-200 via-[#8da8ff] to-violet-300 bg-clip-text text-transparent">out of the timeline.</span></h1>
            <p className="mx-auto mt-6 max-w-lg text-base leading-7 text-white/60 sm:text-lg sm:leading-8 lg:mx-0">The page may have moved, or the link may be incomplete. Return to ClearFrame or reach our team and we&apos;ll help you find the right path.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center lg:justify-start">
              <Link href="/" className="group inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-6 text-sm font-semibold text-white shadow-[0_12px_36px_rgba(79,124,255,.28)] transition duration-200 hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080f] active:brightness-95"><Home size={18} aria-hidden="true" />Back to home<ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden="true" /></Link>
              <Link href="/contact" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-white/15 bg-white/[.045] px-6 text-sm font-semibold text-white transition duration-200 hover:border-cyan-200/30 hover:bg-white/[.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080f] active:bg-white/[.06]"><MessageCircle size={18} aria-hidden="true" />Contact us</Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="relative z-10 mx-auto flex w-full max-w-7xl items-end justify-between text-xs text-white/35"><span>ClearFrame / Authorized video cleanup</span><span className="hidden sm:inline">Lost signal · Safe return</span></footer>
    </main>
  );
}
