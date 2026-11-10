/* Engineering 2.0 (tools/story_lab.py): progressive enhancement for the Weakest Links filter, the Breakthrough Lab scenario builder
   and the Ship Evolution envelope picker. Every number shown comes from the precomputed record embedded in the page (#bt-data); this
   script only selects a case and formats its recorded values. It never computes, scales or interpolates a mass or a performance value. */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const DIGITS = { departure_t: 0, propellant_t: 0, thrust_MN: 2, peak_g: 4, burn_years: 2, min_round_trip_years: 2, pellet_rate_Hz: 0,
    gain: 0, stand_off_m: 1, hot_GW: 0, warm_GW: 0, hot_km2: 2, warm_km2: 2, wing_tip_radius_m: 2 };
  const SCALE = { wing_tip_radius_m: 1e-3 };
  function num(k, v) {
    if (typeof v !== 'number' || !isFinite(v)) return '–';
    const d = DIGITS[k] === undefined ? 2 : DIGITS[k];
    return (v * (SCALE[k] || 1)).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  const badge = (kind, value, text) => `<span class="bt bt-${esc(kind)} bt-${esc(kind)}-${esc(value)}">${esc(text || value)}</span>`;

  /* ---------------------------------------------------------------- Weakest Links filter */
  const wf = $('form[data-filter=wl]');
  if (wf) {
    wf.hidden = false;
    const cards = $$('.wl');
    const rows = $$('.register-summary tbody tr');
    const apply = () => {
      const f = Object.fromEntries(new FormData(wf));
      let n = 0;
      cards.forEach((c) => {
        const show = (!f.tier || c.dataset.tier === f.tier) && (!f.subsystem || c.dataset.subsystem === f.subsystem)
          && (!f.speculative || c.dataset.speculative === f.speculative) && (!f.q || c.dataset.text.includes(f.q.toLowerCase().trim()));
        c.hidden = !show;
        if (show) n++;
      });
      rows.forEach((r) => { const id = r.querySelector('a').getAttribute('href').slice(1); r.hidden = document.getElementById(id).hidden; });
      wf.elements.count.value = `${n} of ${cards.length} shown`;
    };
    wf.addEventListener('input', apply);
    wf.addEventListener('submit', (e) => e.preventDefault());
    apply();
  }

  const dataEl = $('#bt-data');
  if (!dataEl) return;
  let D;
  try { D = JSON.parse(dataEl.textContent); } catch (e) { return; }
  const BT = Object.fromEntries(D.breakthroughs.map((b) => [b.id, b]));
  const keyOf = (levels) => D.order.map((b) => `${b}:${levels[b]}`).join('|');
  const parseKey = (k) => { const o = {}; k.split('|').forEach((p) => { const [b, l] = p.split(':'); o[b] = l; }); return o; };
  const valid = (k) => Object.prototype.hasOwnProperty.call(D.cases, k);
  const levelOf = (b, key) => BT[b].levels.find((x) => x.key === key);

  /* ---------------------------------------------------------------- Breakthrough Lab builder */
  const form = $('form[data-lab]');
  const out = $('[data-result]');
  if (form && out) {
    const custom = {};   // lever id -> {value, state} when a value outside the level table was typed
    const levels = () => {
      const o = {};
      D.order.forEach((b) => { const r = form.querySelector(`input[name="${b}"]:checked`); o[b] = r ? r.value : 'L0'; });
      return o;
    };
    const setLevels = (lv) => {
      D.order.forEach((b) => { const r = form.querySelector(`input[name="${b}"][value="${lv[b]}"]`); if (r) r.checked = true; delete custom[b]; });
      $$('input[type=number]', form).forEach((i) => { i.value = ''; });
    };
    const panel = (title, c, ref) => {
      const s = (c && c.summary) || {};
      const rs = (ref && ref.summary) || {};
      const rows = D.cmp.map((k) => `<tr><td>${esc(D.labels[k][0])}</td><td class="num">${num(k, s[k])} ${s[k] !== undefined ? esc(D.labels[k][1]) : ''}</td>`
        + (ref ? `<td class="num delta">${num(k, rs[k])}</td>` : '') + '</tr>').join('');
      const why = c && c.reason ? `<p class="note">Calculator: ${esc(c.reason)}${c.max_a0_g !== undefined ? `; the most it reaches is ${c.max_a0_g.toFixed(4)} g` : ''}.</p>` : '';
      return `<div class="panel"><h3>${esc(title)}</h3><p class="scenario-status">${c ? badge('st', c.status, D.vocab.status[c.status]) : ''}</p>${why}`
        + `<table>${ref ? '<thead><tr><th></th><th>This case</th><th>V4</th></tr></thead>' : ''}<tbody>${rows}</tbody></table></div>`;
    };
    const render = () => {
      const lv = levels();
      const k = keyOf(lv);
      let c = D.cases[k];
      let note = '';
      const cust = Object.entries(custom);
      if (cust.length) {
        const over = cust.filter(([, x]) => x.state === 'OUT_OF_RANGE');
        c = { status: over.length ? 'OUT_OF_RANGE' : 'NOT_COMPUTED', levels: lv };
        note = over.length
          ? `Out of range: ${over.map(([b, x]) => `${b} ${esc(x.path)} = ${esc(x.value)} is beyond the limit ${BT[b].limit.max} (${esc(BT[b].limit.why)})`).join('; ')}. The calculators are not asked beyond their validity.`
          : `Not computed: ${cust.map(([b, x]) => `${b} = ${esc(x.value)}`).join('; ')} is between the precomputed table points. Nothing is interpolated; choose a table value.`;
      } else if (!c) {
        c = { status: 'NOT_COMPUTED', levels: lv };
        note = 'This combination is outside the computed grid.';
      } else if (c.status === 'DOES_NOT_CLOSE') {
        note = `The calculator does not close this ship: ${esc(c.reason || '')}.`;
      } else if (c.status === 'NOT_COMPUTED') {
        note = esc(c.inferred || 'Not computed.');
      }
      const ref = D.cases[D.reference_key];
      const v4 = D.cases[D.v4_key];
      const on = D.order.filter((b) => lv[b] !== 'L0');
      const onList = on.map((b) => { const L = levelOf(b, lv[b]); return `<li><a href="#${b}"><code>${b}</code> ${esc(BT[b].name)}</a>: ${esc(L.label)} ${badge('ev', L.evidence, D.vocab.evidence[L.evidence])} ${badge('lvl', BT[b].level, 'Level ' + BT[b].level)}</li>`; }).join('')
        || '<li>None: this is the scientific reference.</li>';
      const addressed = new Set(on.flatMap((b) => BT[b].weakest_links));
      const linkLi = (w) => `<li><a href="../weakest-links/#${w.id}"><code>${w.id}</code> ${esc(w.name)}</a> ${badge('tier', w.tier, 'Tier ' + w.tier)}</li>`;
      const yes = D.links.filter((w) => addressed.has(w.id)).map(linkLi).join('') || '<li>None.</li>';
      const no = D.links.filter((w) => !addressed.has(w.id)).map(linkLi).join('') || '<li>None.</li>';
      const open = [...new Set(on.flatMap((b) => BT[b].unbooked))].concat(
        D.breakthroughs.filter((b) => !b.computed).map((b) => `${b.id} ${b.name}: no calculator lever (not computed)`)
      ).map((t) => `<li>${esc(t)}</li>`).join('');
      const cp = c.coupled;
      const coupled = cp ? `<p><strong>Coupled check</strong> (${esc(cp.items)}${cp.rate_cap_Hz ? `, pulse rate held at the launcher cap ${num('pellet_rate_Hz', cp.rate_cap_Hz)} Hz` : ''}): ${badge('cfg', cp.status.split(' ')[0].replace('-', '_'), cp.status)}`
        + (cp.summary ? ` ${num('departure_t', cp.summary.departure_t)} t at ${num('pellet_rate_Hz', cp.summary.pellet_rate_Hz)} Hz, after ${cp.iterations} passes.` : '')
        + (cp.loop_gain !== undefined && !cp.summary ? ` Loop gain ${cp.loop_gain.toFixed(2)}.` : '') + '</p>' : '';
      const launch = c.launcher ? `<p><strong>Launcher</strong> ${num('x', c.launcher.speed_m_s / 1000)} km/s: ${c.launcher.binding ? `caps the pulse rate at ${num('pellet_rate_Hz', c.launcher.rate_cap_Hz)} Hz` : 'does not bind'}.</p>` : '';
      const dep = (D.cases[k] && D.cases[k].dependency_unmet) || [];
      const depNote = dep.length ? `<p class="warn">Dependency not met: ${dep.map(esc).join('; ')}. The calculator result is shown, but the scenario assumes a breakthrough without its prerequisite.</p>` : '';
      out.innerHTML = `<p class="scenario-status">${badge('st', c.status, D.vocab.status[c.status])} <strong>Experimental scenario</strong>, not canon. ${note}</p>` + depNote
        + `<div class="grid2">${panel('Scientific reference (Layer A)', ref)}${panel('Your scenario', c, v4)}</div>`
        + coupled + launch
        + `<div class="grid2"><div class="panel"><h3>Breakthroughs switched on</h3><ul class="plain">${onList}</ul></div>`
        + `<div class="panel"><h3>Weakest links</h3><p class="note">Addressed by a switched-on breakthrough (assumed, not demonstrated):</p><ul class="plain">${yes}</ul>`
        + `<p class="note">Not addressed by any switched-on breakthrough:</p><ul class="plain">${no}</ul></div></div>`
        + `<div class="panel"><h3>Still not computed in this scenario</h3><ul class="plain open-list">${open}</ul></div>`;
      if (!cust.length && valid(k)) history.replaceState(null, '', '#' + k);
      $$('.preset').forEach((p) => { if (p.dataset.case === k) p.setAttribute('aria-current', 'true'); else p.removeAttribute('aria-current'); });
      $$('table.grid tr').forEach((r) => r.classList.toggle('sel', !!r.querySelector(`a[data-case="${CSS.escape(k)}"]`)));
    };
    form.addEventListener('change', (e) => { if (e.target.type === 'radio') { delete custom[e.target.name]; const n = form.querySelector(`input[type=number][data-bt="${e.target.name}"]`); if (n) n.value = ''; } render(); });
    form.addEventListener('input', (e) => {
      const t = e.target;
      if (t.type !== 'number') return;
      const b = t.dataset.bt;
      const v = parseFloat(t.value);
      if (t.value === '' || !isFinite(v)) { delete custom[b]; render(); return; }
      const hit = BT[b].levels.find((x) => x.set[t.dataset.path] === v);
      if (hit) { form.querySelector(`input[name="${b}"][value="${hit.key}"]`).checked = true; delete custom[b]; }
      else custom[b] = { value: v, path: t.dataset.path, state: v > parseFloat(t.dataset.max) ? 'OUT_OF_RANGE' : 'NOT_COMPUTED' };
      render();
    });
    form.addEventListener('submit', (e) => e.preventDefault());
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-case]');
      if (!a || !valid(a.dataset.case)) return;
      e.preventDefault();
      setLevels(parseKey(a.dataset.case));
      render();
      $('#builder').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    const h = decodeURIComponent(location.hash.slice(1));
    setLevels(parseKey(valid(h) ? h : D.v4_key));
    render();
  }

  /* ---------------------------------------------------------------- Ship Evolution picker */
  const evo = $('form[data-evo]');
  const evoOut = $('[data-evo-out]');
  const shipEl = $('#ship-data');
  if (evo && evoOut && shipEl) {
    const ship = JSON.parse(shipEl.textContent);
    const sel = evo.elements.case;
    const closing = Object.keys(D.cases).filter((k) => D.cases[k].envelope);
    const name = (k) => { const lv = parseKey(k); const on = D.order.filter((b) => lv[b] !== 'L0').map((b) => `${b} ${lv[b]}`); return on.join(', ') || 'reference'; };
    sel.innerHTML = closing.map((k) => `<option value="${esc(k)}">${esc(name(k))} · ${num('departure_t', D.cases[k].summary.departure_t)} t</option>`).join('');
    evo.hidden = false;
    const svg = (c, scale) => {
      const e = Object.assign({}, c.envelope, { tip: c.summary.wing_tip_radius_m });
      const W = 880, H = scale === 'ship' ? 300 : 320;
      const x0 = scale === 'ship' ? -420 : -1500, x1 = scale === 'ship' ? 460 : 1500;
      const rmax = scale === 'ship' ? 180 : Math.max(12000, e.tip * 1.05);
      const sx = W / (x1 - x0), sy = scale === 'ship' ? sx : (H - 30) / rmax;
      const X = (x) => ((x - x0) * sx).toFixed(1), Y = (r) => (H - 20 - r * sy).toFixed(1);
      const h = ship.hull;
      const p = [`<line x1="0" y1="${Y(0)}" x2="${W}" y2="${Y(0)}" class="axis"/>`,
        `<rect class="hull" x="${X(h.x_aft)}" y="${Y(h.r)}" width="${((h.x_fwd - h.x_aft) * sx).toFixed(1)}" height="${(h.r * sy).toFixed(1)}"/>`,
        `<rect class="hull" x="${X(h.ring_x - 2)}" y="${Y(h.ring_r)}" width="${Math.max(1.5, 6 * sx).toFixed(1)}" height="${(h.ring_r * sy).toFixed(1)}"/>`,
        `<rect class="wing" x="${X(e.wing_x_m[0])}" y="${Y(Math.min(e.tip, rmax))}" width="${((e.wing_x_m[1] - e.wing_x_m[0]) * sx).toFixed(1)}" height="${((Math.min(e.tip, rmax) - 10) * sy).toFixed(1)}"/>`,
        `<rect class="shield" x="${X(e.x_shield_aft_m)}" y="${Y(e.shield_r_m)}" width="${Math.max(1.5, (e.x_shield_fwd_m - e.x_shield_aft_m) * sx).toFixed(1)}" height="${(e.shield_r_m * sy).toFixed(1)}"/>`,
        `<rect class="module" x="${X(e.x_shield_fwd_m)}" y="${Y(6.5)}" width="${((e.x_module_fwd_m - e.x_shield_fwd_m) * sx).toFixed(1)}" height="${(6.5 * sy).toFixed(1)}"/>`];
      if (e.x_bow_m > h.x_fwd) p.push(`<rect class="stretch" x="${X(h.x_fwd)}" y="${Y(h.r)}" width="${((e.x_bow_m - h.x_fwd) * sx).toFixed(1)}" height="${(h.r * sy).toFixed(1)}"/>`);
      e.loops.forEach((L) => { if (L.r_m <= rmax) p.push(`<circle class="loop" cx="${X(L.x_m)}" cy="${Y(L.r_m)}" r="3"/>`); });
      p.push(`<circle class="burn" cx="${X(e.x_burn_m)}" cy="${Y(0)}" r="4"/>`);
      const bar = scale === 'ship' ? 100 : 5000;
      p.push(`<g class="bar"><line x1="12" y1="${H - 6}" x2="${(12 + bar * sx).toFixed(1)}" y2="${H - 6}"/><text x="${(16 + bar * sx).toFixed(1)}" y="${H - 3}">${scale === 'ship' ? '100 m' : '5 km along the axis'}</text></g>`);
      return `<svg class="env" viewBox="0 0 ${W} ${H}" role="img" aria-label="Envelope ${scale}">${p.join('')}</svg>`;
    };
    const draw = () => {
      const k = sel.value;
      const c = D.cases[k];
      if (!c) { evoOut.innerHTML = ''; return; }
      const e = c.envelope;
      evoOut.innerHTML = `<figure class="figure"><figcaption>${badge('st', c.status, D.vocab.status[c.status])} ${esc(name(k))}: ${num('departure_t', c.summary.departure_t)} t, `
        + `layout length ${num('x', e.length_m)} m, shield r ${num('x', e.shield_r_m)} m, radiator tip ${num('wing_tip_radius_m', c.summary.wing_tip_radius_m)} km`
        + (c.coupled ? `; coupled check ${esc(c.coupled.status)}${c.coupled.summary ? ' ' + num('departure_t', c.coupled.summary.departure_t) + ' t' : ''}` : '')
        + `</figcaption>${svg(c, 'ship')}${svg(c, 'span')}</figure>`;
    };
    sel.addEventListener('change', draw);
    draw();
  }
})();
