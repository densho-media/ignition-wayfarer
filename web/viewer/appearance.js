// WEB-004 appearance state of Explore Ship: pure logic, no three.js. viewer.js renders what resolve() decides.
//
// Three independent parts of the state:
//   style      the global visual language: standard | subsystem | engine | hybrid
//   overrides  explicit per-target visibility states set by the visitor: 'n:<node>', 'g:<group>', 'a:<assembly>' or 's:<subsystem>' ->
//              SOLID | HOLOGRAM | GHOST | HIDDEN (a group is the manifest lineage below the assembly: a nozzle, a mechanism)
//   focus      the subject being examined ({ kind: 'node' | 'group' | 'assembly' | 'subsystem', id }) and how it and its context are drawn
//
// Precedence, first match wins (deterministic for every node):
//   1. HIDDEN by any override that covers the node (hidden always stays hidden: focus never reveals it)
//   2. the node's own override, then its group's, assembly's and subsystem's (the visitor's explicit choice beats focus and style)
//   3. focus: a node inside the subject takes focusLook (solid | subsystem | cyan); every other node takes contextLook (ghost | hologram)
//   4. the style default: standard and hybrid SOLID, subsystem HOLOGRAM in its subsystem colour (the unclassified casing CTX as GHOST,
//      as the M5 scene draws it), engine HOLOGRAM in the engine colour
// A HOLOGRAM state set by an override takes the style's tint: the engine colour in the engine style, the subsystem colour otherwise.

export const STYLES = ['standard', 'subsystem', 'engine', 'hybrid'];
export const STATES = ['SOLID', 'HOLOGRAM', 'GHOST', 'HIDDEN'];
export const LOOKS = ['solid', 'subsystem', 'cyan'];
export const CONTEXTS = ['ghost', 'hologram'];
export const GHOST_DEFAULT = 0.06;          // starting point for review, not a canonical value (owner brief: 3-8 % visual prominence)
export const GHOST_MAX = 0.2;

export function initialState() {
  return { style: 'standard', focus: null, focusLook: null, contextLook: 'ghost', overrides: new Map(), ghost: GHOST_DEFAULT, outlines: true };
}

// The focus subject's look when the visitor has not chosen one: solid in standard and hybrid, the style's hologram otherwise.
export function effectiveLook(s) {
  return s.focusLook || { subsystem: 'subsystem', engine: 'cyan' }[s.style] || 'solid';
}

// info: { id, group, assembly, sid } of one node (id: its WF_ node name). inFocus: whether it belongs to the focus subject.
// Returns { state, tint } with tint 'subsystem' | 'engine' | null (SOLID, HIDDEN) | 'ghost'.
export function resolve(s, info, inFocus) {
  const own = s.overrides.get('n:' + info.id);
  const grp = info.group ? s.overrides.get('g:' + info.group) : undefined;
  const asm = s.overrides.get('a:' + info.assembly);
  const sub = s.overrides.get('s:' + info.sid);
  if ([own, grp, asm, sub].includes('HIDDEN')) return { state: 'HIDDEN', tint: null, why: 'hidden' };
  const explicit = own || grp || asm || sub;
  if (explicit) {
    const why = own ? 'part override' : grp ? 'group override' : asm ? 'assembly override' : 'subsystem override';
    return { state: explicit, tint: tintOf(s, explicit), why };
  }
  if (s.focus) {
    if (inFocus) {
      const look = effectiveLook(s);
      return look === 'solid' ? { state: 'SOLID', tint: null, why: 'focus' }
        : { state: 'HOLOGRAM', tint: look === 'cyan' ? 'engine' : 'subsystem', why: 'focus' };
    }
    return s.contextLook === 'hologram' ? { state: 'HOLOGRAM', tint: tintOf(s, 'HOLOGRAM'), why: 'context' }
      : { state: 'GHOST', tint: 'ghost', why: 'context' };
  }
  if (s.style === 'subsystem') return info.sid === 'CTX' ? { state: 'GHOST', tint: 'ghost', why: 'style' } : { state: 'HOLOGRAM', tint: 'subsystem', why: 'style' };
  if (s.style === 'engine') return { state: 'HOLOGRAM', tint: 'engine', why: 'style' };
  return { state: 'SOLID', tint: null, why: 'style' };
}

