"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowUpRight, CalendarDays, LoaderCircle, MapPin, Navigation } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "@/lib/api";

const schema = z.object({ origin: z.string().min(2, "ระบุจุดเริ่มต้นอย่างน้อย 2 ตัวอักษร"), destination: z.string().min(2, "ระบุปลายทางอย่างน้อย 2 ตัวอักษร"), date: z.string().min(1, "เลือกวันเดินทาง"), mode: z.enum(["DRIVING", "WALKING", "TRANSIT"]), note: z.string().max(240).optional() });
type Form = z.infer<typeof schema>;
export function TravelForm() {
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { origin: "Bangkok", destination: "Chiang Mai", date: "2026-10-06", mode: "DRIVING", note: "" } });
  const mutation = useMutation({ mutationFn: (data: Form) => api.createRecommendation({ origin: { name: data.origin }, destination: { name: data.destination }, departure_at: `${data.date}T08:00:00+07:00`, mode: data.mode, preferences: { note: data.note } }) });
  return <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))} className="grid gap-3 text-left md:grid-cols-2">
    <Field icon={<Navigation size={16}/>} label="จุดเริ่มต้น" error={form.formState.errors.origin?.message}><input aria-label="Origin" {...form.register("origin")} /></Field>
    <Field icon={<MapPin size={16}/>} label="ปลายทาง" error={form.formState.errors.destination?.message}><input aria-label="Destination" {...form.register("destination")} /></Field>
    <Field icon={<CalendarDays size={16}/>} label="ออกเดินทาง"><input aria-label="Departure date" type="date" {...form.register("date")} /></Field>
    <Field icon={<Navigation size={16}/>} label="การเดินทาง"><select aria-label="Travel mode" {...form.register("mode")}><option value="DRIVING">ขับรถ</option><option value="TRANSIT">ขนส่งสาธารณะ</option><option value="WALKING">เดินเท้า</option></select></Field>
    <label className="md:col-span-2"><span className="mb-1 block text-xs font-bold tracking-wider text-slate-500">บอกเราเพิ่มเติม (ไม่บังคับ)</span><input className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-aqua" placeholder="เช่น มีผู้สูงอายุร่วมเดินทาง อยากเลี่ยงถนนเขา" {...form.register("note")} /></label>
    {mutation.isSuccess && <p role="status" className="md:col-span-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">ส่งคำขอแล้ว — ID: {mutation.data.id ?? mutation.data.job_id ?? "กำลังเตรียมผลลัพธ์"}</p>}
    {mutation.isError && <p role="alert" className="md:col-span-2 rounded-lg bg-red-50 p-3 text-sm text-red-800">ยังเชื่อมต่อ API ไม่ได้: ตั้งค่า NEXT_PUBLIC_API_BASE_URL ก่อนใช้งานจริง</p>}
    <button className="md:col-span-2 flex items-center justify-center gap-2 rounded-full bg-ink px-5 py-4 text-sm font-bold text-white transition hover:bg-pine disabled:opacity-60" disabled={mutation.isPending}>{mutation.isPending ? <LoaderCircle className="animate-spin" size={18}/> : <>ตรวจเส้นทางอย่างมั่นใจ <ArrowUpRight size={18}/></>}</button>
  </form>;
}
function Field({ icon, label, error, children }: { icon: React.ReactNode; label: string; error?: string; children: React.ReactNode }) { return <label><span className="mb-1 flex items-center gap-1.5 text-xs font-bold tracking-wider text-slate-500">{icon}{label}</span><div className="[&_input]:w-full [&_input]:rounded-xl [&_input]:border [&_input]:border-slate-200 [&_input]:bg-slate-50 [&_input]:px-4 [&_input]:py-3 [&_input]:text-sm [&_input]:outline-none [&_input]:focus:border-aqua [&_select]:w-full [&_select]:rounded-xl [&_select]:border [&_select]:border-slate-200 [&_select]:bg-slate-50 [&_select]:px-4 [&_select]:py-3 [&_select]:text-sm">{children}</div>{error && <span className="mt-1 block text-xs text-red-700">{error}</span>}</label>; }
