"use client";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  CircleHelp,
  Database,
  FileDown,
  Gauge,
  ShieldAlert,
  Users,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { api, fetchServiceStatus, type ComponentState } from "@/lib/api";

const SERVICE_CARD_CONFIG = [
  { name: "API Gateway", keys: ["api"] },
  { name: "Weather service", keys: ["weather"] },
  { name: "Transport service", keys: ["transport", "traffic"] },
  { name: "Decision engine", keys: ["decision_engine", "risk_model"] },
];

const STATE_LABEL: Record<ComponentState, string> = {
  operational: "Operational",
  degraded: "Degraded",
  down: "Unavailable",
  unknown: "Unknown",
};

export default function AdminPage() {
  const jobs = useQuery({
    queryKey: ["admin", "jobs"],
    queryFn: ({ signal }) => api.getAdminJobs(signal),
    retry: false,
  });
  const reviews = useQuery({
    queryKey: ["admin", "reviews"],
    queryFn: ({ signal }) => api.getFeedbackReviews(signal),
    retry: false,
  });
  const serviceStatus = useQuery({
    queryKey: ["service-status"],
    queryFn: ({ signal }) => fetchServiceStatus(signal),
    retry: false,
  });
  const serviceCards = SERVICE_CARD_CONFIG.map((config, index) => {
    const component = serviceStatus.data?.components.find((candidate) =>
      config.keys.includes(candidate.key),
    );
    const state =
      component?.state ??
      (index === 0 && serviceStatus.isError ? "down" : "unknown");
    return {
      ...config,
      state,
      status: STATE_LABEL[state],
      detail:
        component?.message ??
        (serviceStatus.isError
          ? index === 0
            ? "API status endpoint is unreachable"
            : "Dependency status could not be verified"
          : "Waiting for live status data"),
    };
  });
  const overallState = serviceStatus.isError
    ? "down"
    : (serviceStatus.data?.overall ?? "unknown");
  const overallLabel = serviceStatus.isPending
    ? "Checking core systems…"
    : overallState === "operational"
      ? "All core systems online"
      : overallState === "degraded"
        ? "Some systems are degraded"
        : overallState === "down"
          ? "System status unavailable"
          : "Core status is unknown";
  return (
    <main className="min-h-screen bg-[#f8fbff] text-ink">
      <aside className="fixed inset-y-0 hidden w-64 flex-col bg-ink p-6 text-white lg:flex">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold">
          <Gauge /> WayPoint{" "}
          <span className="rounded bg-aqua px-1.5 py-0.5 text-[10px] tracking-widest">
            ADMIN
          </span>
        </Link>
        <nav className="mt-12 space-y-2 text-sm">
          <Nav icon={<Gauge size={17} />} label="Overview" active />
          <Nav icon={<Activity size={17} />} label="Jobs & streams" />
          <Nav icon={<Users size={17} />} label="Feedback review" />
          <Nav icon={<Database size={17} />} label="Audit logs" />
          <Nav icon={<FileDown size={17} />} label="Data exports" />
        </nav>
        <div className="mt-auto rounded-xl border border-white/15 p-4 text-xs text-white/65">
          <span className="flex items-center gap-2 font-bold text-white">
            <CheckCircle2 size={15} className="text-[#b9e5fb]" /> Admin access
          </span>
          <p className="mt-2 leading-5">
            Diagnostics never expose user places, questions, or answers.
          </p>
        </div>
      </aside>
      <div className="lg:pl-64">
        <header className="flex items-center justify-between border-b border-ink/10 bg-white px-6 py-5 sm:px-10">
          <div>
            <p className="text-xs font-bold tracking-[.18em] text-aqua">
              CONTROL ROOM
            </p>
            <h1 className="mt-1 font-display text-3xl">Good morning, team.</h1>
          </div>
          <Link
            href="/"
            className="rounded-full border border-ink/15 px-4 py-2 text-xs font-bold"
          >
            VIEW PUBLIC APP <ArrowUpRight className="ml-1 inline" size={14} />
          </Link>
        </header>
        <div className="mx-auto max-w-7xl p-6 sm:p-10">
          <section>
            <div className="flex items-end justify-between">
              <div>
                <h2 className="font-display text-3xl">System pulse</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Operational picture across the decision pipeline.
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1.5 text-xs font-bold ${overallState === "operational" ? "bg-emerald-50 text-emerald-800" : overallState === "degraded" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-700"}`}
              >
                {overallLabel}
              </span>
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {serviceCards.map(({ name, status, detail, state }) => {
                const Icon =
                  state === "operational"
                    ? CheckCircle2
                    : state === "degraded"
                      ? CircleAlert
                      : state === "down"
                        ? XCircle
                        : CircleHelp;
                const stateClass =
                  state === "operational"
                    ? "bg-emerald-50 text-emerald-700"
                    : state === "degraded"
                      ? "bg-amber-50 text-amber-700"
                      : state === "down"
                        ? "bg-red-50 text-red-700"
                        : "bg-slate-100 text-slate-600";
                return (
                  <article
                    key={name}
                    className="rounded-2xl bg-white p-5 shadow-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className={`rounded-lg p-2 ${stateClass}`}>
                        <Icon size={18} aria-hidden />
                      </span>
                      <span className="text-xs font-bold text-slate-400">
                        LIVE
                      </span>
                    </div>
                    <h3 className="mt-7 text-sm font-bold">{name}</h3>
                    <p
                      className={`mt-1 text-sm font-bold ${stateClass.split(" ")[1]}`}
                    >
                      {status}
                    </p>
                    <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
                      {detail}
                    </p>
                  </article>
                );
              })}
            </div>
          </section>
          <section className="mt-8 grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
            <article className="rounded-2xl bg-white p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold tracking-widest text-aqua">
                    ASYNC PIPELINE
                  </p>
                  <h2 className="mt-1 font-display text-2xl">Recent jobs</h2>
                </div>
                <button className="text-xs font-bold">
                  VIEW ALL <ArrowUpRight className="inline" size={14} />
                </button>
              </div>
              <div className="mt-6 overflow-x-auto">
                <table className="w-full min-w-[580px] text-left text-sm">
                  <thead className="border-b border-slate-100 text-xs tracking-wider text-slate-400">
                    <tr>
                      <th className="pb-3 font-bold">JOB ID</th>
                      <th className="pb-3 font-bold">STAGE</th>
                      <th className="pb-3 font-bold">OUTCOME</th>
                      <th className="pb-3 font-bold">UPDATED</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.isLoading ? (
                      <Rows label="Loading jobs from API…" />
                    ) : jobs.isError ? (
                      <Rows label="Unable to load jobs from the API" />
                    ) : (
                      <Rows
                        label={`${jobs.data?.items.length ?? 0} jobs returned by the API`}
                      />
                    )}
                  </tbody>
                </table>
              </div>
              <p className="mt-5 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">
                <ShieldAlert className="mr-1 inline text-aqua" size={15} />{" "}
                Progress comes from ticketed SSE. Close the stream immediately
                when a job completes or fails.
              </p>
            </article>
            <article className="rounded-2xl bg-pine p-6 text-white">
              <p className="text-xs font-bold tracking-widest text-[#b9e5fb]">
                HUMAN IN THE LOOP
              </p>
              <h2 className="mt-2 font-display text-3xl">Feedback review</h2>
              <p className="mt-3 text-sm leading-6 text-white/70">
                {reviews.isLoading
                  ? "Checking feedback queue…"
                  : reviews.isError
                    ? "Connect the API to see the oldest reported feedback first."
                    : "Review reported feedback with context, then approve or reject."}
              </p>
              <div className="mt-8 rounded-xl bg-white/10 p-4">
                <span className="text-3xl font-bold">
                  {reviews.data ? reviews.data.items.length : "—"}
                </span>
                <span className="ml-2 text-sm text-white/70">
                  waiting for review
                </span>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/15">
                  <div className="h-full w-2/3 rounded-full bg-[#b9e5fb]" />
                </div>
              </div>
              <button className="mt-5 w-full rounded-xl bg-white px-4 py-3 text-sm font-bold text-pine">
                Open review queue
              </button>
            </article>
          </section>
          <section className="mt-8 grid gap-4 md:grid-cols-3">
            <MiniStat
              label="Loaded jobs"
              value={jobs.data ? String(jobs.data.items.length) : "—"}
              change={jobs.isError ? "API unavailable" : "Current response"}
            />
            <MiniStat
              label="Median assessment"
              value="—"
              change="No live metric"
            />
            <MiniStat
              label="Training exports"
              value="—"
              change="No live metric"
            />
          </section>
        </div>
      </div>
    </main>
  );
}
function Nav({
  icon,
  label,
  active = false,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <button
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left ${active ? "bg-white/12 font-bold" : "text-white/60 hover:bg-white/5 hover:text-white"}`}
    >
      {icon}
      {label}
    </button>
  );
}
function Rows({ label }: { label: string }) {
  return (
    <tr>
      <td colSpan={4} className="py-10 text-center text-sm text-slate-400">
        {label}
      </td>
    </tr>
  );
}
function MiniStat({
  label,
  value,
  change,
}: {
  label: string;
  value: string;
  change: string;
}) {
  return (
    <article className="rounded-2xl bg-white p-5">
      <p className="text-xs font-bold tracking-wider text-slate-400">
        {label.toUpperCase()}
      </p>
      <div className="mt-3 flex items-end justify-between">
        <b className="font-display text-3xl">{value}</b>
        <span className="text-xs font-bold text-pine">{change}</span>
      </div>
    </article>
  );
}
