"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, LayoutDashboard, Menu, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { navGroups, primaryNav, type NavGroup, type NavLink } from "./navItems";
import { scrollToSection } from "@/utils/scrollToSection";
import { useScrollSpy } from "@/hooks/useScrollSpy";
import { useMarketingAuth } from "./marketing/useMarketingAuth";

const sections = ["top", "demo", "workflow", "capabilities", "solutions", "compliance", "formats", "pricing", "faq", "resources"];

function NavButton({ link, active, onSelect }: { link: NavLink; active: boolean; onSelect: () => void }) {
  const Icon = link.icon;
  return <button type="button" onClick={onSelect} aria-current={active ? "page" : undefined} className={`flex min-h-[84px] w-full items-start gap-3 rounded-xl p-3 text-left transition hover:bg-white/[.07] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${active ? "bg-white/[.06]" : ""}`}><span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/[.06] text-cyan-200"><Icon size={16} strokeWidth={1.8} /></span><span><span className="block text-sm font-semibold text-white">{link.label}</span><span className="mt-0.5 line-clamp-2 min-h-10 text-xs leading-5 text-white/50">{link.description}</span></span></button>;
}

function DropdownMenu({ group, open, onOpen, onClose, active, onSelect }: { group: NavGroup; open: boolean; onOpen: () => void; onClose: () => void; active: string; onSelect: (link: NavLink) => void }) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [panelStyle, setPanelStyle] = useState<React.CSSProperties>({});
  const preferredRight = group.label === "Resources";
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelClose = () => { if (closeTimer.current) { clearTimeout(closeTimer.current); closeTimer.current = null; } };
  const scheduleClose = () => { cancelClose(); closeTimer.current = setTimeout(onClose, 140); };

  useEffect(() => {
    if (!open) return;
    const measure = () => {
      const trigger = triggerRef.current;
      const panel = panelRef.current;
      if (!trigger || !panel) return;
      const triggerRect = trigger.getBoundingClientRect();
      const panelRect = panel.getBoundingClientRect();
      const padding = 16;
      const naturalLeft = preferredRight ? triggerRect.right - panelRect.width : triggerRect.left;
      const left = Math.max(padding, Math.min(naturalLeft, window.innerWidth - padding - panelRect.width));
      setPanelStyle({ top: triggerRect.bottom + 8, left });
    };
    const frame = window.requestAnimationFrame(measure);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", onClose, true);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener("resize", measure); window.removeEventListener("scroll", onClose, true); };
  }, [open, preferredRight, onClose]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { const target = event.target as Node; if (!triggerRef.current?.contains(target) && !panelRef.current?.contains(target)) onClose(); };
    const esc = (event: KeyboardEvent) => { if (event.key === "Escape") { onClose(); triggerRef.current?.focus(); } };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open, onClose]);

  return <div className="relative" onMouseEnter={() => { cancelClose(); onOpen(); }} onMouseLeave={scheduleClose}>
    <button ref={triggerRef} type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => open ? onClose() : onOpen()} onFocus={onOpen} className="flex min-h-11 items-center gap-1 rounded-full px-3 py-2 text-sm font-medium text-white/65 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">{group.label}<ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} /></button>
    <div ref={panelRef} role="presentation" style={panelStyle} className={`fixed z-[60] ${group.width === "lg" ? "w-[640px]" : "w-[360px]"} max-w-[calc(100vw-32px)]`} onMouseEnter={cancelClose} onMouseLeave={scheduleClose}>
      <AnimatePresence>
        {open && <motion.div key={group.label} role="menu" initial={{ opacity: 0, y: -6, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -5, scale: .98 }} transition={{ duration: .18 }} className="rounded-2xl border border-white/10 bg-[#10121f]/[.98] p-3 shadow-[0_24px_80px_rgba(0,0,0,.5)] backdrop-blur-xl">
          <div className={`grid gap-1 ${group.columns === 2 ? "grid-cols-2" : "grid-cols-1"}`}>{group.links.map((link) => <NavButton key={link.label} link={link} active={active === link.section} onSelect={() => onSelect(link)} />)}</div>
        </motion.div>}
      </AnimatePresence>
    </div>
  </div>;
}
function MobileDrawer({ open, onClose, active, onSelect, isAuthed }: { open: boolean; onClose: () => void; active: string; onSelect: (link: NavLink) => void; isAuthed: boolean }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return <AnimatePresence>{open && <motion.aside role="dialog" aria-modal="true" aria-label="Mobile navigation" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ duration: .25, ease: [0.22, 1, 0.36, 1] }} className="fixed inset-0 z-[60] overflow-y-auto bg-[#07080f] px-5 pb-8 pt-24 lg:hidden"><div className="space-y-2">{navGroups.map((group) => <div key={group.label} className="border-b border-white/10 py-2"><button type="button" aria-expanded={expanded === group.label} onClick={() => setExpanded(expanded === group.label ? null : group.label)} className="flex min-h-12 w-full items-center justify-between text-left text-lg font-semibold text-white">{group.label}<ChevronDown size={18} className={`transition-transform ${expanded === group.label ? "rotate-180" : ""}`} /></button><AnimatePresence initial={false}>{expanded === group.label && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">{group.links.map((link) => <NavButton key={link.label} link={link} active={active === link.section} onSelect={() => onSelect(link)} />)}</motion.div>}</AnimatePresence></div>)}<NavButton link={primaryNav.pricing} active={active === "pricing"} onSelect={() => onSelect(primaryNav.pricing)} />{isAuthed ? <Link href="/dashboard" onClick={onClose} className="mt-2 flex min-h-12 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 text-lg font-semibold text-white"><LayoutDashboard size={18} /> Open dashboard</Link> : <><Link href="/login" onClick={onClose} className="block rounded-full px-3 py-3 text-lg font-semibold text-white/80">Log in</Link><Link href="/signup" onClick={onClose} className="block rounded-full px-3 py-3 text-lg font-semibold text-white/80 transition hover:text-white">Sign up</Link></>}</div></motion.aside>}</AnimatePresence>;
}

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false); const [openGroup, setOpenGroup] = useState<string | null>(null); const [drawerOpen, setDrawerOpen] = useState(false); const active = useScrollSpy(sections); const pathname = usePathname(); const router = useRouter(); const allLinks = useMemo(() => navGroups.flatMap((group) => group.links), []);
  const { isAuthed } = useMarketingAuth();
  useEffect(() => { const handler = () => setScrolled(window.scrollY > 20); handler(); window.addEventListener("scroll", handler, { passive: true }); return () => window.removeEventListener("scroll", handler); }, []);
  useEffect(() => { setOpenGroup(null); setDrawerOpen(false); }, [pathname]);
  useEffect(() => { document.body.style.overflow = drawerOpen ? "hidden" : ""; return () => { document.body.style.overflow = ""; }; }, [drawerOpen]);
  const select = (link: NavLink) => { if (link.href.startsWith("#")) { if (pathname === "/") scrollToSection(link.href); else router.push(`/${link.href}`); } else { router.push(link.href); } setOpenGroup(null); setDrawerOpen(false); };
  return <><motion.header animate={{ backgroundColor: scrolled ? "rgba(10,11,15,.92)" : "rgba(10,11,15,0)" }} transition={{ duration: .2 }} className="fixed left-0 top-0 z-50 w-full pt-[env(safe-area-inset-top)] backdrop-blur-xl"><div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between px-5 py-2 sm:px-8 lg:px-10"><Link href="/" className="relative z-[70] flex items-center gap-2.5 text-lg font-semibold tracking-tight text-white"><span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] shadow-[0_0_24px_rgba(79,124,255,.38)]"><Sparkles size={18} /></span>ClearFrame</Link><nav className="hidden h-11 items-center gap-1 lg:flex" aria-label="Primary navigation">{navGroups.slice(0, 2).map((group) => <DropdownMenu key={group.label} group={group} open={openGroup === group.label} onOpen={() => setOpenGroup(group.label)} onClose={() => setOpenGroup(null)} active={active} onSelect={select} />)}<Link href="/pricing" aria-current={active === "pricing" ? "page" : undefined} className="inline-flex h-11 items-center rounded-full px-3 text-sm font-medium leading-none text-white/65 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">Pricing</Link>{navGroups.slice(2).map((group) => <DropdownMenu key={group.label} group={group} open={openGroup === group.label} onOpen={() => setOpenGroup(group.label)} onClose={() => setOpenGroup(null)} active={active} onSelect={select} />)}{isAuthed ? <Link href="/dashboard" className="ml-2 inline-flex h-10 items-center gap-2 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 text-sm font-semibold text-white shadow-[0_8px_22px_rgba(79,124,255,.24)] transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"><LayoutDashboard size={16} /> Open dashboard</Link> : <><Link href="/login" className="inline-flex h-11 items-center rounded-full px-3 text-sm font-medium leading-none text-white/75 transition hover:text-white">Log in</Link><Link href="/signup" className="inline-flex h-11 items-center rounded-full px-3 text-sm font-medium leading-none text-white/75 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">Sign up</Link></>}</nav><button type="button" aria-label={drawerOpen ? "Close menu" : "Open menu"} aria-expanded={drawerOpen} onClick={() => setDrawerOpen(!drawerOpen)} className="relative z-[70] grid h-11 w-11 place-items-center rounded-xl text-white lg:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">{drawerOpen ? <X /> : <Menu />}</button></div></motion.header><MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} active={active} onSelect={select} isAuthed={isAuthed} /></>;
}




















