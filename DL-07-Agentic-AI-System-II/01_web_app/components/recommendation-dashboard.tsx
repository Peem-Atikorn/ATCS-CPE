"use client";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  CircleAlert,
  Clock3,
  LoaderCircle,
  Route,
  ShieldAlert,
  ShieldCheck,
  Waves,
  WifiOff,
} from "lucide-react";
import { useTrip } from "@/components/trip-context";
import type { RiskLevel } from "@/lib/types";

const RISK_UI: Record<RiskLevel, { label: string; icon: typeof ShieldCheck; className: string; bg: string }> = {
  LOW: { label: "ความเสี่ยงต่ำ", icon: ShieldCheck, className: "text-[#b9e5fb]", bg: "bg-[#102e4e]" },
  MEDIUM: { label: "ความเสี่ยงปานกลาง", icon: ShieldAlert, className: "text-amber-300", bg: "bg-[#3a2a0e]" },
  HIGH: { label: "ความเสี่ยงสูง", icon: AlertTriangle, className: "text-red-300", bg: "bg-[#3a1414]" },
};

const ACTION_LABEL: Record<string, string> = {
  TRAVEL_NORMALLY: "เดินทางได้ตามปกติ",
  CHANGE_ROUTE: "ควรเปลี่ยนเส้นทาง",
  DELAY_TRAVEL: "ควรเลื่อนการเดินทาง",
  AVOID_TRAVEL: "ควรหลีกเลี่ยงการเดินทาง",
};

