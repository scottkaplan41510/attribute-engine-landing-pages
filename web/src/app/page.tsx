import { Info, ResultsView } from "@/components/results-view";
import { Shell } from "@/components/shell";

const HERO = (
  <section className="bg-hero">
    <div className="mx-auto flex min-h-64 max-w-6xl items-end px-6 py-10">
      <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight text-zinc-900 sm:text-6xl">
        Landing Page Attribute Finder
        <Info text="Paste your pages and a metric. See which attributes go with better performance. Correlation, not cause." />
      </h1>
    </div>
  </section>
);

export default function Results() {
  return (
    <Shell hero={HERO}>
      <ResultsView />
    </Shell>
  );
}
