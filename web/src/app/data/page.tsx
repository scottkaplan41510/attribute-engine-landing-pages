"use client";

import { Shell } from "@/components/shell";
import { useRun } from "@/lib/run-context";

export default function Data() {
  const { result } = useRun();
  return (
    <Shell>
      <article className="max-w-2xl">
        <h1 className="font-display text-4xl font-semibold tracking-tight">About</h1>
        {result.sample && (
          <>
            <h2 className="mt-6 font-semibold">Sample data</h2>
            <p className="mt-1 text-zinc-700">Example Co is a made-up company. Its pages, screenshots, tags and rates are all illustrative, with effects planted to show how the tool works. Run your own pages to see real results.</p>
          </>
        )}
        <h2 className="mt-6 font-semibold">How it stays honest</h2>
        <p className="mt-1 text-zinc-700">Code does all the math. AI tags pages and never sees your metric. Results are correlations, not causes.</p>
        <h2 className="mt-6 font-semibold">Your data</h2>
        <p className="mt-1 text-zinc-700">Run results are kept for 30 days, then deleted.</p>
        <h2 className="mt-6 font-semibold">Next</h2>
        <p className="mt-1 text-zinc-700">Connect Google Analytics, and store each page change as it happens.</p>
      </article>
    </Shell>
  );
}