export function RecommendationDashboard() {
  const { status, recommendation, usingMock, errorMessage, progressMessage } = useTrip();

  if (status === "idle" || !recommendation) {
    return <IdleExample busy={status === "geocoding" || status === "submitting"} message={progressMessage} />;
  }

  const risk = recommendation.risk;
  const ui = RISK_UI[risk?.level ?? "LOW"];
  const Icon = ui.icon;
  const weatherFactors = (risk?.factors ?? []).filter((f) => f.type.toUpperCase() === "WEATHER");
  const otherFactors = (risk?.factors ?? []).filter((f) => f.type.toUpperCase() !== "WEATHER");
  const weatherAge = recommendation.data_freshness?.items.find((i) => i.category === "WEATHER")
    ?.age_seconds;

  return (
    <div>
      {usingMock && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-300/30 bg-amber-400/10 px-4 py-3 text-xs text-amber-100">
          <WifiOff size={15} />
          <span>
            แสดงข้อมูลตัวอย่าง (ต่อ API จริงไม่ได้{errorMessage ? `: ${errorMessage}` : ""})
          </span>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.05fr_.95fr]">
        <article className={`rounded-2xl ${ui.bg} p-6 sm:p-8`}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold tracking-[.17em] text-white/55">
                ASSESSMENT · {usingMock ? "DEMO DATA" : "LIVE"}
              </p>
              <div className={`mt-6 flex items-center gap-3 ${ui.className}`}>
                <Icon size={28} />
                <span className="font-bold">{ui.label.toUpperCase()}</span>
              </div>
              <h3 className="mt-3 font-display text-4xl sm:text-5xl">
                {ACTION_LABEL[recommendation.recommendation?.type ?? ""] ?? "รอผลการประเมิน"}
              </h3>
            </div>
            <span className="rounded-full bg-white/10 p-3">
              <Check size={20} />
            </span>
          </div>
          <p className="mt-7 max-w-md text-sm leading-7 text-white/70">
            {recommendation.recommendation?.summary ?? "—"}
          </p>
          {recommendation.recommendation?.reasons && recommendation.recommendation.reasons.length > 0 && (
            <ul className="mt-4 space-y-1.5 text-sm text-white/60">
              {recommendation.recommendation.reasons.map((reason) => (
                <li key={reason} className="flex gap-2">
                  <span aria-hidden>•</span>
                  {reason}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-8 grid grid-cols-2 border-t border-white/15 pt-5 text-sm">
            <div>
              <span className="text-white/50">Risk score</span>
              <b className="mt-1 block text-xl">
                {risk?.score != null ? `${Math.round(risk.score * 100)} / 100` : "—"}
              </b>
            </div>
            <div>
              <span className="text-white/50">Confidence</span>
              <b className="mt-1 block text-xl">
                {risk?.confidence != null ? `${Math.round(risk.confidence * 100)}%` : "—"}
              </b>
            </div>
          </div>
        </article>

        <article className="rounded-2xl bg-[#eef7fc] p-6 text-ink sm:p-8">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl">Live signals</h3>
            <span className="flex items-center gap-1 text-xs font-bold text-pine">
              <span className="h-2 w-2 animate-pulse rounded-full bg-pine" /> UPDATING
            </span>
          </div>
          <div className="mt-5 space-y-3">
            {weatherFactors.length === 0 && otherFactors.length === 0 && (
              <p className="text-sm text-slate-500">ไม่มีข้อมูลสัญญาณเพิ่มเติมในขณะนี้</p>
            )}
            {weatherFactors.map((f, i) => (
              <Signal key={`w-${i}`} icon={<Waves size={17} />} title="สภาพอากาศ" copy={f.description} />
            ))}
            {otherFactors.map((f, i) => (
              <Signal key={`o-${i}`} icon={<Route size={17} />} title={f.type} copy={f.description} />
            ))}
            <Signal
              icon={<Clock3 size={17} />}
              title={weatherAge != null ? `อัปเดตสภาพอากาศเมื่อ ${formatAge(weatherAge)}` : "อัปเดตล่าสุด"}
              copy={`แหล่งข้อมูล: ${recommendation.sources.map((s) => s.name).join(", ") || "—"}`}
            />
          </div>
        </article>
      </div>

      {recommendation.emergency_instructions && (
        <div className="mt-6 rounded-xl border border-red-400/30 bg-red-500/10 p-5 text-sm text-red-50">
          <p className="flex items-center gap-2 font-bold">
            <CircleAlert size={17} /> คำแนะนำฉุกเฉิน
          </p>
          <p className="mt-2 leading-6">{recommendation.emergency_instructions.what_to_do_now}</p>
          {recommendation.emergency_instructions.safety_steps.length > 0 && (
            <ul className="mt-3 space-y-1 text-red-100/90">
              {recommendation.emergency_instructions.safety_steps.map((step) => (
                <li key={step}>• {step}</li>
              ))}
            </ul>
          )}
          {recommendation.emergency_instructions.contacts.length > 0 && (
            <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-bold">
              {recommendation.emergency_instructions.contacts.map((c) => (
                <a key={c.phone} href={`tel:${c.phone}`} className="underline underline-offset-4">
                  {c.name}: {c.phone}
                </a>
              ))}
            </p>
          )}
        </div>
      )}

      {!recommendation.emergency_instructions && (
        <div className="mt-6 rounded-xl border border-[#9fcce8]/30 bg-[#9fcce8]/10 p-4 text-sm text-[#e0f3ff]">
          <CircleAlert className="mr-2 inline" size={17} />
          <b>ความเสี่ยงสูงหรือวิกฤต?</b> การ์ดเดียวกันนี้จะเปลี่ยนเป็นแผงคำแนะนำฉุกเฉิน พร้อมระดับความเสี่ยงแบบข้อความ ไอคอน ขั้นตอนรับมือ และเบอร์ติดต่อหน่วยงานทางการโดยอัตโนมัติ
        </div>
      )}
    </div>
  );
}

function IdleExample({ busy, message }: { busy: boolean; message: string | null }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.05fr_.95fr]">
      <article className="rounded-2xl bg-[#102e4e] p-6 sm:p-8">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-bold tracking-[.17em] text-white/55">
              ASSESSMENT · {busy ? "กำลังประมวลผล" : "EXAMPLE STATE"}
            </p>
            <div className="mt-6 flex items-center gap-3 text-[#b9e5fb]">
              {busy ? <LoaderCircle className="animate-spin" size={28} /> : <ShieldCheck size={28} />}
              <span className="font-bold">{busy ? (message ?? "กำลังตรวจสอบ…").toUpperCase() : "LOW RISK"}</span>
            </div>
            <h3 className="mt-3 font-display text-4xl sm:text-5xl">
              {busy ? "กำลังประเมินเส้นทางของคุณ…" : "Travel normally."}
            </h3>
          </div>
          <span className="rounded-full bg-white/10 p-3">
            {busy ? <LoaderCircle className="animate-spin" size={20} /> : <Check size={20} />}
          </span>
        </div>
        <p className="mt-7 max-w-md text-sm leading-7 text-white/70">
          {busy
            ? "โปรดรอสักครู่ ระบบกำลังตรวจสอบสภาพอากาศ การเดินทาง และประกาศภัยพิบัติที่เกี่ยวข้องกับเส้นทางของคุณ"
            : "กรอกแบบฟอร์มด้านบนแล้วกดส่ง เพื่อดูผลประเมินความเสี่ยงจริงของเส้นทางคุณตรงนี้"}
        </p>
        <div className="mt-8 grid grid-cols-2 border-t border-white/15 pt-5 text-sm">
          <div>
            <span className="text-white/50">Risk score</span>
            <b className="mt-1 block text-xl">{busy ? "…" : "18 / 100"}</b>
          </div>
          <div>
            <span className="text-white/50">Confidence</span>
            <b className="mt-1 block text-xl">{busy ? "…" : "High · 91%"}</b>
          </div>
        </div>
      </article>
      <article className="rounded-2xl bg-[#eef7fc] p-6 text-ink sm:p-8">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-2xl">Live signals</h3>
          <span className="flex items-center gap-1 text-xs font-bold text-pine">
            <span className="h-2 w-2 animate-pulse rounded-full bg-pine" /> UPDATING
          </span>
        </div>
        <div className="mt-5 space-y-3">
          <Signal icon={<Waves size={17} />} title="Light rain, 14:00–16:00" copy="Monitor the coastal sections." />
          <Signal icon={<Route size={17} />} title="Primary route remains open" copy="No active disruption along the route." />
          <Signal icon={<Clock3 size={17} />} title="Updated 2 minutes ago" copy="Sources: weather + transport services" />
        </div>
        <button className="mt-6 flex w-full items-center justify-between rounded-xl border border-ink/15 px-4 py-3 text-sm font-bold hover:bg-white">
          View data sources <ArrowUpRight size={16} />
        </button>
      </article>
    </div>
  );
}

function Signal({ icon, title, copy }: { icon: React.ReactNode; title: string; copy: string }) {
  return (
    <div data-card className="flex gap-3 rounded-xl bg-white p-3">
      <span className="mt-0.5 text-aqua">{icon}</span>
      <span>
        <b className="block text-sm">{title}</b>
        <small className="text-xs text-slate-500">{copy}</small>
      </span>
    </div>
  );
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${seconds} วินาทีที่แล้ว`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} นาทีที่แล้ว`;
  return `${Math.round(minutes / 60)} ชั่วโมงที่แล้ว`;
}
