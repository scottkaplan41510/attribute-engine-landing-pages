"use client";

import Link from "next/link";
import { BrandLockup } from "@/components/brand";
import { SAMPLE_BANNER } from "@/lib/results";
import { useRun } from "@/lib/run-context";

const NAV = [
  { href: "/", text: "Run" },
  { href: "/pages", text: "Pages" },
  { href: "/data", text: "About" },
];

export function Shell({ children, hero }: { children: React.ReactNode; hero?: React.ReactNode }) {
  const { result } = useRun();
  return (
    <>
      {result.sample && <div className="bg-warning px-4 py-2 text-center text-sm font-medium text-ink">{SAMPLE_BANNER}</div>}
      <header>
        <div className="mx-auto flex min-h-[60px] max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-3">
          <BrandLockup />
          <nav className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-zinc-900">
            {NAV.map((n) => <Link key={n.href} href={n.href} className="hover:text-zinc-700">{n.text}</Link>)}
          </nav>
        </div>
      </header>
      {hero}
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </>
  );
}
