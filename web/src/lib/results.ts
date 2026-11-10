import sampleData from "@/data/results.json";
import catalogData from "@/data/catalog.json";

export type ScoreRow = {
  attribute: string; value: string | null; kind: "group" | "number";
  n_with: number | null; mean_with: number | null; n_rest: number | null; mean_rest: number | null;
  lift: number | null; lift_pct: number | null; correlation: number | null;
  p_adjusted: number | null; significant: boolean; note?: string;
};
export type Page = {
  id: string; url: string; opening: string; ctas: string[]; fold_shot: string; full_shot: string;
  render_ok: boolean; conversion_rate: number; [key: string]: unknown;
};
export type Attribute = {
  name: string; title: string | null; question: string; computed_by: "code" | "label" | "jev" | "vision";
  type: "number" | "choice" | "boolean"; group: string; default: boolean; options: Record<string, string>;
};
export type WordRow = { term: string; pages: number; rate_with: number; rate_without: number; correlation: number; p_adjusted: number; significant: boolean };
export type WordTable = { tested: number; significant: number; terms: WordRow[] };
export type Result = {
  run_id: string; metric: string; pages: Page[]; skipped: number; sample: boolean; attributes: Attribute[];
  scorecards: Record<string, { rows: number; card: ScoreRow[] }>; words: Record<string, WordTable>;
};
export type Custom = { name: string; title: string; question: string; type: "boolean" | "choice"; options: Record<string, string> };

export const sample = { ...sampleData, sample: true } as unknown as Result;
export const catalog = catalogData as unknown as { attributes: Attribute[]; sample_csv: string; max_pages: number };
export const SAMPLE_BANNER = "Illustrative data. Not real analytics.";

export const label = (s: string) =>
  s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()).replace(/\bcta\b/gi, "CTA").replace(/\bui\b/gi, "UI");
export const pageName = (url: string) => url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");

/** Rates show as percentages. Any other metric shows as its own number. */
export function metricFormat(pages: Page[]) {
  const asRate = pages.every((p) => p.conversion_rate <= 1);
  return (n: number) => asRate ? `${(n * 100).toFixed(2)}%` : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
export const liftText = (share: number | null) => share == null ? "n/a" : `${share >= 0 ? "+" : ""}${Math.round(share * 100)}%`;
export const corrText = (r: number | null) => r == null ? "n/a" : r.toFixed(2);
export const pText = (p: number | null) => p == null ? "n/a" : p < 0.001 ? "<0.001" : p.toFixed(3);
export const attrTitle = (attrs: Attribute[], name: string) => attrs.find((a) => a.name === name)?.title ?? label(name);
export const attrOrigin = (attrs: Attribute[], name: string) => {
  const by = attrs.find((a) => a.name === name)?.computed_by;
  return by === "vision" ? "Screenshot" : by === "jev" ? "Jev" : "Counted";
};
