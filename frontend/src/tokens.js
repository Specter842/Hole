// Design tokens. Third generation -- lime/purple is being replaced with the
// warm orange/maroon language from the Evoque flight-booking reference.
//
// Key names are unchanged from generation two (93 call sites across the app
// read `C.lime` / `C.purple` / `C.chart[...]` etc.) -- repointing their
// VALUES recolors every one of those consistently without a 93-site rename.
// `lime` is genuinely orange now, `purple` is a warm gold/amber secondary,
// not their generation-two colors; treat the names as roles (primary
// accent, secondary accent), not literal colors.
export const C = {
  bg: '#1B1210',
  panel: '#271A17',
  panelAlt: '#32211D',
  border: 'rgba(255,225,205,0.10)',
  text: '#FFFFFF',
  textSub: '#C2AEA3',
  textMute: '#8C7A70',

  // Primary accent -- active nav, primary buttons, positive status. Orange
  // bg needs a white foreground here, not a dark one (the old lime was
  // light enough to need dark text; this orange is not).
  lime: '#E8834A',
  limeDim: 'rgba(232,131,74,0.16)',
  onLime: '#FFFFFF',

  // Secondary accent -- warm gold, decorative/structural only, never a
  // status color. The reference itself is almost monochrome (one orange
  // against dark maroon); this exists for chart variety without breaking
  // that restraint by reaching for an unrelated hue.
  purple: '#C9954D',
  purpleDim: 'rgba(201,149,77,0.16)',

  yellow: '#D9A441',
  pink: '#B87355',

  // Multi-series chart palette -- analogous warm hues, not a rainbow, to
  // stay inside the reference's one-accent-family restraint.
  chart: ['#E8834A', '#C9954D', '#8B4A3D', '#D9A441', '#B87355'],

  red: '#E15A4A',

  // Legacy aliases from generation two -- see file header.
  orange: '#E8834A',
  teal: '#C9954D',
  tealDark: '#3D2A22',
  barDark: '#1F1512',
  mapLand: '#4A3630',
  mapBorder: '#6B5148',
}
