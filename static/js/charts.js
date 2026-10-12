// Small, dependency-free SVG charts: thin bars with rounded data-ends, recessive grid, hover tooltips, table view.
import { esc } from './core.js';

let tip;
function tooltip() {
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'tooltip';
    tip.hidden = true;
    document.body.appendChild(tip);
    document.addEventListener('pointermove', e => {
      const m = e.target.closest?.('[data-tip]');
      if (!m) { tip.hidden = true; return; }
      tip.textContent = m.dataset.tip;
      tip.hidden = false;
      tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px';
      tip.style.top = (e.clientY - 38) + 'px';
    });
    document.addEventListener('focusin', e => {
      const m = e.target.closest?.('[data-tip]');
      if (!m) { tip.hidden = true; return; }
      const r = m.getBoundingClientRect();
      tip.textContent = m.dataset.tip;
      tip.hidden = false;
      tip.style.left = r.left + 'px';
      tip.style.top = (r.top - 36) + 'px';
    });
  }
}

// round tick step (1, 2, 5 × 10^n) so the axis reads 0, 50, 100… and the top sits just above the data
const niceStep = v => {
  const raw = Math.max(v, 1) / 4;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map(m => m * p).find(m => m >= raw);
};

// a bar with a 4 px rounded top and a square base on the baseline
function barPath(x, y, w, h, r = 4) {
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

/** Vertical bars. series = [{key, label, cls, values: [...]}]; labels along x. One or two series. */
export function columnChart({ labels, series, height = 220, unit = '', title = '', valueLabels = 'max' }) {
  tooltip();
  const W = 640, H = height, padL = 36, padB = 26, padT = 18, padR = 8;
  const step = niceStep(Math.max(...series.flatMap(s => s.values)));
  const ticks = Math.ceil(Math.max(...series.flatMap(s => s.values), 1) / step);
  const max = step * ticks;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const group = plotW / labels.length;
  const gap = 2;
  const barW = Math.max(3, Math.min(28, (group * 0.62 - gap * (series.length - 1)) / series.length));
  const y = v => padT + plotH - (v / max) * plotH;
  const out = [];
  for (let i = 0; i <= ticks; i++) {
    const v = step * i, yy = y(v);
    out.push(`<line class="grid-line" x1="${padL}" x2="${W - padR}" y1="${yy}" y2="${yy}"/>`);
    out.push(`<text class="axis-text" x="${padL - 6}" y="${yy + 4}" text-anchor="end">${Math.round(v)}</text>`);
  }
  const every = Math.ceil(labels.length / 10);
  labels.forEach((lab, i) => {
    const gx = padL + group * i + (group - (barW * series.length + gap * (series.length - 1))) / 2;
    series.forEach((s, j) => {
      const v = s.values[i];
      const x = gx + j * (barW + gap);
      const h = Math.max(0, padT + plotH - y(v));
      out.push(`<g class="mark"><rect class="hit" x="${x - 2}" y="${padT}" width="${barW + 4}" height="${plotH}"
        data-tip="${esc(lab)}: ${esc(s.label)} ${v}${unit}" tabindex="0"/>
        ${h > 0 ? `<path class="${s.cls}" d="${barPath(x, y(v), barW, h)}" pointer-events="none"/>` : ''}</g>`);
    });
    if (i % every === 0) out.push(`<text class="axis-text" x="${padL + group * i + group / 2}" y="${H - 8}" text-anchor="middle">${esc(lab)}</text>`);
  });
  if (valueLabels === 'max') {  // label only the peak of each series
    series.forEach((s, j) => {
      const i = s.values.indexOf(Math.max(...s.values));
      const gx = padL + group * i + (group - (barW * series.length + gap * (series.length - 1))) / 2 + j * (barW + gap);
      out.push(`<text class="val" x="${gx + barW / 2}" y="${y(s.values[i]) - 5}" text-anchor="middle">${s.values[i]}${unit}</text>`);
    });
  }
  const legend = series.length > 1
    ? `<div class="series-key">${series.map(s => `<span><i style="background:var(--${s.cls === 'bar-with' ? 'series-with' : 'series-without'})"></i>${esc(s.label)}</span>`).join('')}</div>`
    : '';
  const table = `<table class="data-table" hidden><thead><tr><th scope="col"></th>${series.map(s => `<th scope="col">${esc(s.label)}</th>`).join('')}</tr></thead>
    <tbody>${labels.map((l, i) => `<tr><th scope="row">${esc(l)}</th>${series.map(s => `<td>${s.values[i]}${unit}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  return `${legend}<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">${out.join('')}</svg>
    <button class="link-btn table-toggle" data-table-toggle>Show as table</button>${table}`;
}

/** Horizontal bars as HTML rows (label, bar, value) — easiest to read for category lists. */
export function hbars(rows, { unit = '' } = {}) {
  tooltip();
  const max = Math.max(1, ...rows.map(r => r.value));
  return rows.map(r => `<div class="hbar"><span>${esc(r.label)}</span>
    <span class="track" data-tip="${esc(r.label)}: ${r.value}${unit}" tabindex="0"><i style="width:${(100 * r.value / max).toFixed(1)}%"></i></span>
    <b>${r.value}${unit}</b></div>`).join('');
}

export function wireTables(root) {
  root.querySelectorAll('[data-table-toggle]').forEach(b => {
    b.onclick = () => {
      const tbl = b.nextElementSibling;
      tbl.hidden = !tbl.hidden;
      b.textContent = tbl.hidden ? 'Show as table' : 'Hide table';
    };
  });
}
