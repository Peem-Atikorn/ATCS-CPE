import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = { title: "WayPoint — Travel with clarity", description: "Travel safety intelligence powered by verified data." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="th"><body><Providers>{children}</Providers></body></html>;
}
