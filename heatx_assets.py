"""Self-contained HTML assets for Eunice HeatX (app_heatx.py).

Both blocks are rendered via st.iframe inside a sandboxed
iframe, so they carry their own styles. The explorer's equations are
IDENTICAL to sizing_model.py — if the model changes, change both
(see HANDOVER.md: mirror, don't fork). Palette matches the Eunice
Streamlit theme (light, emerald primary).
"""

EXPLORER_HTML = """<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<style>
  body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#0f172a;background:#ffffff;margin:0;padding:0 2px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:0 0 1.25rem}
  .card{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:.9rem 1rem}
  .card p{margin:0}
  .lbl{font-size:13px;color:#64748b;margin-bottom:4px!important}
  .val{font-size:24px;font-weight:600}
  .row{display:flex;align-items:center;gap:12px;margin:0 0 .8rem}
  .row label{font-size:14px;color:#64748b;min-width:160px}
  .row input[type=range],.row select{flex:1;accent-color:#10b981}
  .row select{padding:4px 8px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;font-size:14px}
  .row .out{font-size:14px;font-weight:600;min-width:64px;text-align:right}
  #barwrap{height:10px;border-radius:5px;background:#f1f5f9;overflow:hidden;margin:0 0 .4rem}
  #bar{height:100%;width:0;background:#10b981;transition:width .2s}
  #warn{font-size:13px;color:#854f0b;min-height:20px;margin:0 0 1rem}
  .cap{font-size:13px;color:#64748b;margin:1rem 0 6px}
  svg{width:100%;height:auto;display:block}
</style>
</head>
<body>
<div class="grid">
  <div class="card"><p class="lbl">Tubes that fit</p><p class="val" id="oN">–</p></div>
  <div class="card"><p class="lbl">Finned tube length</p><p class="val" id="oL">–</p></div>
  <div class="card"><p class="lbl">Effective area</p><p class="val" id="oA">–</p></div>
  <div class="card"><p class="lbl">Estimated duty</p><p class="val" id="oQ">–</p></div>
</div>

<div style="display:flex;justify-content:space-between;font-size:13px;color:#64748b;margin-bottom:.5rem"><span>Progress to 1 MW</span><span id="oPct">–</span></div>
<div id="barwrap"><div id="bar"></div></div>
<p id="warn"></p>

<div class="row"><label for="iD">Tube OD</label>
  <select id="iD"><option value="25">25 mm</option><option value="38">38 mm</option><option value="50">50 mm</option><option value="63" selected>63 mm</option></select>
  <span class="out"></span></div>
<div class="row"><label for="iP">Tube pitch</label>
  <input type="range" id="iP" min="60" max="250" step="5" value="150"><span class="out" id="vP">150 mm</span></div>
<div class="row"><label for="iF">Fin area multiplier</label>
  <input type="range" id="iF" min="1" max="3.5" step="0.1" value="3"><span class="out" id="vF">3.0×</span></div>
<div class="row"><label for="iU">Design U (fouled)</label>
  <input type="range" id="iU" min="300" max="900" step="10" value="480"><span class="out" id="vU">480</span></div>
<div class="row"><label for="iT">Glycol supply (ΔT 10 K)</label>
  <input type="range" id="iT" min="45" max="60" step="1" value="50"><span class="out" id="vT">50 °C</span></div>
<div class="row"><label for="iR">River temperature</label>
  <input type="range" id="iR" min="4" max="18" step="1" value="10"><span class="out" id="vR">10 °C</span></div>
<label style="display:flex;align-items:center;gap:8px;font-size:14px;color:#64748b;margin-bottom:1.25rem;cursor:pointer">
  <input type="checkbox" id="iPipe" checked style="accent-color:#10b981"> Include DN125 submerged runs (+13.35 m² bare, derated 30%)
</label>

<p class="cap">Bundle cross-section — 0.9 m along flow × 0.8 m deep, viewed side-on (dashed halo = fin envelope)</p>
<svg viewBox="0 0 680 420" role="img" aria-label="Cross-section of the tube bundle at the selected pitch">
  <text x="40" y="200" font-size="12" fill="#64748b">flow →</text>
  <rect x="150" y="20" width="378" height="336" rx="4" fill="rgba(55,138,221,0.08)" stroke="#378add" stroke-width="0.8"/>
  <g id="tubes"></g>
  <text x="339" y="378" text-anchor="middle" font-size="12" fill="#64748b" id="gridLbl"></text>
  <text x="339" y="398" text-anchor="middle" font-size="12" fill="#64748b" id="blkLbl"></text>
</svg>

<script>
const $=id=>document.getElementById(id);
function calc(){
  const D=+$('iD').value,p=+$('iP').value,F=+$('iF').value,U=+$('iU').value,
        Tin=+$('iT').value,Tr=+$('iR').value,Tout=Tin-10,
        finOD=D*(1+0.4*(F-1));
  $('vP').textContent=p+' mm';$('vF').textContent=F.toFixed(1)+'\\u00d7';
  $('vU').textContent=U;$('vT').textContent=Tin+' \\u00b0C';$('vR').textContent=Tr+' \\u00b0C';
  const nf=Math.floor(900/p),nv=Math.floor(800/p),N=nf*nv,L=N*0.85;
  const Ab=Math.PI*D/1000*L,Ae=Ab*F;
  const d1=Tin-Tr,d2=Tout-Tr;
  const dtlm=(d2>0&&d1!==d2)?(d1-d2)/Math.log(d1/d2):(d2>0?d1:0);
  const Q=U*Ae*dtlm/1000;
  const Qp=$('iPipe').checked?U*13.35*dtlm*0.7/1000:0;
  const tot=Q+Qp,pct=Math.min(100,Math.round(tot/10));
  $('oN').textContent=N;$('oL').textContent=Math.round(L)+' m';
  $('oA').textContent=Ae.toFixed(1)+' m\\u00b2';$('oQ').textContent=Math.round(tot)+' kW';
  $('oPct').textContent=Math.round(tot/10)+'%';
  const bar=$('bar');bar.style.width=pct+'%';
  bar.style.background=tot>=1000?'#10b981':(tot>=600?'#ef9f27':'#e24b4a');
  const w=[];
  if(p<finOD+20)w.push('fins clash or near-touch at this pitch \\u2014 dense radiator core, uncleanable');
  if(nf>7)w.push(nf+' tube rows along flow \\u2014 high head loss / backwater risk');
  if(d2<=0)w.push('glycol return at or below river temperature \\u2014 no driving force');
  $('warn').textContent=w.join(' \\u00b7 ');
  const s=0.42,x0=150,y0=20;let html='';
  for(let i=0;i<nf;i++)for(let j=0;j<nv;j++){
    const cx=(x0+(i+0.5)*p*s).toFixed(1),cy=(y0+(j+0.5)*p*s).toFixed(1);
    html+=`<circle cx="${cx}" cy="${cy}" r="${(finOD/2*s).toFixed(1)}" fill="none" stroke="#d85a30" stroke-width="0.8" stroke-dasharray="3 3" opacity="0.55"/>`;
    html+=`<circle cx="${cx}" cy="${cy}" r="${(D/2*s).toFixed(1)}" fill="#f0997b" stroke="#d85a30" stroke-width="1"/>`;
  }
  $('tubes').innerHTML=html;
  $('gridLbl').textContent=`${nf} columns \\u00d7 ${nv} rows = ${N} tubes \\u00b7 ${Math.round(L)} m`;
  $('blkLbl').textContent=`first-row solid blockage \\u2248 ${Math.round(nv*D/8)}% of depth \\u00b7 fin envelope ${Math.round(finOD)} mm`;
}
document.querySelectorAll('input,select').forEach(el=>el.addEventListener('input',calc));
calc();
</script>
</body>
</html>"""

