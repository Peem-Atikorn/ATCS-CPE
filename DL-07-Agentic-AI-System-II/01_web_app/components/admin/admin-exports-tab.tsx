"use client";

import { useMutation } from "@tanstack/react-query";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  FileDown,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { TrainingExportResponse } from "@/lib/types";

export function AdminExportsTab() {
  const [rangeFrom, setRangeFrom] = useState<string>("");
  const [rangeTo, setRangeTo] = useState<string>("");
  const [activeExportId, setActiveExportId] = useState<string | null>(null);
  const [exportDetails, setExportDetails] = useState<TrainingExportResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const exportMutation = useMutation({
    mutationFn: (body: { from?: string; to?: string }) =>
      api.requestTrainingExport(body),
    onSuccess: async (data) => {
      setActiveExportId(data.export_id);
      setErrorMsg(null);
      // Immediately check status
      pollStatus(data.export_id);
    },
    onError: (err) => {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to request training data export.",
      );
    },
  });

  const pollStatus = async (id: string) => {
    setChecking(true);
    try {
      const result = await api.getTrainingExport(id);
      setExportDetails(result);
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to query export status.",
      );
    } finally {
      setChecking(false);
    }
  };

  const handleRequestExport = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    exportMutation.mutate({
      from: rangeFrom ? new Date(rangeFrom).toISOString() : undefined,
      to: rangeTo ? new Date(rangeTo).toISOString() : undefined,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl text-slate-900">Training Data Exports</h2>
        <p className="mt-1 text-xs text-slate-500">
          Export anonymized, privacy-compliant datasets for fine-tuning and safety evaluations (FR-19, D-92).
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Export Request Form */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-pine/10 text-pine">
              <FileDown size={18} />
            </div>
            <div>
              <h3 className="font-display text-lg text-slate-900">Request New Dataset</h3>
              <p className="text-xs text-slate-500">
                Select an optional time window or export all completed recommendations.
              </p>
            </div>
          </div>

          <form onSubmit={handleRequestExport} className="mt-6 space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700">
                Start Date / Time (Optional)
              </label>
              <div className="relative mt-1">
                <input
                  type="datetime-local"
                  value={rangeFrom}
                  onChange={(e) => setRangeFrom(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-pine focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700">
                End Date / Time (Optional)
              </label>
              <div className="relative mt-1">
                <input
                  type="datetime-local"
                  value={rangeTo}
                  onChange={(e) => setRangeTo(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs focus:border-pine focus:outline-none"
                />
              </div>
            </div>

            <div className="rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-500">
              <ShieldAlert className="mr-1 inline text-aqua" size={14} /> Anonymization
              guarantee: Personal places, exact user questions, and identifiable attributes
              are stripped out before storage.
            </div>

            {errorMsg && (
              <p className="text-xs font-bold text-red-600">{errorMsg}</p>
            )}

            <button
              type="submit"
              disabled={exportMutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-pine px-4 py-2.5 text-xs font-bold text-white transition hover:bg-pine/90 disabled:opacity-50"
            >
              {exportMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} className="text-[#b9e5fb]" />
              )}
              Queue Export Task
            </button>
          </form>
        </div>

        {/* Export Status & Download Card */}
        <div className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="font-display text-lg text-slate-900">Task Status</h3>
            {activeExportId && (
              <button
                type="button"
                onClick={() => pollStatus(activeExportId)}
                disabled={checking}
                className="inline-flex items-center gap-1 text-xs font-bold text-pine hover:underline"
              >
                <RefreshCw size={12} className={checking ? "animate-spin" : ""} /> Check
              </button>
            )}
          </div>

          <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
            {exportDetails ? (
              <div className="w-full space-y-4 text-left">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">Export ID</span>
                  <span className="font-mono text-xs font-bold text-slate-800">
                    {exportDetails.export_id.slice(0, 12)}...
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">Status</span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                      exportDetails.status === "completed"
                        ? "bg-emerald-100 text-emerald-800"
                        : exportDetails.status === "failed"
                          ? "bg-red-100 text-red-800"
                          : "bg-sky-100 text-sky-800"
                    }`}
                  >
                    {exportDetails.status.toUpperCase()}
                  </span>
                </div>

                {exportDetails.row_count !== null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">Exported Rows</span>
                    <span className="font-display text-lg font-bold text-slate-900">
                      {exportDetails.row_count.toLocaleString()} rows
                    </span>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">Created At</span>
                  <span className="text-xs text-slate-600">
                    {new Date(exportDetails.created_at).toLocaleString()}
                  </span>
                </div>

                {exportDetails.download_url ? (
                  <a
                    href={exportDetails.download_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-xs font-bold text-white shadow-sm hover:bg-emerald-700"
                  >
                    <Download size={15} /> Download Export File (.jsonl / .tar)
                  </a>
                ) : (
                  <div className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-slate-50 p-4 text-xs text-slate-500">
                    <Clock size={16} className="text-slate-400" />
                    <span>Processing in background worker... Refresh in a few moments.</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-slate-400">
                <FileDown size={40} className="mx-auto mb-2 text-slate-300" />
                <p className="text-sm font-bold text-slate-600">No active export selected</p>
                <p className="mt-1 text-xs text-slate-400">
                  Submit an export request on the left to track progress and download here.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
