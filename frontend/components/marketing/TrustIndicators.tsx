import { Check } from "lucide-react";

import { heroTrust } from "./content";

export function TrustIndicators({ items = heroTrust }: { items?: string[] }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2">
      {items.map((item) => (
        <li key={item} className="inline-flex items-center gap-1.5 text-sm text-white/65">
          <Check className="h-4 w-4 shrink-0 text-cyan-300" />
          {item}
        </li>
      ))}
    </ul>
  );
}
