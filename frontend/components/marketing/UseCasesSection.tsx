import { useCases } from "./content";

const useCaseAccents = [
  "bg-[#4f7cff]/15 text-[#9db9ff]",
  "bg-[#22d3ee]/12 text-[#7de6f7]",
  "bg-[#a78bfa]/15 text-[#c4b0ff]",
  "bg-[#34d399]/12 text-[#86e8c3]",
  "bg-[#fbbf24]/12 text-[#fcd77f]",
  "bg-[#f472b6]/12 text-[#f9a8d1]",
];

export function UseCasesSection() {
  return (
    <section id="use-cases" className="relative scroll-mt-24 overflow-hidden bg-[#0c0e1a] py-24 sm:py-28">
      <div className="pointer-events-none absolute left-[-6%] bottom-0 h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(79,124,255,.08),transparent_70%)]" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="max-w-2xl">
          <p className="bg-gradient-to-r from-[#7de6f7] to-[#9db9ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Who it&apos;s for</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">Remove owned logos, timestamps, and subtitles.</h2>
          <p className="mt-4 text-lg leading-8 text-white/60">ClearFrame is a video overlay remover for footage you own, license, or are authorized to edit.</p>
        </div>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {useCases.map((uc, i) => {
            const Icon = uc.icon;
            return (
              <article
                key={uc.title}
                className="rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-6 transition hover:-translate-y-0.5 hover:border-white/[.16]"
              >
                <span className={`grid h-10 w-10 place-items-center rounded-xl ${useCaseAccents[i % useCaseAccents.length]}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-5 font-semibold text-white">{uc.title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/55">{uc.copy}</p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
