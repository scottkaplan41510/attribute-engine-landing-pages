"use client";

import Link from "next/link";
import { Shell } from "@/components/shell";
import { label, metricFormat, pageName } from "@/lib/results";
import { useRun } from "@/lib/run-context";

export default function Pages() {
  const { result } = useRun();
  const shown = result.attributes.filter((a) => a.type !== "number").slice(0, 4);
  const pages = [...result.pages].sort((a, b) => b.conversion_rate - a.conversion_rate);
  const format = metricFormat(result.pages);
  return (
    <Shell>
      <h1 className="font-display text-4xl font-semibold tracking-tight">Pages</h1>
      <div className="mt-5 overflow-x-auto">
        <table className="min-w-max text-left text-sm">
          <thead className="text-zinc-500">
            <tr>{["Page", ...shown.map((a) => a.title ?? label(a.name)), label(result.metric)].map((h) => <th key={h} className="py-2 pr-5 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr key={p.id} className="border-t border-zinc-100">
                <td className="max-w-64 truncate py-2 pr-5"><Link href={`/pages/detail?id=${p.id}`} title={p.url} className="font-medium underline underline-offset-4 hover:text-zinc-700">{pageName(p.url)}</Link></td>
                {shown.map((a) => <td key={a.name} className="py-2 pr-5">{label(String(p[`jev_${a.name}`] ?? "unknown"))}</td>)}
                <td className="py-2 pr-5">{format(p.conversion_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
