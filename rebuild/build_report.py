import base64, pandas as pd, numpy as np, json, datetime as dt
from pathlib import Path
_R = Path(__file__).resolve().parent.as_posix()
D = f"{_R}/data"; O = f"{_R}/out"

def img(name):
    b = base64.b64encode(open(f"{O}/{name}", 'rb').read()).decode()
    return f'<img src="data:image/png;base64,{b}" alt="{name}">'

def table(df, fmt=None, index=False):
    return df.to_html(index=index, border=0, classes='tbl', float_format=lambda x: f"{x:.2f}", escape=False)

# ---------- numbers ----------
S16 = pd.read_csv(f"{O}/summary_v2_1635_C.csv")
S10 = pd.read_csv(f"{O}/summary_v2_1000_C.csv")
T = pd.read_csv(f"{O}/tier_performance.csv")
T1 = pd.read_csv(f"{O}/tier_performance_h1.csv")

def hz(S, cols):
    d = S[cols].copy()
    d.columns = ['lead (days)', 'n slots', 'MAE p/kWh', 'bias', 'inside P10–P90', 'inside P05–P95', 'naive MAE (slot last week)', 'neg AUC', 'neg AP', '<5p AUC', '<5p AP', '<10p AUC', '<10p AP', '>40p AUC', '>40p AP']
    for c in ['inside P10–P90', 'inside P05–P95']:
        d[c] = (d[c] * 100).round(0).astype(int).astype(str) + '%'
    return d
cols = ['horizon', 'n', 'mae', 'bias', 'cov10_90', 'cov05_95', 'mae_persist7', 'neg_auc', 'neg_ap', 'sub5_auc', 'sub5_ap', 'sub10_auc', 'sub10_ap', 'hi40_auc', 'hi40_ap']
tab16 = hz(S16, cols); tab10 = hz(S10[S10.horizon.astype(str).isin(['1', '2', '3'])], cols)

def tiers(T):
    rows = []
    for _, r in T.iterrows():
        rows.append({'event': {'neg': 'negative', 'sub5': '< 5p', 'sub10': '< 10p'}[r.event], 'lead days': r.days, 'base rate': f"{r.base_rate*100:.1f}%",
                     'possible': f"P ≥ {r.possible_thr*100:.0f}%: prec {r.possible_prec*100:.0f}% · recall {r.possible_rec*100:.0f}% · {r.possible_flags_per_day:.1f} flags/day",
                     'likely': f"P ≥ {r.likely_thr*100:.0f}%: prec {r.likely_prec*100:.0f}% · recall {r.likely_rec*100:.0f}% · {r.likely_flags_per_day:.1f}/day",
                     'very likely': f"P ≥ {r.very_likely_thr*100:.0f}%: prec {r.very_likely_prec*100:.0f}% · recall {r.very_likely_rec*100:.0f}% · {r.very_likely_flags_per_day:.1f}/day"})
    return pd.DataFrame(rows)
tierT = tiers(pd.concat([T1, T[T.days != '2-7']], ignore_index=True))

# Eunice live scorecard
E = pd.read_parquet(f"{D}/eunice_forward_preds_scored.parquet")
E3 = E[E.model_version == 'hgbt_quantile_v3_trough']
rows = []
for l in sorted(E3.lead_d.unique()):
    if l < 1 or l > 7: continue
    r = E3[E3.lead_d == l]
    rows.append({'lead (days)': int(l), 'n slots (14 regions)': len(r), 'MAE p/kWh': round(r.err.abs().mean(), 2), 'inside P10–P90': f"{r['cov'].mean()*100:.0f}%", 'negative slots': int(r.neg.sum()),
                 'MAE on negative slots': round(r.err[r.neg].abs().mean(), 1) if r.neg.any() else '–', 'negative slots with p05<0': f"{(r.p05[r.neg]<0).mean()*100:.0f}%" if r.neg.any() else '–',
                 'mean p_trough on negative slots': f"{r.p_trough[r.neg].mean()*100:.0f}%" if r.neg.any() else '–', 'MAE on >40p slots': round(r.err[r.value_inc_vat > 40].abs().mean(), 1)})
