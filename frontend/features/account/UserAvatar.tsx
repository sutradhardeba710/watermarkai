"use client";

import { useState } from "react";
import { UserRound } from "lucide-react";

import { cn } from "@/lib/utils";
import type { AuthUser } from "@/features/auth/authStore";

/** First letter of name, else email, else nothing (caller shows the icon). */
export function initialFor(user: Pick<AuthUser, "full_name" | "email"> | null | undefined): string {
  const source = user?.full_name?.trim() || user?.email?.trim() || "";
  return source ? source[0]!.toUpperCase() : "";
}

/** Deterministic gradient so a user's fallback avatar is stable across renders. */
const GRADIENTS = [
  "from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]",
  "from-[#22d3ee] via-[#4f7cff] to-[#6d5ef7]",
  "from-[#f472b6] via-[#a855f7] to-[#6d5ef7]",
  "from-[#34d399] via-[#22d3ee] to-[#4f7cff]",
  "from-[#fbbf24] via-[#fb7185] to-[#a855f7]",
];

function gradientFor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length]!;
}

export function UserAvatar({
  user,
  imageUrl,
  size = 36,
  className,
}: {
  user: Pick<AuthUser, "id" | "full_name" | "email"> | null | undefined;
  imageUrl?: string | null;
  size?: number;
  className?: string;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const initial = initialFor(user);
  const seed = user?.id || user?.email || "account";
  const showImage = Boolean(imageUrl) && !imageFailed;

  return (
    <span
      className={cn(
        "grid shrink-0 place-items-center overflow-hidden rounded-full text-sm font-semibold text-white",
        !showImage && `bg-gradient-to-br ${gradientFor(seed)}`,
        className,
      )}
      style={{ height: size, width: size, fontSize: Math.round(size * 0.4) }}
    >
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageUrl!}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setImageFailed(true)}
        />
      ) : initial ? (
        <span aria-hidden>{initial}</span>
      ) : (
        <UserRound aria-hidden style={{ height: size * 0.45, width: size * 0.45 }} />
      )}
    </span>
  );
}

export function AuthAvatarSkeleton({ size = 36 }: { size?: number }) {
  return (
    <span
      className="block shrink-0 animate-pulse rounded-full bg-white/10"
      style={{ height: size, width: size }}
      aria-hidden
    />
  );
}
