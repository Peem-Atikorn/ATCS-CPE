"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowUpRight, CalendarDays, LoaderCircle, MapPin, Navigation } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useTrip } from "@/components/trip-context";

const schema = z.object({
  origin: z.string().min(2, "ระบุจุดเริ่มต้นอย่างน้อย 2 ตัวอักษร"),
  destination: z.string().min(2, "ระบุปลายทางอย่างน้อย 2 ตัวอักษร"),
  date: z.string().min(1, "เลือกวันเดินทาง"),
  mode: z.enum(["CAR", "BUS", "TRAIN", "FLIGHT", "WALK"]),
  note: z.string().max(240).optional(),
});
type Form = z.infer<typeof schema>;

const BUSY_STATUS = new Set(["geocoding", "submitting", "streaming"]);
const STATUS_LABEL: Record<string, string> = {
  geocoding: "กำลังค้นหาตำแหน่งบนแผนที่…",
  submitting: "กำลังส่งคำขอไปยังเซิร์ฟเวอร์…",
  streaming: "กำลังประเมินความเสี่ยง…",
};

export function TravelForm() {
  const { status, submit, recommendation, usingMock } = useTrip();
  const busy = BUSY_STATUS.has(status);
  const form = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { origin: "Bangkok", destination: "Chiang Mai", date: "2026-09-28", mode: "CAR", note: "" },
  });

  return (
    <form
      onSubmit={form.handleSubmit((data) => void submit(data))}
      className="grid gap-3 text-left md:grid-cols-2"
    >
      <Field icon={<Navigation size={16} />} label="จุดเริ่มต้น" error={form.formState.errors.origin?.message}>
        <input aria-label="Origin" {...form.register("origin")} />
      </Field>
      <Field icon={<MapPin size={16} />} label="ปลายทาง" error={form.formState.errors.destination?.message}>
        <input aria-label="Destination" {...form.register("destination")} />
      </Field>
      <Field icon={<CalendarDays size={16} />} label="ออกเดินทาง">
        <input aria-label="Departure date" type="date" {...form.register("date")} />
      </Field>
      <Field icon={<Navigation size={16} />} label="การเดินทาง">
        <select aria-label="Travel mode" {...form.register("mode")}>
          <option value="CAR">ขับรถ</option>
          <option value="BUS">รถโดยสารประจำทาง</option>
          <option value="TRAIN">รถไฟ</option>
          <option value="FLIGHT">เครื่องบิน</option>
          <option value="WALK">เดินเท้า</option>
        </select>
      </Field>
      <label className="md:col-span-2">
        <span className="mb-1 block text-xs font-bold tracking-wider text-slate-500">บอกเราเพิ่มเติม (ไม่บังคับ)</span>
        <input
          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-aqua"
          placeholder="เช่น มีผู้สูงอายุร่วมเดินทาง อยากเลี่ยงถนนเขา"
          {...form.register("note")}
        />
      </label>

      {status === "success" && recommendation && (
        <p role="status" className="md:col-span-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
          ประเมินเสร็จแล้ว{usingMock ? " (ข้อมูลตัวอย่าง)" : ""} — เลื่อนลงไปดูผลที่{" "}
          <a href="#dashboard" className="font-bold underline underline-offset-2">
            แดชบอร์ดคำแนะนำ
          </a>
        </p>
      )}
      {status === "error" && (
        <p role="alert" className="md:col-span-2 rounded-lg bg-red-50 p-3 text-sm text-red-800">
          ไม่สามารถประเมินเส้นทางได้ในขณะนี้ ลองใหม่อีกครั้ง
        </p>
      )}

      <button
        className="md:col-span-2 flex items-center justify-center gap-2 rounded-full bg-ink px-5 py-4 text-sm font-bold text-white transition hover:bg-pine disabled:opacity-60"
        disabled={busy}
      >
        {busy ? (
          <>
            <LoaderCircle className="animate-spin" size={18} /> {STATUS_LABEL[status]}
          </>
        ) : (
          <>
            ตรวจเส้นทางอย่างมั่นใจ <ArrowUpRight size={18} />
          </>
        )}
      </button>
    </form>
  );
}

function Field({
  icon,
  label,
  error,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label>
      <span className="mb-1 flex items-center gap-1.5 text-xs font-bold tracking-wider text-slate-500">
        {icon}
        {label}
      </span>
      <div className="[&_input]:w-full [&_input]:rounded-xl [&_input]:border [&_input]:border-slate-200 [&_input]:bg-slate-50 [&_input]:px-4 [&_input]:py-3 [&_input]:text-sm [&_input]:outline-none [&_input]:focus:border-aqua [&_select]:w-full [&_select]:rounded-xl [&_select]:border [&_select]:border-slate-200 [&_select]:bg-slate-50 [&_select]:px-4 [&_select]:py-3 [&_select]:text-sm">
        {children}
      </div>
      {error && <span className="mt-1 block text-xs text-red-700">{error}</span>}
    </label>
  );
}
