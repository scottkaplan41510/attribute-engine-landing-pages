"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Shell } from "@/components/shell";
import { label, metricFormat, pageName, type Attribute } from "@/lib/results";
import { useRun } from "@/lib/run-context";

function Detail() {
  const { result } = useRun();
  const id = useSearchParams().get("id");
  const page = result.pages.find((p) => p.id === id);
  if (!page) return <p className="text-zinc-600">Page not found.</p>;
  const value = (a: Attribute) => a.type === "number"
    ? String(page[a.name] ?? "n/a")
    : label(String(page[`jev_${a.name}`] ?? "unknown"));
  return (
    <>
      <h1 className="text-2xl font-medium tracking-tight"><a href={page.url} target="_blank" rel="noreferrer" className="hover:underline">{pageName(page.url)}</a></h1>
      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_360px]">
        <div>
          <a href={page.full_shot} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-xl border border-zinc-200">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={page.fold_shot} alt={`Top of ${page.url}`} className="h-auto w-full" />
          </a>
        </div>
        <aside>
          <p className="text-sm text-zinc-500">{label(result.metric)}</p>
          <p className="text-3xl font-bold">{metricFormat(result.pages)(page.conversion_rate)}</p>
          <dl className="mt-6 text-sm">
            {result.attributes.map((a) => (
              <div key={a.name} className="flex justify-between gap-4 border-t border-zinc-100 py-1.5">
                <dt className="text-zinc-500">{a.title ?? label(a.name)}</dt>
                <dd className="text-right font-medium">{value(a)}</dd>
              </div>
            ))}
          </dl>
        </aside>
      </div>
    </>
  );
}

export default function PageDetail() {
  return (
    <Shell>
      <Suspense><Detail /></Suspense>
    </Shell>
  );
}
