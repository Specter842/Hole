// Design tokens. Second generation -- the first (orange/teal, ported from
// estics-reach-dashboard.jsx) is being replaced with the lime/purple language
// from the new reference screenshots.
//
// `orange` and `teal` are kept as key names because ~44 call sites across 11
// files already read `C.orange` / `C.teal` -- repointing their VALUES recolors
// every one of those consistently without a 44-site rename. New code should
// reach for `C.lime` / `C.purple` / `C.chart[...]` directly; `orange` and
// `teal` are legacy aliases for the same two colors, not a second accent pair.
export const C = {
  bg: '#0B0C0E',
  panel: '#151619',
  panelAlt: '#1E2023',
  border: 'rgba(255,255,255,0.08)',
  text: '#FFFFFF',
  textSub: '#9CA0A6',
  textMute: '#6B6F76',

  // Primary accent -- active nav, primary buttons, positive status, the one
  // color the reference treats as "yes / go / this matters."
  lime: '#C6FF3D',
  limeDim: 'rgba(198,255,61,0.14)',
  onLime: '#10130A', // text/icons placed on a lime fill need a dark foreground

  // Secondary accent -- decorative, structural (chart segments, gradient
  // panels, an AI/assist affordance). Never a status color.
  purple: '#9B7BFF',
  purpleDim: 'rgba(155,123,255,0.14)',

  yellow: '#FFD23D',
  pink: '#FF6EC7',

  // Multi-series chart palette, in the order a legend should read.
  chart: ['#C6FF3D', '#9B7BFF', '#3DE0D6', '#FF6EC7', '#FFD23D'],

  red: '#FF5A5A',

  // Legacy aliases -- see file header. orange:lime, teal:the chart cyan.
  orange: '#C6FF3D',
  teal: '#3DE0D6',
  tealDark: '#1F3A38',
  barDark: '#121517',
  mapLand: '#4D4D4D',
  mapBorder: '#6B6B6B',
}
