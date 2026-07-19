export function scrollToSection(id: string): void {
  const element = document.getElementById(id.replace(/^#/, ""));
  if (!element) return;
  const offset = 80;
  const top = element.getBoundingClientRect().top + window.scrollY - offset;
  window.history.replaceState(null, "", `#${id.replace(/^#/, "")}`);
  window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
}
