"use client";

import * as React from "react";
import { useState } from "react";
import Link from "next/link";
import { BadgeCheck, ChevronDown, LogOut } from "lucide-react";

import { cn } from "@/lib/utils";
import type { AuthUser } from "@/features/auth/authStore";
import type { SubscriptionStatus } from "@/services/payments";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { accountActions, accountSupportNav } from "./accountNav";
import { AccountContextNotice } from "./AccountContextNotice";
import { CompactAccountSummary } from "./CompactAccountSummary";
import { AuthAvatarSkeleton, UserAvatar } from "./UserAvatar";
import { useAccountMenu } from "./useAccountMenu";

/** Display name that never renders undefined/null/empty. */
function displayName(user: AuthUser): string {
  const full = user.full_name?.trim();
  if (full) return full;
  const emailUser = user.email?.split("@")[0]?.trim();
  return emailUser || "Account";
}

function planLabel(status: SubscriptionStatus | undefined): string | null {
  return status?.plan_name?.trim() || null;
}

/** Compact identity row: avatar + name + email + verified·plan meta line. */
function AccountIdentity({ user, status }: { user: AuthUser; status: SubscriptionStatus | undefined }) {
  const name = displayName(user);
  const plan = planLabel(status);
  return (
    <div className="flex items-center gap-3 px-1">
      <UserAvatar user={user} size={40} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-white" title={name}>
          {name}
        </p>
        <p className="truncate text-xs text-white/50" title={user.email}>
          {user.email}
        </p>
        <p className="mt-0.5 flex items-center gap-1 text-[11px] text-white/40">
          {user.email_verified && (
            <span className="flex items-center gap-0.5 text-cyan-300/90">
              <BadgeCheck aria-hidden className="h-3 w-3" />
              Verified
            </span>
          )}
          {user.email_verified && plan && <span aria-hidden>·</span>}
          {plan && <span className="text-[#b7c7ff]">{plan}</span>}
        </p>
      </div>
    </div>
  );
}

type MenuData = ReturnType<typeof useAccountMenu>;

/**
 * Shared trigger: circular avatar button with hover/focus/open states.
 * forwardRef + prop spread so Radix (DropdownMenuTrigger asChild) can attach
 * its handlers and aria attributes directly to the real button.
 */
const Trigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    user: AuthUser;
    open: boolean;
    showChevron?: boolean;
  }
>(({ user, open, showChevron, className, ...props }, ref) => {
  return (
    <button
      ref={ref}
      type="button"
      aria-label="Open account menu"
      className={cn(
        "flex h-10 items-center gap-1.5 rounded-full pl-0.5 outline-none transition",
        "focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080f]",
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          "grid place-items-center rounded-full p-0.5 ring-2 transition",
          open ? "ring-[#6d5ef7]" : "ring-transparent hover:ring-white/20",
        )}
      >
        <UserAvatar user={user} size={36} />
      </span>
      {showChevron && (
        <ChevronDown
          aria-hidden
          className={cn("hidden h-4 w-4 text-white/45 transition-transform sm:block", open && "rotate-180")}
        />
      )}
    </button>
  );
});
Trigger.displayName = "AccountMenuTrigger";

