// Store floor plan as SVG (1 unit = 1 metre). Draws aisles, shelves, signs, checkouts, a route and stops.
import { esc, state, t } from './core.js';

const c = v => v + 0.5; // centre of a grid cell

export function mapSVG({ route = null, highlight = [], heat = null, you = null, label = '', animate = true } = {}) {
  const plan = state.plan;
  if (!plan) return '';
  const W = plan.width, H = plan.height;
  const heatMax = heat ? Math.max(1, ...Object.values(heat)) : 1;
  const heatFill = n => `var(--heat-${Math.min(4, Math.round((n / heatMax) * 4))})`;
  const parts = [];
  parts.push(`<rect class="floor" x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="0.6"/>`);
  for (const a of plan.aisles) {
    const fill = heat ? heatFill(heat[a.aisle] || 0) : a.color;
    parts.push(`<rect class="walk ${heat ? 'heat' : ''}" data-aisle="${a.aisle}" x="${a.x}" y="${a.y}" width="${a.w}" height="${a.h}"
      style="fill:${fill}" tabindex="0" role="button" aria-label="${esc(t('aisle'))} ${a.aisle}: ${esc(a.name)}${heat ? `, ${heat[a.aisle] || 0}` : ''}"><title>${esc(t('aisle'))} ${a.aisle} — ${esc(a.name)}${heat ? ` (${heat[a.aisle] || 0})` : ''}</title></rect>`);
  }
  for (const s of plan.shelves) parts.push(`<rect class="shelf" x="${s.x + 0.12}" y="${s.y}" width="${s.w - 0.24}" height="${s.h}" rx="0.15"/>`);
  for (const a of plan.aisles) {
    parts.push(`<g class="sign" aria-hidden="true"><rect x="${a.x + 0.25}" y="1.25" width="1.5" height="1.3" rx="0.25"/>
      <text x="${a.x + 1}" y="1.92">${a.aisle}</text></g>`);
  }
  for (const k of plan.checkouts) parts.push(`<rect class="checkout" x="${k.x + 0.08}" y="${k.y + 0.15}" width="0.84" height="0.7" rx="0.12"/>`);
  parts.push(`<text class="label" x="${plan.checkouts[0].x}" y="${H - 0.65}">${esc(t('checkout'))}</text>`);
  parts.push(`<rect x="${plan.entrance.x + 0.1}" y="${H - 1.05}" width="0.8" height="0.6" rx="0.1" fill="var(--route)"/>`);
  parts.push(`<text class="label" x="${plan.entrance.x + 1.2}" y="${H - 0.6}">${esc(t('entrance'))}</text>`);

  if (route && route.path?.length > 1) {
    const pts = route.path.map(p => `${c(p.x)},${c(p.y)}`).join(' ');
    const len = route.path.length + 2;
    parts.push(`<polyline class="route ${animate ? 'draw' : ''}" style="--len:${len}" points="${pts}"/>`);
    route.order.forEach((key, i) => {
      const p = state.products[key];
      if (!p) return;
      parts.push(`<g class="stop"><title>${i + 1}. ${esc(p.name)}</title><circle cx="${c(p.pick.x)}" cy="${c(p.pick.y)}" r="0.55"/>
        <text x="${c(p.pick.x)}" y="${c(p.pick.y) + 0.02}">${i + 1}</text></g>`);
    });
    const s = route.path[0];
    parts.push(`<g class="you"><title>${esc(t('you_are_here'))}</title><circle cx="${c(s.x)}" cy="${c(s.y)}" r="0.45"/></g>`);
  } else if (you) {
    parts.push(`<g class="you"><circle cx="${c(you.x)}" cy="${c(you.y)}" r="0.45"/></g>`);
  }
  for (const key of highlight) {
    const p = state.products[key];
    if (!p) continue;
    parts.push(`<circle class="pin" cx="${c(p.pick.x)}" cy="${c(p.pick.y)}" r="0.42"><title>${esc(p.name)}</title></circle>`);
  }
  return `<svg class="store-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label || t('map'))}">${parts.join('')}</svg>`;
}

export function stepText(step, isLast, product) {
  const turn = { left: t('turn_left'), right: t('turn_right'), straight: t('go_straight'), back: t('turn_back') }[step.turn] || t('go_straight');
  const where = step.area.startsWith('Aisle') ? `${t('aisle')} ${step.area.split(' ')[1]}` :
    step.area.includes('front') ? (state.lang === 'hi' ? 'आगे की ओर' : state.lang === 'te' ? 'ముందు వైపు' : 'along the front') :
    (state.lang === 'hi' ? 'पीछे की ओर' : state.lang === 'te' ? 'వెనుక వైపు' : 'along the back');
  const metres = `${step.metres} m`;
  if (isLast && product) {
    return `${turn}, ${metres} — ${where}. ${t('arrived')}: ${product.level_name.toLowerCase()}, ${t(product.side === 'L' ? 'left' : 'right')}.`;
  }
  return `${turn}, ${metres} — ${where}`;
}

export function flattenSteps(route) {
  const out = [];
  route.legs.forEach(leg => {
    const product = state.products[leg.to];
    leg.steps.forEach((s, i) => out.push({ ...s, text: stepText(s, i === leg.steps.length - 1, product), leg: leg.to,
                                           last: i === leg.steps.length - 1 }));
  });
  return out.filter(s => s.metres > 0);
}