function tintOf(s, state) {
  if (state === 'HOLOGRAM') return s.style === 'engine' ? 'engine' : 'subsystem';
  if (state === 'GHOST') return 'ghost';
  return null;
}

export function inFocus(s, info) {
  const f = s.focus;
  if (!f) return false;
  if (f.kind === 'node') return info.id === f.id;
  if (f.kind === 'group') return info.group === f.id;
  if (f.kind === 'assembly') return info.assembly === f.id;
  return info.sid === f.id;
}

// Bookmark: compact, defaults omitted. The camera part (view= or cam=) stays first, as WEB-002/003 links have it.
//   style=<name>  focus=<n|g|a|s>:<id>  look=<solid|subsystem|cyan>  ctx=hologram  ghost=<percent>  outl=0  ov=<target>.<s|h|g|x>,...
const LETTER = { SOLID: 's', HOLOGRAM: 'h', GHOST: 'g', HIDDEN: 'x' };
const FROM_LETTER = Object.fromEntries(Object.entries(LETTER).map(([k, v]) => [v, k]));
const KIND = { node: 'n', group: 'g', assembly: 'a', subsystem: 's' };
const FROM_KIND = { n: 'node', g: 'group', a: 'assembly', s: 'subsystem' };

const enc = x => encodeURIComponent(x).replace(/%3A/g, ':');

export function encode(s) {
  const parts = [];
  if (s.style !== 'standard') parts.push(`style=${s.style}`);
  if (s.focus) parts.push(`focus=${KIND[s.focus.kind]}:${enc(s.focus.id)}`);
  if (s.focusLook) parts.push(`look=${s.focusLook}`);
  if (s.contextLook !== 'ghost') parts.push(`ctx=${s.contextLook}`);
  if (Math.abs(s.ghost - GHOST_DEFAULT) > 1e-6) parts.push(`ghost=${Math.round(s.ghost * 100)}`);
  if (!s.outlines) parts.push('outl=0');
  if (s.overrides.size) parts.push('ov=' + [...s.overrides].map(([k, v]) => `${enc(k)}.${LETTER[v]}`).join(','));
  return parts.join('&');
}

// Reads a hash into a state; exists(kind, id) drops focus and overrides whose target is not in this build (a later model).
export function decode(hash, exists = () => true) {
  const s = initialState();
  const p = new URLSearchParams(hash.replace(/^#/, ''));
  if (STYLES.includes(p.get('style'))) s.style = p.get('style');
  const focus = /^([ngas]):(.+)$/.exec(p.get('focus') || '');
  if (focus && exists(FROM_KIND[focus[1]], focus[2])) s.focus = { kind: FROM_KIND[focus[1]], id: focus[2] };
  if (LOOKS.includes(p.get('look'))) s.focusLook = p.get('look');
  if (CONTEXTS.includes(p.get('ctx'))) s.contextLook = p.get('ctx');
  const g = Number(p.get('ghost'));
  if (p.has('ghost') && Number.isFinite(g)) s.ghost = Math.min(GHOST_MAX, Math.max(0, g / 100));
  if (p.get('outl') === '0') s.outlines = false;
  for (const item of (p.get('ov') || '').split(',').filter(Boolean)) {
    const m = /^(.*)\.([shgx])$/.exec(item);
    if (!m) continue;
    const key = m[1];                         // URLSearchParams has decoded it
    const kind = FROM_KIND[key[0]];
    if (key[1] !== ':' || !STATES.includes(FROM_LETTER[m[2]])) continue;
    if (kind && exists(kind, key.slice(2))) s.overrides.set(key, FROM_LETTER[m[2]]);
  }
  return s;
}
