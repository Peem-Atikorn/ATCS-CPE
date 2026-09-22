"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  CircleHelp,
  Database,
  FileDown,
  Gauge,
  Layers,
  RefreshCw,
  ShieldAlert,
  Users,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AdminAuditTab } from "@/components/admin/admin-audit-tab";
import { AdminAuthBar } from "@/components/admin/admin-auth-bar";
import { AdminExportsTab } from "@/components/admin/admin-exports-tab";
import { AdminJobsTab } from "@/components/admin/admin-jobs-tab";
import { AdminReviewsTab } from "@/components/admin/admin-reviews-tab";
import { api, fetchServiceStatus, type ComponentState } from "@/lib/api";

type TabId = "overview" | "jobs" | "reviews" | "audit" | "exports";

const SERVICE_CARD_CONFIG = [
  { name: "API Gateway", keys: ["api"] },
  { name: "Agent Core & RAG", keys: ["agent", "rag"] },
  { name: "Weather service", keys: ["weather"] },
  { name: "Transport service", keys: ["transport", "traffic"] },
  { name: "Disaster alerts", keys: ["disaster"] },
  { name: "Decision engine", keys: ["decision_engine", "risk_model"] },
];

const STATE_LABEL: Record<ComponentState, string> = {
  operational: "Operational",
  degraded: "Degraded",
  down: "Unavailable",
  unknown: "Unknown",
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const queryClient = useQueryClient();

  const jobs = useQuery({
    queryKey: ["admin", "jobs", "overview"],
    queryFn: ({ signal }) => api.getAdminJobs({ limit: 5 }, signal),
    retry: false,
  });

  const reviews = useQuery({
    queryKey: ["admin", "reviews", "overview"],
    queryFn: ({ signal }) => api.getFeedbackReviews({ status: "pending", limit: 5 }, signal),
    retry: false,
  });

  const audit = useQuery({
    queryKey: ["admin", "audit-logs", "overview"],
    queryFn: ({ signal }) => api.getAuditLogs({ limit: 5 }, signal),
    retry: false,
  });

  const serviceStatus = useQuery({
    queryKey: ["service-status"],
    queryFn: ({ signal }) => fetchServiceStatus(signal),
    refetchInterval: 30_000,
  });

  const handleTokenChange = () => {
    queryClient.invalidateQueries({ queryKey: ["admin"] });
    queryClient.invalidateQueries({ queryKey: ["service-status"] });
  };

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
            ? "API status endpoint unreachable"
            : "Dependency status unverified"
          : "Live operational telemetry"),
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
      {/* Sidebar Navigation */}
      <aside className="fixed inset-y-0 hidden w-64 flex-col bg-ink p-6 text-white lg:flex">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold">
          <Gauge /> WayPoint{" "}
          <span className="rounded bg-aqua px-1.5 py-0.5 text-[10px] tracking-widest">
            ADMIN
          </span>
        </Link>

        <nav className="mt-12 space-y-2 text-sm">
          <Nav
            icon={<Gauge size={17} />}
            label="Overview"
            active={activeTab === "overview"}
            onClick={() => setActiveTab("overview")}
          />
          <Nav
            icon={<Activity size={17} />}
            label="Jobs & streams"
            active={activeTab === "jobs"}
            onClick={() => setActiveTab("jobs")}
          />
          <Nav
            icon={<Users size={17} />}
            label="Feedback review"
            active={activeTab === "reviews"}
            onClick={() => setActiveTab("reviews")}
          />
          <Nav
            icon={<Database size={17} />}
            label="Audit logs"
            active={activeTab === "audit"}
            onClick={() => setActiveTab("audit")}
          />
          <Nav
            icon={<FileDown size={17} />}
            label="Data exports"
            active={activeTab === "exports"}
            onClick={() => setActiveTab("exports")}
          />
        </nav>

        <div className="mt-auto rounded-xl border border-white/15 p-4 text-xs text-white/65">
          <span className="flex items-center gap-2 font-bold text-white">
            <CheckCircle2 size={15} className="text-[#b9e5fb]" /> Operational Integrity
          </span>
          <p className="mt-2 leading-5">
            Diagnostics never expose user locations, private queries, or identifiable credentials.
          </p>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="lg:pl-64">
        <header className="flex items-center justify-between border-b border-ink/10 bg-white px-6 py-5 sm:px-10">
          <div>
            <p className="text-xs font-bold tracking-[.18em] text-aqua">
              CONTROL ROOM
            </p>
            <h1 className="mt-1 font-display text-3xl capitalize">
              {activeTab === "overview" && "System Pulse & Control"}
              {activeTab === "jobs" && "Pipeline Jobs"}
              {activeTab === "reviews" && "Safety Review Queue"}
              {activeTab === "audit" && "Audit Trail"}
              {activeTab === "exports" && "Training Data Exports"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {/* Mobile Tab Selector */}
            <div className="flex rounded-xl border border-slate-200 bg-white p-1 text-xs lg:hidden">
              {(["overview", "jobs", "reviews", "audit", "exports"] as const).map(
                (tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveTab(tab)}
                    className={`rounded-lg px-2.5 py-1 capitalize font-bold ${
                      activeTab === tab
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {tab}
                  </button>
                ),
              )}
            </div>

            <Link
              href="/"
              className="rounded-full border border-ink/15 px-4 py-2 text-xs font-bold transition hover:bg-slate-50"
            >
              PUBLIC APP <ArrowUpRight className="ml-1 inline" size={14} />
            </Link>
          </div>
        </header>

        <div className="mx-auto max-w-7xl p-6 sm:p-10">
          {/* Admin Auth Bar */}
          <AdminAuthBar onTokenChange={handleTokenChange} />

          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-8">
              {/* System Pulse Section */}
              <section>
                <div className="flex items-end justify-between">
                  <div>
                    <h2 className="font-display text-3xl">System Pulse</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      Live component availability across the real-time decision pipeline.
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1.5 text-xs font-bold ${
                      overallState === "operational"
                        ? "bg-emerald-50 text-emerald-800"
                        : overallState === "degraded"
                          ? "bg-amber-50 text-amber-800"
                          : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {overallLabel}
                  </span>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
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
                        className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
                      >
                        <div className="flex items-center justify-between">
                          <span className={`rounded-lg p-2 ${stateClass}`}>
                            <Icon size={18} aria-hidden />
                          </span>
                          <span className="text-[10px] font-bold tracking-wider text-slate-400">
                            TELEMETRY
                          </span>
                        </div>
                        <h3 className="mt-5 text-sm font-bold text-slate-900">{name}</h3>
                        <p className={`mt-1 text-sm font-bold ${stateClass.split(" ")[1]}`}>
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

              {/* Jobs and Safety Review Summary */}
              <section className="grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
                <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold tracking-widest text-aqua">
                        ASYNC PIPELINE
                      </p>
                      <h2 className="mt-1 font-display text-2xl">Recent Jobs</h2>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveTab("jobs")}
                      className="text-xs font-bold text-pine hover:underline"
                    >
                      VIEW ALL <ArrowUpRight className="inline" size={14} />
                    </button>
                  </div>

                  <div className="mt-6 overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-slate-100 text-[11px] uppercase tracking-wider text-slate-400">
                        <tr>
                          <th className="pb-3 font-bold">JOB ID</th>
                          <th className="pb-3 font-bold">TYPE</th>
                          <th className="pb-3 font-bold">STATUS</th>
                          <th className="pb-3 font-bold">STAGE</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {jobs.isLoading ? (
                          <tr>
                            <td colSpan={4} className="py-8 text-center text-slate-400">
                              Loading live jobs...
                            </td>
                          </tr>
                        ) : jobs.isError ? (
                          <tr>
                            <td colSpan={4} className="py-8 text-center text-slate-400">
                              Connect admin token above to view live jobs.
                            </td>
                          </tr>
                        ) : !jobs.data?.items || jobs.data.items.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-8 text-center text-slate-400">
                              No recent jobs recorded.
                            </td>
                          </tr>
                        ) : (
                          jobs.data.items.slice(0, 5).map((job) => (
                            <tr key={job.job_id} className="hover:bg-slate-50">
                              <td className="py-3 font-mono text-slate-700">
                                {job.job_id.slice(0, 8)}...
                              </td>
                              <td className="py-3 font-bold text-slate-800">{job.type}</td>
                              <td className="py-3">
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                    job.status === "succeeded"
                                      ? "bg-emerald-50 text-emerald-700"
                                      : job.status === "running"
                                        ? "bg-sky-50 text-sky-700"
                                        : job.status === "failed"
                                          ? "bg-red-50 text-red-700"
                                          : "bg-slate-100 text-slate-700"
                                  }`}
                                >
                                  {job.status}
                                </span>
                              </td>
                              <td className="py-3 font-mono text-slate-500">{job.stage}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>

                  <p className="mt-5 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">
                    <ShieldAlert className="mr-1 inline text-aqua" size={15} /> Real-time
                    evaluations stream over ticketed Server-Sent Events (SSE).
                  </p>
                </article>

                <article className="rounded-2xl bg-pine p-6 text-white shadow-sm">
                  <p className="text-xs font-bold tracking-widest text-[#b9e5fb]">
                    HUMAN IN THE LOOP
                  </p>
                  <h2 className="mt-2 font-display text-3xl">Feedback Review</h2>
                  <p className="mt-3 text-sm leading-6 text-white/70">
                    Inspect user safety feedback and route accuracy reports.
                  </p>

                  <div className="mt-8 rounded-xl bg-white/10 p-5">
                    <div className="flex items-baseline gap-2">
                      <span className="font-display text-4xl font-bold">
                        {reviews.data?.items ? reviews.data.items.length : "0"}
                      </span>
                      <span className="text-sm text-white/70">waiting in review queue</span>
                    </div>
                    <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/15">
                      <div
                        className="h-full rounded-full bg-[#b9e5fb]"
                        style={{
                          width: `${Math.min(
                            ((reviews.data?.items.length ?? 0) / 10) * 100,
                            100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveTab("reviews")}
                    className="mt-6 w-full rounded-xl bg-white px-4 py-3 text-sm font-bold text-pine transition hover:bg-slate-100"
                  >
                    Open Review Queue
                  </button>
                </article>
              </section>

              {/* Quick Metrics */}
              <section className="grid gap-4 md:grid-cols-4">
                <MiniStat
                  label="Completed Jobs"
                  value={jobs.data?.items ? String(jobs.data.items.length) : "—"}
                  change={jobs.isError ? "Auth Required" : "Live from database"}
                />
                <MiniStat
                  label="Pending Reviews"
                  value={reviews.data?.items ? String(reviews.data.items.length) : "—"}
                  change="Awaiting human decision"
                />
                <MiniStat
                  label="Audit Records"
                  value={audit.data?.items ? String(audit.data.items.length) : "—"}
                  change="Immutable security trail"
                />
                <MiniStat
                  label="System Core"
                  value={overallState === "operational" ? "100%" : "Degraded"}
                  change="Live Health Status"
                />
              </section>
            </div>
          )}

          {/* TAB 2: JOBS */}
          {activeTab === "jobs" && <AdminJobsTab />}

          {/* TAB 3: REVIEWS */}
          {activeTab === "reviews" && <AdminReviewsTab />}

          {/* TAB 4: AUDIT LOGS */}
          {activeTab === "audit" && <AdminAuditTab />}

          {/* TAB 5: DATA EXPORTS */}
          {activeTab === "exports" && <AdminExportsTab />}
        </div>
      </div>
    </main>
  );
}

function Nav({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-xl px-3.5 py-3 text-left transition ${
        active
          ? "bg-white/12 font-bold text-white shadow-sm"
          : "text-white/60 hover:bg-white/5 hover:text-white"
      }`}
    >
      {icon}
      {label}
    </button>
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
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-bold tracking-wider text-slate-400">
        {label.toUpperCase()}
      </p>
      <div className="mt-3 flex items-end justify-between">
        <b className="font-display text-3xl text-slate-900">{value}</b>
        <span className="text-xs font-bold text-pine">{change}</span>
      </div>
    </article>
  );
}