function DesktopMenu({ data, showChevron }: { data: MenuData; showChevron?: boolean }) {
  const [open, setOpen] = useState(false);
  const { user, status, statusLoading, statusError, signingOut, logout } = data;
  if (!user) return null;

  return (
    <DropdownMenu open={open} onOpenChange={(next) => !signingOut && setOpen(next)}>
      <DropdownMenuTrigger asChild>
        <Trigger user={user} open={open} showChevron={showChevron} />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        side="bottom"
        sideOffset={8}
        collisionPadding={12}
        className="w-[320px] p-2"
      >
        <div className="py-1.5">
          <AccountIdentity user={user} status={status} />
        </div>
        <DropdownMenuSeparator />
        <div className="py-2">
          <CompactAccountSummary status={status} isLoading={statusLoading} isError={statusError} />
        </div>
        {!statusLoading && <AccountContextNotice user={user} status={status} />}
        <DropdownMenuSeparator />
        {accountActions.map((item) => (
          <DropdownMenuItem key={item.label} asChild>
            <Link href={item.href}>
              <item.icon aria-hidden className="h-[18px] w-[18px] text-white/50" />
              {item.label}
            </Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        {accountSupportNav.map((item) => (
          <DropdownMenuItem key={item.label} asChild className="text-white/55">
            <Link href={item.href}>
              <item.icon aria-hidden className="h-[18px] w-[18px] text-white/40" />
              {item.label}
            </Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={signingOut}
          onSelect={(e) => {
            e.preventDefault(); // own the logout lifecycle; don't auto-close mid-request
            void logout();
          }}
          className="text-rose-300/85 data-[highlighted]:bg-rose-400/10 data-[highlighted]:text-rose-200"
        >
          <LogOut aria-hidden className="h-[18px] w-[18px]" />
          {signingOut ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function MobileMenu({ data }: { data: MenuData }) {
  const [open, setOpen] = useState(false);
  const { user, status, statusLoading, statusError, signingOut, logout } = data;
  if (!user) return null;

  const items = [...accountActions, ...accountSupportNav];

  return (
    <Sheet open={open} onOpenChange={(next) => !signingOut && setOpen(next)}>
      <SheetContent
        side="bottom"
        className="gap-0 rounded-t-3xl px-5 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] pt-6"
      >
        <SheetTitle className="sr-only">Account menu</SheetTitle>
        <AccountIdentity user={user} status={status} />
        <div className="mt-5 border-t border-white/10 py-4">
          <CompactAccountSummary status={status} isLoading={statusLoading} isError={statusError} />
          {!statusLoading && (
            <div className="mt-3">
              <AccountContextNotice user={user} status={status} />
            </div>
          )}
        </div>
        <nav className="border-t border-white/10 py-2">
          {items.map((item) => (
            <SheetClose asChild key={item.label}>
              <Link
                href={item.href}
                className="flex min-h-12 items-center gap-3 rounded-xl px-2 text-sm text-white/80 transition hover:bg-white/5 hover:text-white"
              >
                <item.icon aria-hidden className="h-5 w-5 text-white/50" />
                {item.label}
              </Link>
            </SheetClose>
          ))}
        </nav>
        <div className="border-t border-white/10 pt-3">
          <button
            type="button"
            disabled={signingOut}
            onClick={() => void logout()}
            className="flex min-h-12 w-full items-center gap-3 rounded-xl px-2 text-sm font-medium text-rose-300/90 transition hover:bg-rose-400/10 hover:text-rose-200 disabled:opacity-50"
          >
            <LogOut aria-hidden className="h-5 w-5" />
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </SheetContent>
      <button
        type="button"
        aria-label="Open account menu"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        className="flex h-10 items-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080f]"
      >
        <span className="grid place-items-center rounded-full p-0.5 ring-2 ring-transparent transition hover:ring-white/20">
          <UserAvatar user={user} size={36} />
        </span>
      </button>
    </Sheet>
  );
}

/**
 * Account control center opened from the header avatar. Desktop → right-aligned
 * Radix dropdown (portaled, collision-aware). Mobile → bottom sheet. Focused on
 * identity, account status, subscription, and support — not workspace nav.
 */
export function UserMenu({ showChevron = true }: { showChevron?: boolean }) {
  const data = useAccountMenu();
  const isDesktop = useMediaQuery("(min-width: 640px)");

  // Auth not hydrated yet → avatar skeleton, no wrong user, not clickable.
  if (!data.user) return <AuthAvatarSkeleton size={36} />;

  return isDesktop ? (
    <DesktopMenu data={data} showChevron={showChevron} />
  ) : (
    <MobileMenu data={data} />
  );
}
