import type { Metadata } from "next";
import "./globals.css";
import { APP_NAME } from "@/components/brand";
import { RunProvider } from "@/lib/run-context";

export const metadata: Metadata = {
  title: APP_NAME,
  robots: { index: false, follow: false, noarchive: true, nocache: true },
};

export const viewport = { themeColor: "#121214" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><RunProvider>{children}</RunProvider></body>
    </html>
  );
}
