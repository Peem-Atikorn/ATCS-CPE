import { Activity, Compass, Menu } from "lucide-react";

export function SiteHeader() {
  return (
    <header className="absolute inset-x-0 top-0 z-20 mx-auto flex max-w-7xl items-center justify-between px-6 py-6 text-white">
      <a href="#top" className="flex items-center gap-2 text-lg font-bold tracking-tight">
        <Compass size={21} /> WayPoint
      </a>
      <nav className="hidden gap-7 text-xs font-bold tracking-wide md:flex">
        <a href="#map" className="transition hover:text-aqua">ROUTE MAP</a>
        <a href="#dashboard" className="transition hover:text-aqua">SAFETY DASHBOARD</a>
        <a href="/status" className="flex items-center gap-1.5 transition hover:text-aqua">
          <Activity size={13} className="text-emerald-400" /> SYSTEM STATUS
        </a>
        <a href="#faq" className="transition hover:text-aqua">FAQ</a>
      </nav>
      <a
        href="/admin"
        className="rounded-full border border-white/60 px-4 py-2 text-xs font-bold backdrop-blur transition hover:bg-white hover:text-ink"
      >
        ADMIN <Menu className="ml-1 inline" size={14} />
      </a>
    </header>
  );
}