eunT = pd.DataFrame(rows)

css = """
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:1080px;margin:32px auto;padding:0 20px;color:#0b0b0b;line-height:1.5}
h1{font-size:26px;margin-bottom:4px} h2{font-size:20px;margin-top:36px;border-bottom:1px solid #e6e6e3;padding-bottom:4px} h3{font-size:16px;margin-top:24px}
p{margin:10px 0} .sub{color:#52514e;font-size:14px}
img{max-width:100%;height:auto;display:block;margin:12px 0}
.tbl{border-collapse:collapse;font-size:12.5px;margin:10px 0} .tbl th{background:#f0efec;text-align:left;padding:6px 8px;border-bottom:1px solid #c3c2b7} .tbl td{padding:5px 8px;border-bottom:1px solid #eee;vertical-align:top}
.box{background:#f7f7f5;border-left:4px solid #2a78d6;padding:10px 14px;margin:14px 0} .warn{border-left-color:#eb6834}
code{background:#f0efec;padding:1px 4px;border-radius:3px;font-size:12.5px} pre{background:#f0efec;padding:10px;overflow:auto;font-size:12px}
.small{font-size:12.5px;color:#52514e}
"""

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Eunice price-prediction rebuild — findings and plan</title><style>{css}</style></head><body>
<h1>Eunice price-prediction rebuild — findings and plan</h1>
<p class="sub">Prepared for Callum (RenewaBlox), 18 August 2026. Scope: domestic Agile, all 14 GSP regions, staged low-price flags (&lt;10p / &lt;5p / negative). Sources: the <code>eunice-platform</code> repo and its <code>data.sqlite</code>, the live app, Octopus / NESO / Elexon public APIs, and a rebuilt model back-tested in this workspace.</p>

