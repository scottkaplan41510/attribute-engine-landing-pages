"use client";

import { useRef, useState } from "react";
import { catalog, corrText, label, liftText, metricFormat, pText, sample, type Attribute, type Custom, type Result, type ScoreRow } from "@/lib/results";
import { useRun } from "@/lib/run-context";
import { getIdeas, startRun } from "@/lib/server";

const GROUPS = ["Words", "CTA", "Visuals", "Proof", "Layout"];
const WORDS = "words";
const STAGE: Record<string, string> = { capture: "Reading pages", tag: "Tagging", score: "Scoring" };
const FIELD = "h-9 rounded-lg border border-zinc-400 bg-transparent px-3 text-sm";
const BUTTON = "inline-flex h-9 items-center rounded-full px-4 font-medium ring-[1.5px] ring-inset ring-zinc-300 hover:ring-zinc-900";
const defaults = () => [...catalog.attributes.filter((a) => a.default).map((a) => a.name), WORDS];

export function Info({ text }: { text: string }) {
  return <span title={text} className="ml-1.5 cursor-help text-xs font-normal tracking-normal text-zinc-400">ⓘ</span>;
}

function Chip({ on, text, tip, onClick }: { on: boolean; text: string; tip?: string; onClick: () => void }) {
  return (
    <button onClick={onClick} title={tip} aria-pressed={on}
      className={`h-[30px] rounded-full px-3 text-sm ring-inset ${on ? "font-medium ring-[1.5px] ring-zinc-900" : "text-zinc-400 ring-1 ring-zinc-300 hover:ring-zinc-900"}`}>
      {on ? "✓ " : "+ "}{text}
    </button>
  );
}