FLOW_HTML = """<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<style>
  body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#0f172a;background:#ffffff;margin:0;padding:0 2px}
  p.cap{font-size:13px;color:#64748b;margin:0 0 4px}
  svg{width:100%;height:auto;display:block}
  @keyframes fm28{to{stroke-dashoffset:-28}}
  @keyframes fm36{to{stroke-dashoffset:-36}}
  .sup{stroke:#d85a30;stroke-width:3;fill:none;stroke-dasharray:8 6;animation:fm28 1.1s linear infinite}
  .ret{stroke:#f0997b;stroke-width:3;fill:none;stroke-dasharray:8 6;animation:fm28 1.1s linear infinite}
  .riv{stroke:#378add;stroke-width:1.5;fill:none;stroke-dasharray:10 8;animation:fm36 1.8s linear infinite;opacity:.7}
  .intk{stroke:#378add;stroke-width:2.5;fill:none;stroke-dasharray:8 6;animation:fm28 1.3s linear infinite}
  .amb{stroke:#ef9f27;stroke-width:3;fill:none;stroke-dasharray:8 6;animation:fm28 1.3s linear infinite}
  @media (prefers-reduced-motion:reduce){.sup,.ret,.riv,.intk,.amb{animation:none}}
  .box{fill:#f8fafc;stroke:#cbd5e1;stroke-width:1}
  .tp{fill:#0f172a;font-size:15px;font-weight:600}
  .ts{fill:#64748b;font-size:13px}
  .tx{fill:#64748b;font-size:12px}
</style>
</head>
<body>
<p class="cap">Option A — submerged finned coil, single closed loop</p>
<svg viewBox="0 0 680 470" role="img" aria-label="Option A: closed glycol loop from the data centre to a finned tube bundle submerged in the tailrace">
  <rect x="40" y="310" width="620" height="120" fill="rgba(55,138,221,0.10)"/>
  <line x1="40" y1="310" x2="660" y2="310" stroke="#378add" stroke-width="1" opacity="0.5"/>
  <line x1="40" y1="430" x2="660" y2="430" stroke="#378add" stroke-width="1" opacity="0.3"/>
  <path class="riv" d="M 50 332 H 650"/>
  <path class="riv" d="M 50 360 H 650"/>
  <path class="riv" d="M 50 390 H 650"/>
  <path class="riv" d="M 50 416 H 650"/>
  <line x1="70" y1="372" x2="125" y2="372" stroke="#94a3b8" stroke-width="1.5"/>
  <polygon points="125,367 137,372 125,377" fill="#94a3b8"/>
  <path class="sup" d="M 240 52 H 646 V 330 H 620"/>
  <path class="ret" d="M 620 358 H 600 V 80 H 240"/>
  <rect class="box" x="60" y="30" width="180" height="70" rx="8"/>
  <text class="tp" x="150" y="58" text-anchor="middle">Data centre</text>
  <text class="tx" x="150" y="80" text-anchor="middle">1 MW heat · 30% glycol loop</text>
  <circle cx="300" cy="80" r="9" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5"/>
  <line x1="300" y1="73" x2="300" y2="87" stroke="#94a3b8" stroke-width="1.5"/>
  <text class="tx" x="300" y="112" text-anchor="middle">circulation pump ≈6 kW</text>
  <text class="ts" x="440" y="42" text-anchor="middle">glycol supply 50 °C →</text>
  <text class="ts" x="445" y="102" text-anchor="middle">← return 40 °C</text>
  <text class="tx" x="590" y="244" text-anchor="end">DN125 runs · 17 m each</text>
  <text class="ts" x="40" y="300">from turbine</text>
  <rect x="470" y="318" width="150" height="104" rx="6" fill="#ffffff" stroke="#94a3b8" stroke-width="1.2" stroke-dasharray="4 3"/>
  <g fill="#f0997b" stroke="#d85a30" stroke-width="1.5">
    <circle cx="497" cy="338" r="9"/><circle cx="529" cy="338" r="9"/><circle cx="561" cy="338" r="9"/><circle cx="593" cy="338" r="9"/>
    <circle cx="497" cy="364" r="9"/><circle cx="529" cy="364" r="9"/><circle cx="561" cy="364" r="9"/><circle cx="593" cy="364" r="9"/>
    <circle cx="497" cy="390" r="9"/><circle cx="529" cy="390" r="9"/><circle cx="561" cy="390" r="9"/><circle cx="593" cy="390" r="9"/>
    <circle cx="497" cy="416" r="9"/><circle cx="529" cy="416" r="9"/><circle cx="561" cy="416" r="9"/><circle cx="593" cy="416" r="9"/>
  </g>
  <line x1="545" y1="424" x2="545" y2="444" stroke="#94a3b8" stroke-width="1" stroke-dasharray="3 3"/>
  <text class="ts" x="40" y="458">river ~10 °C · up to 1,300 L/s (≈1.6 m/s)</text>
  <text class="ts" x="530" y="458" text-anchor="middle">finned tube bundle — drop-in frame, annual lift-out</text>
</svg>

<p class="cap" style="margin-top:1.5rem">Option B — primary/secondary plate heat exchanger, open river loop</p>
<svg viewBox="0 0 680 566" role="img" aria-label="Option B: glycol loop to a plate heat exchanger with a pumped open river-water secondary circuit">
  <path class="sup" d="M 220 85 H 330"/>
  <path class="ret" d="M 330 125 H 220"/>
  <path class="intk" d="M 540 472 V 200 H 460"/>
  <path class="amb" d="M 460 110 H 640 V 470"/>
  <rect class="box" x="50" y="55" width="170" height="80" rx="8"/>
  <text class="tp" x="135" y="88" text-anchor="middle">Data centre</text>
  <text class="tx" x="135" y="110" text-anchor="middle">25.5 L/s glycol</text>
  <rect class="box" x="330" y="50" width="130" height="180" rx="8"/>
  <g stroke="#cbd5e1" stroke-width="1">
    <line x1="344" y1="62" x2="344" y2="218"/><line x1="358" y1="62" x2="358" y2="218"/><line x1="372" y1="62" x2="372" y2="218"/><line x1="386" y1="62" x2="386" y2="218"/><line x1="400" y1="62" x2="400" y2="218"/><line x1="414" y1="62" x2="414" y2="218"/><line x1="428" y1="62" x2="428" y2="218"/><line x1="442" y1="62" x2="442" y2="218"/>
  </g>
  <text class="tp" x="395" y="38" text-anchor="middle">Plate heat exchanger</text>
  <text class="tx" x="300" y="74" text-anchor="middle">50 °C</text>
  <circle cx="272" cy="125" r="9" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5"/>
  <line x1="272" y1="118" x2="272" y2="132" stroke="#94a3b8" stroke-width="1.5"/>
  <text class="tx" x="305" y="150" text-anchor="middle">40 °C</text>
  <text class="tx" x="240" y="172" text-anchor="middle">primary pump 4.4–5.8 kW</text>
  <circle cx="540" cy="385" r="9" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5"/>
  <line x1="540" y1="378" x2="540" y2="392" stroke="#94a3b8" stroke-width="1.5"/>
  <text class="tx" x="522" y="389" text-anchor="end">river pump 5.5–8.2 kW</text>
  <rect x="528" y="428" width="24" height="16" rx="3" fill="rgba(55,138,221,0.15)" stroke="#378add" stroke-width="1.2"/>
  <text class="tx" x="520" y="441" text-anchor="end">strainer</text>
  <text class="tx" x="630" y="300" text-anchor="end">≈15 °C</text>
  <text class="ts" x="40" y="462">river / tailrace ~10 °C</text>
  <rect x="40" y="470" width="620" height="70" fill="rgba(55,138,221,0.10)"/>
  <line x1="40" y1="470" x2="660" y2="470" stroke="#378add" stroke-width="1" opacity="0.5"/>
  <path class="riv" d="M 50 495 H 650"/>
  <path class="riv" d="M 50 520 H 650"/>
  <text class="ts" x="350" y="560" text-anchor="middle">Open secondary loop: 47.8 L/s drawn, warmed +5 °C, returned downstream</text>
</svg>
</body>
</html>"""