<h2>1. Summary</h2>
<p><b>What is wrong today.</b> Eunice's live forward forecasts (model <code>hgbt_quantile_v3_trough</code>, 28 daily runs stored in your local <code>data.sqlite</code> between 21 May and 17 Aug 2026, 63k scored slots across the 14 regions) have a mean absolute error of about 4.8p/kWh, their P10–P90 band contains only 45% of actual prices (it should contain 80%), and — the crux — <b>beyond a one-day lead the model has no negative-price skill at all</b>: on the 1,319 negative-priced slots at lead ≥ 2 days, not one had a P05, P10 or median below zero, and the trough classifier's average probability on those slots was 1.1% (against 0.3% on positive slots — no usable separation). Errors on negative slots average 19–25p. High-price slots (&gt;40p) are under-predicted by 6–14p depending on lead. The app's "last 7 days backtest" (2.35p MAE) is optimistic because it is computed with <i>actual</i> weather and grid data rather than the forecasts the live model actually sees.</p>
<p><b>Why.</b> Reading <code>model.py</code>/<code>features.py</code>: (1) the only wind/demand/carbon features are Elexon WINDFOR/NDF (≈2–3 days) and NESO carbon intensity (48h); everything beyond that is imputed with <i>all-history hour-of-day medians</i>, so for days 3–7 the model literally cannot see a windy or sunny day coming; (2) the model is trained on actual weather (Open-Meteo archive) and actual FUELHH wind/demand, then served with forecasts and medians — a train/serve skew that shrinks everything toward the mean; (3) there is no lead-time feature, so the P10–P90 band is the same width on day 7 as on day 2; (4) sample weights decay with a 14-day half-life, so after a quiet fortnight the model has effectively forgotten what negative-price days look like (May 2026 had zero negative slots; June's were missed); (5) the trough classifier is fine in principle but starves on the same features.</p>
<p><b>What the rebuild achieves (back-tested honestly).</b> Using only information available at each forecast time — NESO's <i>archived</i> 14-day embedded wind &amp; solar forecasts (every hourly issue since 2024), NESO's archived 2–14 day demand forecasts, Elexon WINDFOR history, the published Agile prices, and calendar — a walk-forward test with monthly refits from Aug 2025 to Aug 2026 (region K, forecasts issued 16:35 for days 2–7) gives MAE 3.3p (2.6p at day 2, 3.9p at day 7 versus 5.5p for "same slot last week"), 77.5% coverage of the P10–P90 band after conformal calibration, and real tail skill: negative-price AUC 0.94 (0.98 at day 2), &lt;5p AUC 0.93, &lt;10p AUC 0.93. Like-for-like against Eunice's own live runs (7 Jun–17 Aug 2026, region K, lead ≥ 2): MAE 3.9p vs 5.1p, coverage 76% vs 45%, and at a 10% probability threshold the rebuilt model flags 51% of negative slots with 73% precision, where Eunice flags none. For "tomorrow" (issued 10:00, before the 16:00 publication) the rebuild reaches MAE 2.5p, negative-price AUC 0.98, and a day-level "any negative slot tomorrow" detector with AUC 0.96 (76% precision at 65% recall).</p>
<div class="box"><b>Recommendation in one line:</b> keep the product, replace the engine — as-of feature store built from archived NESO/Elexon forecasts, a lead-aware LightGBM quantile model with dedicated event heads for &lt;10p/&lt;5p/&lt;0p (and &gt;40p), conformal interval calibration, monthly refits on all history, one model for the wholesale-equivalent price mapped to all 14 regions by their exact tariff formulas, and a UI that shows staged probabilities per slot and per day. Working code for all of this is attached.</div>

<h2>2. Evidence: how Eunice performs today</h2>
<h3>2.1 Live forward runs scored against published prices</h3>
<p>Every daily run writes its 7-day forecast to the <code>prediction</code> table keyed by <code>generated_at</code>, so the true forward skill can be measured. The table below covers the v3 model (all 14 regions, forward runs only, 7 Jun–17 Aug 2026; lead = target day minus run day).</p>
{table(eunT)}
<p class="small">Lead 1 is the only lead where the model has WINDFOR/NDF/carbon-intensity forecasts; from lead 2 the imputed medians take over and tail skill vanishes. The v2 model (May–June runs, 24k slots) behaved the same way (MAE 3.1p, coverage 62%, 0% of negative slots reached by P10).</p>
<h3>2.2 What negative and sub-5p pricing looks like (region K, Oct 2024 → Aug 2026)</h3>
<p>2.0% of half-hours are negative (73 days with at least one negative slot), 5.7% are below 5p, 8.7% below 10p, 3.6% above 40p. Negatives cluster on weekends (Sun 5.9%, Sat 3.7% of slots vs ~1% on weekdays), overnight 02–05h (wind) and 11–15h (solar); April 2026 had 9.9% negative slots (Easter weekend reached −12p), June–July 2026 4–5%. The events are growing with solar capacity (NESO embedded solar capacity 16.4 → 23.3 GW over the period), so a model that forgets history under-estimates them structurally.</p>
{img('fig_tail_by_month.png')}
{img('fig_neg_heatmap.png')}
<h3>2.3 Tariff mechanics that simplify the problem</h3>
<p>All 14 regional Agile prices are affine transforms of one another (regressing each region on K gives R² ≥ 0.9997 with residual s.d. ≤ 0.12p): the off-peak multiplier ratios are exactly 2.0/2.1/2.2/2.3/2.4 ÷ 2.2 and the peak adders differ by 1–3p. Negative-price frequency is identical in every region (1.96–2.00%) because off-peak adders are ~0; the &lt;5p/&lt;10p frequencies differ slightly (5.3–5.9% and 8.0–9.6%). So one model of the wholesale-equivalent price serves all regions, with region-specific thresholds. (Shape Shifters is ≈ 0.52 × Agile + 9p off-peak, has never printed below 5.7p, and maps a negative wholesale hour to ≈ 7–10p; a "&lt;10p" flag is the commercial equivalent, out of scope for now.) Note also that <code>renewablox_dispatch.prices_halfhourly.da_price</code> in BigQuery is <b>not</b> the auction price Agile is built from (e.g. it prints +14–20 £/MWh on 25 May 2025 while Agile was negative, and it carries the 8 Jan 2025 system-price spike) — do not use it as the wholesale driver.</p>

<h2>3. Root causes in the code</h2>
<table class="tbl"><tr><th>Where</th><th>What happens</th><th>Effect</th></tr>
<tr><td><code>features.py: _impute_by_hour</code>, <code>ingest.py: ingest_grid_forecast</code></td><td>Grid forecast covers WINDFOR/NDF (~73 rows ≈ 3 days) and carbon intensity 48h; every later slot gets the all-history hour-of-day median.</td><td>Days 3–7: <code>wind_generation_mw</code>, <code>demand_mw</code>, <code>net_demand_mw</code>, <code>carbon_intensity_forecast</code> are climatology → no signal for the tails; the model regresses to the mean.</td></tr>
<tr><td><code>features.py: build_training_data</code> vs <code>build_forecast_features</code></td><td>Trains on <i>actual</i> Open-Meteo archive weather and <i>actual</i> FUELHH outturn; predicts with 7-day forecast weather + imputed grid.</td><td>Train/serve skew: sharp learned relationships fed with smooth inputs; also makes the in-app 7-day backtest optimistic (2.35p) versus live (4.8p).</td></tr>
<tr><td><code>model.py: RECENT_HALF_LIFE_DAYS = 14</code></td><td>Exponential sample weights, half-life two weeks (+ ×5 peak, ×6 low-price boosts).</td><td>Effective training set is a few weeks; rare tail regimes are forgotten after quiet spells; boosts distort the quantile levels instead of adding information.</td></tr>
<tr><td><code>features.py: FEATURE_COLS</code></td><td>No lead-time feature; weather is a single GB-weighted composite (10 m wind speed, GHI, temperature); no capacity, no per-hub wind, no D+1 known-price anchor for D+2.</td><td>Bands cannot widen with lead (coverage 45%); weak proxy for national wind/solar MW; capacity growth invisible.</td></tr>
<tr><td><code>model.py: _train_quantiles</code></td><td>Four independent HGBT quantile fits, no post-hoc calibration, no monotonic ordering.</td><td>Under-dispersed and occasionally crossing quantiles; nothing corrects coverage drift.</td></tr>
<tr><td><code>bmrs.py</code> docstring</td><td>"Forecast endpoints only retain the latest publication."</td><td>Not true for the datasets endpoints (<code>publishDateTimeFrom/To</code> works) and NESO archives every issue of its 14-day embedded forecast and 2–14 day demand forecast — the historical vintages needed for honest training exist.</td></tr>
</table>

<h2>4. The rebuilt approach</h2>
<h3>4.1 As-of feature store</h3>
<p>Every training row is built exactly as it would be at forecast time. Two daily origins: <b>16:35 London</b> (Eunice's cron; D+1 prices are published; targets D+2…D+7) and <b>10:00 London</b> ("tomorrow" before publication; targets D+1…D+7). Features:</p>
<table class="tbl"><tr><th>Group</th><th>Features (all as-of the origin)</th><th>Source (historic + live)</th></tr>
<tr><td>Calendar</td><td>half-hour index, weekday, weekend, England bank holiday, day-of-year sin/cos, month, peak flag (16–19h), <b>lead (days)</b></td><td>—</td></tr>
<tr><td>Embedded renewables</td><td>embedded wind MW, solar MW, load factors, capacities, target-day mean wind / max solar, renewables share proxy; same for the last known day and the deltas target − last known</td><td>NESO "Embedded Wind and Solar Forecasts" — 14 days ahead, hourly issues; archives 2019→2026 (used: Sep 2024→Aug 2026, 14.2M rows)</td></tr>
<tr><td>Transmission wind</td><td>WINDFOR MW at the target slot (available for lead ≤ 2), share of demand</td><td>Elexon Insights <code>/datasets/WINDFOR</code> by publish time (406k rows pulled)</td></tr>
<tr><td>Demand</td><td>ND forecast interpolated to the slot from NESO cardinal points; day min/max/mean; last-known-day values and deltas</td><td>NESO 1-day, 7-day and 2–14 day ahead demand forecast archives</td></tr>
<tr><td>Price memory</td><td>same slot last week (always known for lead ≤ 7), same slot on last known day, last known day's mean/min/max/off-peak mean, 7- and 30-day rolling mean/min and counts of negative and &lt;5p slots, 7-day mean by slot</td><td>Octopus API</td></tr></table>
<h3>4.2 Model</h3>
<p>LightGBM (regularised: 31 leaves, min 200 rows per leaf, 450 rounds at learning rate 0.03), trained on <b>all</b> history each month. Target = price minus the last known day's off-peak mean (a "level" anchor that absorbs gas-price regime shifts); seven quantiles (5/10/25/50/75/90/95) sorted to be monotone; four binary heads for &lt;0p, &lt;5p, &lt;10p and &gt;40p. Interval calibration is <b>conformal</b>: on the most recent 8 weeks of resolved forecasts, per lead, the P10–P90 and P05–P95 margins are widened (or narrowed) so that empirical coverage hits 80%/90%, and the median bias is removed; raw coverage was 64%, calibrated 77.5% (86% for P05–P95). Rolling isotonic recalibration of the event probabilities was tested and <i>rejected</i> — with two-month windows it over-fits the previous regime (AUC fell 0.94→0.90); the raw probabilities rank well and are only mildly under-confident in the 5–40% range, so tier thresholds are set on raw probabilities (below).</p>
<h3>4.3 Back-test results (walk-forward, monthly refits, Aug 2025 → Aug 2026, region K)</h3>
<p><b>Issued 16:35, days 2–7</b> (108,996 slots, 381 origins):</p>
{table(tab16)}
<p><b>Issued 10:00 ("tomorrow" and beyond), days 1–3</b> (54,858 slots):</p>
{table(tab10)}
<p class="small">AUC = probability the model ranks a random event slot above a random non-event slot (0.5 = no skill). AP = average precision (area under the precision–recall curve; the base rates are 2.3% for negative, 6.3% for &lt;5p, 9.5% for &lt;10p, 2.7% for &gt;40p). "Naive" = the same slot one week earlier.</p>
{img('fig_eunice_vs_rebuilt.png')}
<p class="small">The Eunice line is its live runs (Jun–Aug 2026, all regions); the rebuilt line is the 12-month walk-forward (region K). On the identical window (7 Jun–17 Aug 2026, region K, lead ≥ 2): rebuilt MAE 3.88p vs Eunice 5.14p; P10–P90 coverage 75.5% vs 44.5%; negative-price AUC 0.978 vs 0.678; on negative slots the rebuilt P05 is below zero 53% of the time vs 0%.</p>
{img('fig_monthly_mae.png')}
<p class="small">March 2026 was the hardest month (a sharp level shift; naive error 10p) and coverage dipped to 42% before the conformal margins caught up in April — the calibration window should shrink automatically when recent errors jump (see roadmap).</p>
<h3>4.4 The staged flags — what "clear indication" looks like</h3>
{img('fig_example_easter2026.png')}
<p class="small">Forecast issued Thursday 9 April 16:35. Saturday 11 and Sunday 12 April carried &lt;10p probabilities of 60–85% and &lt;5p probabilities of 40–60% across the daytime block, two and three days ahead; the P05 band crossed zero; the deep −12p depth was under-called by the median (medians of rare events always are — the probabilities and lower quantiles carry the tail). Weekday peaks and Wednesday's midday dip were captured.</p>
{img('fig_reliability_pr.png')}
<p>Reliability (left) is close to the diagonal and slightly under-confident between 5% and 40%: when the model says "15%", it happens ~35% of the time. Precision–recall (right) shows the trade-off you can pick per lead. The tiers below use raw probabilities and read as follows for the walk-forward year (precision = share of flags that were right; recall = share of events flagged; flags/day = how often a tier lights up on an average day):</p>
{table(tierT)}
<p>Suggested product behaviour, per region: show every slot's P(&lt;10p), P(&lt;5p), P(&lt;0p) as a stacked bar under the price fan (as in the chart above), and roll them up per day into a sentence, e.g. "<b>Sat 11 Apr — very likely &lt;10p 09:00–16:00 (P 70–85%), likely &lt;5p 11:00–15:00 (P 40–60%), negative possible 12:00–14:00 (P ≈ 20%)</b>". At day level the "any negative slot" question is well answered even at long leads (AUC 0.94 at day 2, 0.88 at day 5, 0.79 at day 7; for tomorrow AUC 0.955), so the daily headline is the most robust element of the UI; slot-level probabilities become indicative beyond day 4 and should be styled that way (lighter, "outlook").</p>
{img('fig_example_june2026.png')}

<h2>5. What to build — implementation plan</h2>
<h3>Phase 1 (1–2 weeks): replace the engine, keep the app</h3>
<p>Adopt the attached pipeline: <code>fetch_octopus.py</code>, <code>fetch_neso.py</code>, <code>fetch_elexon.py</code>, <code>build_asof_embedded.py</code>, <code>build_features.py</code>, <code>add_lastknown_feats.py</code>, <code>train_eval_v2.py</code>. Concretely: (a) run the NESO/Elexon backfills once (already done here — the parquet files are in the bundle) and add a nightly job that appends the latest issues (the archives lag by weeks; the live NESO CSVs and Elexon endpoints fill the gap); (b) build the two origin datasets (16:35 and 10:00) and train the LightGBM quantile + event heads on all history, refit weekly or monthly, calibrate conformally on the last 8 weeks per lead; (c) predict for region K's wholesale-equivalent price and map to the 14 regions with the fitted affine coefficients (in the bundle as <code>region_affine.csv</code>); (d) write the new columns to <code>prediction</code> (p05…p95, p_neg, p_sub5, p_sub10, p_hi40) and change the app's spike/trough panels into the staged flags above; (e) replace the in-app "backtest" with a live scorecard computed from stored vintages (the query in section 2.1), so the app reports the skill it actually has.</p>
<h3>Phase 2 (weeks 3–4): weather at horizon</h3>
<p>Add horizon-honest NWP: Open-Meteo's <i>Previous Runs</i> API gives, for any point and day, what the model forecast 1…7 days earlier (100 m wind at ~10 offshore/onshore wind hubs, GHI at solar regions, temperature at demand centres). That is the correct way to train days 3–7 on forecasts rather than actuals. Its free tier is rate-limited (this workspace's shared quota was exhausted today, which is why the prototype leans on NESO's embedded forecasts as the D+3…D+7 wind/solar signal); a paid Open-Meteo key (~€30/month) or ECMWF open data solves it. Also start archiving NESO's 14-day national wind forecast daily (NESO does not archive it) and Elexon NDFD/TSDFD 2–14 day demand.</p>
<h3>Phase 3 (month 2): sharpen the extremes and the level</h3>
<p>Peak (&gt;40p) under-prediction: add a peak-level anchor (last known day's 16–19h mean) alongside the off-peak level, and a "&gt;40p"/"&gt;60p" head with its own tiers. Level shifts: make the conformal window adaptive (halve it when the last 7 days' errors exceed twice the window's), add a gas-price regime proxy (recent off-peak level already helps; a daily NBP price feed would be better). Deep-negative depth: a separate regression on the negative-slot subset conditioned on renewables surplus. Optional: per-region fine-tuning of peak adders (they change with each tariff version — re-fit the affine map monthly).</p>
<h3>Storage and scheduling</h3>
<p>Keep GitHub Actions for the daily job (it already runs at 16:35 UTC; add a 09:45 UTC run for the "tomorrow" forecast) but move data out of the LFS/SQLite juggling into BigQuery: datasets in <code>europe-west2</code> with tables <code>tariff</code>, <code>forecast_vintages</code> (source, issue_time, target_time, variable, value), <code>predictions</code> (origin_time, region, target_time, quantiles, probabilities, model_version) and a view <code>scorecard</code>. BigQuery's on-demand tier will cost pennies at these volumes and lets you (and me) query the history without shipping a 146 MB file. Streamlit reads the small daily extract as it does now.</p>

<h2>6. What I need from you</h2>
<p><b>Have now:</b> the repo (via the connected folder — thank you), the local <code>data.sqlite</code>, all public feeds. <b>Would help:</b> (1) the production <code>data.sqlite</code> from the GitHub Actions cache (it should hold every daily run since spring, not just the 28 runs on your laptop) so the live scorecard starts with real history; (2) an Open-Meteo API key (paid tier) or your Met Office DataHub key extended to the site-specific hourly forecast for the wind hubs — one of these unlocks Phase 2; (3) a BigQuery dataset in your project for the pipeline to write to (a service account with <code>bigquery.dataEditor</code>; keep the key in GitHub Secrets, not in the repo — I never need to see it); (4) confirmation of the tier thresholds and wording you want in the UI (I've proposed possible/likely/very likely at raw P ≥ 8/25/50% for negative and ≥ 10/30/60% for &lt;5p and &lt;10p); (5) later, for commercial: whether Shape Shifters flags should be "wholesale negative" (≈ &lt;9.5p SS) or a fixed "&lt;10p".</p>

<h2>7. Caveats</h2>
<p>The back-test uses NESO's archived forecast issues; a small share of issues are missing (gaps of 1–4 days in Jul 2024, May and Nov 2025, Feb 2026) and the model then falls back to the latest available issue — production will be at least as good. The 10:00-origin results assume prices for day D are known at 10:00 (they are, published the previous afternoon). Results are for region K; other regions are affine images of K to within 0.12p, but their peak-adder tiers should be checked once the region mapping is live. Eunice's live scorecard covers 28 runs from your laptop copy of the database; the production cache may contain more, which would only sharpen the comparison. All figures are inc-VAT p/kWh unless stated.</p>

<h2>Appendix — bundle contents</h2>
<pre>eunice_rebuild/
  README.md                      how to run the pipeline end-to-end
  fetch_octopus.py               Agile / Shape Shifters unit-rate history, all regions
  fetch_neso.py                  NESO archives (embedded wind/solar 14d, demand cardinal points, historic demand)
  fetch_elexon.py                Elexon WINDFOR history, actual wind/solar, demand outturn
  build_asof_embedded.py         DuckDB as-of extraction of the 14M-row embedded-forecast archive (16:35 and 10:00 origins)
  build_features.py              feature store per origin (calendar, renewables, demand, price memory), targets and flags
  add_lastknown_feats.py         last-known-day driver features and deltas
  train_eval_v2.py               walk-forward training, conformal calibration, event heads, summary
  charts_data.py / charts_results.py   the figures in this report
  score_eunice_live.py           scores Eunice's stored forward runs against published prices (section 2.1)
  region_affine.csv              per-region affine map from region K (off-peak and peak)
  out/summary_v2_*.csv, out/tier_performance*.csv, out/preds_v2_*.parquet   back-test outputs
</pre>
<p class="small">Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} UTC.</p>
</body></html>"""
open(f"{O}/eunice_rebuild_report.html", 'w').write(html)
print('report written', len(html))
