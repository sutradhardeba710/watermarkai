import { benefits } from "./content";

/**
 * Asymmetric layout: one large lead panel + three supporting panels — avoids the
 * "four identical cards" look the brief calls out.
 */
export function BenefitsSection() {
  const [lead, ...rest] = benefits;
  const LeadIcon = lead.icon;

  return (
    <section id="benefits" className="scroll-mt-24 bg-[#07080f] py-24 sm:py-28">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="max-w-2xl">
          <p className="bg-gradient-to-r from-[#9db9ff] to-[#c4b0ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Why ClearFrame</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">Automation where it helps. Control where it matters.</h2>
        </div>

        <div className="mt-12 grid gap-4 lg:grid-cols-2">
          <article
            className="relative flex flex-col justify-between overflow-hidden rounded-3xl border border-[#4f7cff]/25 bg-gradient-to-br from-[#1a2046] via-[#141833] to-[#10121f] p-8 shadow-[0_20px_70px_rgba(79,124,255,.12)]"
          >
            <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-[#6d5ef7]/15 blur-3xl" />
            <div className="relative">
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#4f7cff]/30 to-[#a78bfa]/20 text-[#b7c7ff]">
                <LeadIcon className="h-6 w-6" />
              </span>
              <h3 className="mt-6 text-2xl font-semibold text-white">{lead.title}</h3>
              <p className="mt-3 max-w-md leading-7 text-white/60">{lead.copy}</p>
            </div>
            <div className="mt-8 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/55">
              Suggestions are a starting point — you approve, edit, or replace every selection before anything is processed.
            </div>
          </article>

          <div className="grid gap-4 sm:grid-cols-1">
            {rest.map((b, i) => {
              const Icon = b.icon;
              return (
                <article
                  key={b.title}
                  className="flex items-start gap-4 rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-6 transition hover:border-white/[.16]"
                >
                  <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${["bg-[#22d3ee]/12 text-[#7de6f7]", "bg-[#a78bfa]/15 text-[#c4b0ff]", "bg-[#34d399]/12 text-[#86e8c3]"][i % 3]}`}>
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <h3 className="font-semibold text-white">{b.title}</h3>
                    <p className="mt-1.5 text-sm leading-6 text-white/55">{b.copy}</p>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