function Step({ n, text, tip, children }: { n: number; text: string; tip?: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-sm uppercase tracking-[0.12em] text-zinc-400"><span className="mr-2">0{n}</span>{text}{tip && <Info text={tip} />}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function NumberResult({ row }: { row?: ScoreRow }) {
  if (!row) return <p className="mt-3 text-sm text-zinc-500">Same on every page</p>;
  const direction = (row.correlation ?? 0) > 0 ? "higher" : "lower";
  return (
    <p className="mt-3 text-sm text-zinc-700">
      {row.significant ? `More goes with ${direction} performance` : "No clear link"}
      <span className="mt-1 block text-xs text-zinc-500">Correlation {corrText(row.correlation)} · P-value {pText(row.p_adjusted)}</span>
    </p>
  );
}

function GroupResult({ rows, format }: { rows: ScoreRow[]; format: (n: number) => string }) {
  const shown = rows.filter((r) => r.value !== "unknown" && r.mean_with != null).sort((a, b) => b.mean_with! - a.mean_with!);
  const top = Math.max(...shown.map((r) => r.mean_with!));
  return (
    <ul className="mt-3 space-y-2.5">
      {shown.map((r) => {
        const wins = r.significant && r.correlation! > 0;
        return (
          <li key={r.value} className="text-sm">
            <div className="flex justify-between gap-3">
              <span className={wins ? "font-semibold" : "text-zinc-700"}>{label(r.value!)}</span>
              <span className="whitespace-nowrap text-zinc-500"><span className="font-medium text-zinc-900">{format(r.mean_with!)}</span> · {r.n_with} {r.n_with === 1 ? "page" : "pages"}</span>
            </div>
            <div className="mt-1 h-1.5 bg-zinc-300">
              <div className={`h-1.5 ${wins ? "bg-accent" : "bg-zinc-500"}`} style={{ width: `${top > 0 ? (r.mean_with! / top) * 100 : 0}%` }} />
            </div>
            <p className="mt-1 text-xs text-zinc-500">Lift {liftText(r.lift_pct)} · Correlation {corrText(r.correlation)} · P-value {pText(r.p_adjusted)}</p>
          </li>
        );
      })}
    </ul>
  );
}

function AttributeCard({ attr, card, format }: { attr: Attribute; card: ScoreRow[]; format: (n: number) => string }) {
  const rows = card.filter((r) => r.attribute === attr.name);
  return (
    <section className="bg-zinc-100 p-5">
      <h3 className="font-semibold">{attr.title ?? label(attr.name)}<Info text={attr.question} /></h3>
      {attr.type === "number" ? <NumberResult row={rows[0]} /> : <GroupResult rows={rows} format={format} />}
    </section>
  );
}

function WordsCard({ result, format }: { result: Result; format: (n: number) => string }) {
  const table = Object.values(result.words)[0];
  if (!table) return null;
  return (
    <section className="min-w-0 bg-zinc-100 p-5 sm:col-span-2">
      <h3 className="font-semibold">Words<Info text={`Filler and site-wide menu words are skipped. ${table.significant} of ${table.tested} cleared the significance bar.${result.sample ? " Nothing was planted on words, so this shows the format only." : ""}`} /></h3>
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-zinc-500">
            <tr>{["Word or phrase", "Pages", "With it", "Without it", "Lift", "Correlation", "P-value"].map((h) => <th key={h} className="py-2 pr-5 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {table.terms.map((t) => (
              <tr key={t.term} className="border-t border-zinc-100">
                <td className="py-2 pr-5 font-medium">{t.term}</td>
                <td className="py-2 pr-5">{t.pages}</td>
                <td className="py-2 pr-5">{format(t.rate_with)}</td>
                <td className="py-2 pr-5">{format(t.rate_without)}</td>
                <td className="py-2 pr-5">{liftText(t.rate_without ? (t.rate_with - t.rate_without) / t.rate_without : null)}</td>
                <td className="py-2 pr-5">{corrText(t.correlation)}</td>
                <td className="py-2 pr-5">{pText(t.p_adjusted)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AddYourOwn({ onAdd }: { onAdd: (c: Custom) => void }) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState<"boolean" | "choice">("boolean");
  const [answers, setAnswers] = useState("");
  const list = answers.split(",").map((a) => a.trim()).filter(Boolean);
  const ready = title.trim() && (type === "boolean" || list.length >= 2);
  const add = () => {
    onAdd({
      name: title, title: title.trim(), question: title.trim(), type,
      options: type === "choice" ? Object.fromEntries(list.map((a) => [a.toLowerCase().replace(/\W+/g, "_"), a])) : {},
    });
    setTitle(""); setAnswers("");
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add your own" aria-label="Your attribute" className={`${FIELD} w-56`} />
      <select value={type} onChange={(e) => setType(e.target.value as "boolean" | "choice")} aria-label="Answer type" className={FIELD}>
        <option value="boolean">Yes / No</option>
        <option value="choice">List</option>
      </select>
      {type === "choice" && <input value={answers} onChange={(e) => setAnswers(e.target.value)} placeholder="Answers, with commas" aria-label="Answers" className={`${FIELD} w-56`} />}
      <button disabled={!ready} onClick={add} className={`${BUTTON} disabled:opacity-40`}>Add</button>
    </div>
  );
}

export function ResultsView() {
  const { result, setResult } = useRun();
  const [csv, setCsv] = useState(catalog.sample_csv);
  const [on, setOn] = useState<string[]>(defaults);
  const [custom, setCustom] = useState<Custom[]>([]);
  const [ideas, setIdeas] = useState<Custom[]>([]);
  const [ideaCount, setIdeaCount] = useState(5);
  const [loadingIdeas, setLoadingIdeas] = useState(false);
  const [progress, setProgress] = useState<{ text: string; share: number } | null>(null);
  const [error, setError] = useState("");
  const file = useRef<HTMLInputElement>(null);

  const has = (name: string) => on.includes(name);
  const toggle = (name: string) => setOn((now) => has(name) ? now.filter((n) => n !== name) : [...now, name]);
  const core = catalog.attributes.filter((a) => a.default);
  const optional = catalog.attributes.filter((a) => !a.default);
  const yours = [...custom, ...ideas];
  const rowCount = Math.max(csv.trim().split("\n").filter(Boolean).length - 1, 0);
  const job = () => ({
    csv, selected: on.filter((n) => n !== WORDS), words: has(WORDS),
    custom: yours.filter((c) => has(c.name)),
  });
  const reset = () => { setOn(defaults()); setCustom([]); setIdeas([]); };

  const askIdeas = async () => {
    setLoadingIdeas(true); setError("");
    try { setIdeas(await getIdeas({ ...job(), count: ideaCount })); }
    catch (e) { setError((e as Error).message); }
    setLoadingIdeas(false);
  };

  const run = async () => {
    setError("");
    const isSample = csv.trim() === catalog.sample_csv.trim();
    const unchanged = isSample && !yours.some((c) => has(c.name)) && [...on].sort().join() === defaults().sort().join();
    if (unchanged) { setResult(sample); return; }
    setProgress({ text: "Starting", share: 0.02 });
    try {
      await startRun(job(), (event) => {
        if (event.stage === "done") setResult({ ...(event.result as Result), sample: isSample });
        else if (event.stage === "error") setError(String(event.message));
        else setProgress({
          text: `${STAGE[String(event.stage)]}${event.stage === "capture" ? ` ${event.done} of ${event.total}` : ""}`,
          share: event.stage === "capture" ? 0.05 + 0.6 * Number(event.done) / Number(event.total) : event.stage === "tag" ? 0.7 : 0.95,
        });
      });
    } catch (e) { setError((e as Error).message); }
    setProgress(null);
  };

  const format = metricFormat(result.pages);
  const { card } = Object.values(result.scorecards)[0];
  return (
    <>
      <Step n={1} text="Pages" tip={`Two columns: url and your metric. Up to ${catalog.max_pages} public pages.`}>
        <textarea value={csv} onChange={(e) => setCsv(e.target.value)} aria-label="Pages CSV" spellCheck={false}
          className="h-44 w-full rounded-lg border border-zinc-400 bg-transparent p-3 font-mono text-xs" />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <p className="mr-auto text-sm text-zinc-500">{rowCount} rows</p>
          <a className={BUTTON} download="pages-template.csv" href="data:text/csv,url,conversion_rate%0A">Template</a>
          <button className={BUTTON} onClick={() => file.current?.click()}>Upload CSV</button>
          <button className={BUTTON} onClick={() => setCsv("url,conversion_rate\n")}>Clear</button>
          <input ref={file} type="file" accept=".csv,text/csv" aria-label="Upload CSV" className="hidden"
            onChange={async (e) => { const f = e.target.files?.[0]; if (f) setCsv(await f.text()); }} />
        </div>
      </Step>
      <Step n={2} text="Attributes">
        <div className="flex flex-wrap gap-2">
          {core.map((a) => <Chip key={a.name} on={has(a.name)} text={a.title ?? label(a.name)} tip={a.question} onClick={() => toggle(a.name)} />)}
          <Chip on={has(WORDS)} text="Words" tip="Which real words go with better or worse performance?" onClick={() => toggle(WORDS)} />
          {custom.map((c) => <Chip key={c.name} on={has(c.name)} text={c.title} tip={c.question} onClick={() => toggle(c.name)} />)}
        </div>
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium underline underline-offset-4">Add more</summary>
          <div className="mt-2 space-y-3">
            {GROUPS.map((group) => (
              <div key={group}>
                <p className="text-xs font-medium text-zinc-500">{group}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {optional.filter((a) => a.group === group).map((a) => (
                    <Chip key={a.name} on={has(a.name)} text={a.title ?? label(a.name)} tip={a.question} onClick={() => toggle(a.name)} />
                  ))}
                </div>
              </div>
            ))}
            <AddYourOwn onAdd={(c) => { setCustom((now) => [...now, c]); setOn((now) => [...now, c.name]); }} />
          </div>
        </details>
        <button onClick={reset} className="mt-2 text-sm text-zinc-500 hover:underline">Reset</button>
      </Step>
      <Step n={3} text="AI ideas" tip="AI reads your pages, never your metric, and suggests attributes to check.">
        <div className="flex items-center gap-2">
          <select value={ideaCount} onChange={(e) => setIdeaCount(Number(e.target.value))} aria-label="How many ideas" className={FIELD}>
            {[3, 5, 8].map((n) => <option key={n}>{n}</option>)}
          </select>
          <button onClick={askIdeas} disabled={loadingIdeas || !!progress} className={`${BUTTON} disabled:opacity-40`}>{loadingIdeas ? "Thinking" : "Get AI ideas"}</button>
        </div>
        {ideas.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {ideas.map((c) => <Chip key={c.name} on={has(c.name)} text={c.title} tip={c.question} onClick={() => toggle(c.name)} />)}
          </div>
        )}
      </Step>
      <Step n={4} text="Run">
        <button onClick={run} disabled={!!progress} className="inline-flex h-12 items-center rounded-full bg-zinc-900 px-6 font-medium text-ink hover:bg-zinc-700 disabled:opacity-50">Run</button>
        {progress && (
          <div className="mt-3 max-w-md" role="status">
            <p className="text-sm text-zinc-600">{progress.text}</p>
            <div className="mt-1 h-1.5 bg-zinc-300"><div className="h-1.5 bg-accent" style={{ width: `${progress.share * 100}%` }} /></div>
          </div>
        )}
        {error && <p className="mt-3 text-sm font-medium text-critical" role="alert">{error}</p>}
      </Step>
      <Step n={5} text="Results" tip={`Lift compares pages with this option to all other pages. Correlation runs from -1 to 1. P-values are adjusted for testing many options; below 0.05 is significant, shown in the accent color.${result.sample ? " Everything in the sample is illustrative." : ""}`}>
        {result.skipped > 0 && <p className="mb-3 text-sm text-critical">{result.skipped} {result.skipped === 1 ? "page" : "pages"} could not be opened.</p>}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {result.attributes.map((a) => <AttributeCard key={a.name} attr={a} card={card} format={format} />)}
          <WordsCard result={result} format={format} />
        </div>
      </Step>
    </>
  );
}
