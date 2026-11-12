# Attribute Engine for Landing Pages

Which attributes of your landing pages line up with conversion?

Give it your page URLs and a metric for each (conversion rate, signups, revenue
per visit). It opens each page, screenshots it, tags its words and how it looks,
and tests every tag against your metric. You see which opening angle, proof,
hero style and CTA treatment go with better numbers, plus which words and
phrases do.

Everything it finds is a correlation, not a cause. Treat results as hypotheses
to test, not answers.

The stats come from its sister repo,
[attribute-engine-ad-copy](https://github.com/redavio/attribute-engine-ad-copy).

## Install

Requires Python 3.10+ and Node 20+.

```
git clone https://github.com/redavio/attribute-engine-landing-pages && cd attribute-engine-landing-pages && pip install -e .
```

Then install the browser and the viewer:

```
playwright install chromium
cd web && npm install && cd ..
```

## See the sample (no keys, no cost)

```
waf example example
cd web && VIEWER_PASSCODE=pick-one npm run dev
```

Open http://localhost:3000 and enter your passcode. The sample is **Example Co,
a made-up company**. Its pages, screenshots, tags and rates are all illustrative,
with two effects planted on purpose (customer quotes and a prominent CTA) so you
can see the engine find them.

## Run it on your site

1. Copy the example config: `cp -r config/example config/mysite`
2. Put your pages and metric in `config/mysite/sample.csv`. Two columns, any
   order: `url` and your metric. 4 to 25 public pages. `4.2%` and `0.042` read
   the same; any other number is taken as it stands.

   ```
   url,conversion_rate
   https://www.yoursite.com/,3.1%
   https://www.yoursite.com/pricing,1.8%
   ```

3. Add keys: `cp .env.example .env`, then fill in
   - `OPENROUTER_API_KEY` from [OpenRouter](https://openrouter.ai), for Jev, which tags the copy.
     Jev is a small model by [TypeSafe](https://typesafe.ai) that answers multiple-choice
     questions about text.
   - `AI_GATEWAY_API_KEY` from [Vercel AI Gateway](https://vercel.com/ai-gateway), for Claude, which tags screenshots. Needs paid credits.
4. Run `waf sample mysite`, then start the viewer as above. Your results replace
   the sample.

Optional: `deploy.sh` and `scripts/setup_secrets.sh` put the run server on your
own Google Cloud project so people can paste URLs into the viewer and run them
live. Both read your project from environment variables.

## Where your data goes

- Your computer opens each URL you list and screenshots it.
- Page text goes to Jev through OpenRouter, and to Claude when you ask for
  attribute ideas. Screenshots go to Claude through Vercel AI Gateway. Your
  metric never leaves your machine.
- Page history mode also reads old versions from the Internet Archive.
- Nothing is sent to Redavio.
- The viewer is a Next.js app, which sends anonymous usage data to Vercel by
  default. Run `npx next telemetry disable` once to turn that off.

## Make it yours

- **Look:** colors and fonts live in one file, `web/src/theme.css`. The name in
  the header is in `web/src/components/brand.tsx`.
- **Attributes:** add or edit questions and options in
  `config/<site>/attributes.yaml`. Types: number, choice or yes/no. Set
  `default: true` to show one by default. No code changes.
- **Your brand name:** add it to `extra_stopwords` in the same file, so the
  word table skips it.
- **Page history (advanced):** `site.yaml` lists pages for `waf capture-live`,
  `waf capture-archive` (Internet Archive history) and `waf run`, which tags
  every version and tests them against a simulated metric. Replace
  `src/website_attribute_finder/simulate.py` with a reader for your analytics
  to use real numbers.

## Cost

About half a cent per page with the five default attributes: a 15-page run cost
under 7 cents. Adding more AI-tagged attributes adds a little per page. Results
are cached, so rerunning the stats costs nothing. The sample costs nothing.

## How it works

- Code counts (words, reading level, CTAs, colors, contrast). Jev tags the copy.
  Claude tags the screenshots.
- Tagging finishes before the metric is joined, so no model ever sees your numbers.
- Each attribute value is compared with the rest of the pages. P-values are
  adjusted for testing many things at once (Benjamini-Hochberg, 0.05).
- The five default attributes are tested as their own small set. Anything you
  add answers to a stricter bar, so adding one never changes the defaults.

## Limits

- Small samples. 25 pages is a lot of pages and very little data. Expect most
  results to come back not significant. That is the honest answer, not a bug.
- Correlation, not causation. A page with customer quotes may also have more
  traffic from warmer sources. Run an A/B test before you rewrite anything.
- Public pages only. Logins, private hosts and internal addresses are refused.
- Screenshots of pages with heavy animation or cookie walls can tag as unknown.

## Tests

```
pip install -e ".[test]"
pytest
```

## License

MIT. See `LICENSE`.
