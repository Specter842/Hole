"""Verbatim Evoque design-system assets.

Generated from the reference build's index.html by tools/_genassets.py --
the stylesheet and the dotted-globe canvas script are carried over
unchanged so the look is identical to the approved design. Do not
hand-edit: this CSS is the single source of truth for every page's
appearance.
"""

CSS = r'''
  :root{
    --bg:#e2e2e4;
    --panel:#1a0f0d;
    --panel-2:#211311;
    --panel-3:#2a1815;
    --card:#0e0806;
    --line:rgba(255,255,255,.07);
    --line-2:rgba(255,255,255,.12);
    --text:#f6efe9;
    --muted:#9c8f88;
    --muted-2:#6f635d;
    --accent:#e8763a;
    --accent-2:#f0894a;
    --accent-soft:rgba(232,118,58,.16);
    --danger:#e5484d;
    --globe-dot:#9a5c42;
    --globe-hi:#f0894a;
    --radius:20px;
    --shadow:0 30px 80px -20px rgba(0,0,0,.55);
  }
  html[data-theme="light"]{
    --bg:#e2e2e4; --panel:#faf7f5; --panel-2:#fff;
    --panel-3:#f1eae6; --card:#fff; --line:rgba(0,0,0,.08); --line-2:rgba(0,0,0,.14);
    --text:#1b1310; --muted:#7a6d66; --muted-2:#9c8f88;
    --globe-dot:#d8b8a8;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{
    font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    background:var(--bg);
    color:var(--text);
    min-height:100vh;
    display:flex;align-items:center;justify-content:center;
    padding:28px;
    -webkit-font-smoothing:antialiased;
  }
  h1,h2,h3,.font-display{font-family:'Sora','Inter',sans-serif}

  .app{
    width:min(1600px,100%);
    background:var(--panel);
    border-radius:26px;
    box-shadow:var(--shadow);
    display:grid;
    grid-template-columns:400px 1fr;
    overflow:hidden;
    border:1px solid var(--line);
    min-height:840px;
  }

  /* ---------------- SIDEBAR ---------------- */
  .sidebar{
    padding:22px;
    display:flex;flex-direction:column;gap:18px;
    background:linear-gradient(180deg,var(--panel) 0%, #150c0a 100%);
    border-right:1px solid var(--line);
  }
  .brand{
    display:flex;align-items:center;gap:12px;
    padding:16px 18px;
    background:var(--panel-2);
    border:1px solid var(--line);
    border-radius:var(--radius);
  }
  .brand .mark{
    width:34px;height:34px;border-radius:11px;
    background:conic-gradient(from 220deg,var(--accent),#b8481f,#f0a072,var(--accent));
    -webkit-mask:radial-gradient(circle at 50% 50%, transparent 26%, #000 27%);
    mask:radial-gradient(circle at 50% 50%, transparent 26%, #000 27%);
    animation:spin 14s linear infinite;
  }
  @keyframes spin{to{transform:rotate(360deg)}}
  .brand b{font-family:'Sora';font-size:22px;letter-spacing:-.01em}

  .search-card{
    background:var(--panel-2);
    border:1px solid var(--line);
    border-radius:var(--radius);
    padding:14px;
    display:flex;flex-direction:column;gap:10px;
  }
  .field-row{display:flex;gap:10px;position:relative}
  .field{
    flex:1;
    background:var(--panel-3);
    border:1px solid var(--line);
    border-radius:14px;
    padding:10px 14px;
    cursor:text;
  }
  .field label{display:block;font-size:11px;color:var(--muted-2);margin-bottom:3px}
  .field input{
    width:100%;border:0;background:transparent;color:var(--text);
    font-size:14px;font-weight:600;font-family:inherit;outline:none;
  }
  .swap{
    position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
    width:30px;height:30px;border-radius:50%;
    background:var(--accent);color:#fff;border:3px solid var(--panel-2);
    display:grid;place-items:center;cursor:pointer;z-index:2;
    transition:transform .3s;
  }
  .swap:hover{transform:translate(-50%,-50%) rotate(180deg)}
  .field-grid{display:grid;grid-template-columns:1.4fr 1fr;gap:10px}
  .field.with-icon{display:flex;align-items:center;justify-content:space-between;gap:8px}
  .field.with-icon .txt{flex:1}
  .icon{color:var(--muted);flex-shrink:0}
  .btn-search{
    border:0;border-radius:14px;padding:14px;
    background:linear-gradient(180deg,var(--accent-2),var(--accent));
    color:#fff;font-weight:700;font-size:15px;font-family:'Sora';
    cursor:pointer;letter-spacing:.01em;
    box-shadow:0 12px 26px -8px var(--accent);
    transition:filter .2s,transform .1s;
  }
  .btn-search:hover{filter:brightness(1.07)}
  .btn-search:active{transform:translateY(1px)}

  .flights{
    background:var(--panel-2);
    border:1px solid var(--line);
    border-radius:var(--radius);
    padding:16px;
    display:flex;flex-direction:column;gap:6px;
    flex:1;min-height:0;
  }
  .flights-head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:6px}
  .flights-head h2{font-size:22px;letter-spacing:-.01em}
  .flights-head .sub{font-size:12px;color:var(--muted);margin-top:2px}
  .sort-btn{background:transparent;border:0;color:var(--muted);cursor:pointer;padding:4px;border-radius:8px}
  .sort-btn:hover{color:var(--text)}

  .flight-list{display:flex;flex-direction:column;gap:8px;overflow-y:auto;padding-right:4px;margin-right:-4px}
  .flight-list::-webkit-scrollbar{width:5px}
  .flight-list::-webkit-scrollbar-thumb{background:var(--line-2);border-radius:9px}

  .flight{
    background:var(--panel-3);
    border:1px solid var(--line);
    border-radius:14px;
    overflow:hidden;
    transition:border-color .2s;
  }
  .flight.open{border-color:var(--accent-soft)}
  .flight-row{
    display:flex;align-items:center;gap:12px;
    padding:13px 14px;cursor:pointer;
  }
  .flight-row .chev{color:var(--muted-2);transition:transform .25s}
  .flight.open .chev{transform:rotate(180deg)}
  .airline{font-family:'Sora';font-weight:800;font-style:italic;font-size:13px;letter-spacing:.03em;min-width:42px}
  .times{font-size:14px;font-weight:600;letter-spacing:.02em}
  .dots{flex:1;border-top:1.5px dotted var(--line-2);margin:0 2px;position:relative;top:1px}
  .price{font-family:'Sora';font-weight:700;font-size:15px}
  .go{
    width:30px;height:30px;border-radius:9px;flex-shrink:0;
    background:var(--panel);border:1px solid var(--line);
    display:grid;place-items:center;color:var(--text);
  }
  .flight.open .go{background:#fff;color:#111}

  .flight-detail{display:none;padding:0 14px 14px}
  .flight.open .flight-detail{display:block;animation:fade .3s ease}
  @keyframes fade{from{opacity:0;transform:translateY(-4px)}to{opacity:1}}
  .leg{display:grid;grid-template-columns:54px 18px 1fr;gap:10px;font-size:13px}
  .leg .t{color:var(--muted);font-weight:600}
  .leg .t small{display:block;color:var(--muted-2);font-weight:400;font-size:11px}
  .rail{display:flex;flex-direction:column;align-items:center;padding-top:4px}
  .rail .pt{width:9px;height:9px;border-radius:50%;border:2px solid var(--accent)}
  .rail .pt.fill{background:var(--accent)}
  .rail .ln{flex:1;width:2px;background:var(--line-2);margin:3px 0}
  .leg .place{font-weight:600}
  .leg .place small{display:block;color:var(--muted-2);font-weight:400;font-size:11px;margin-top:1px}
  .mid-leg{grid-column:1/-1;display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;padding:8px 0 8px 64px}
  .bag{display:inline-flex;align-items:center;gap:6px;background:var(--accent-soft);color:var(--accent-2);padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600}

  /* ---------------- MAIN ---------------- */
  .main{position:relative;overflow:hidden;background:radial-gradient(120% 90% at 60% 20%, #2a1512 0%, #0c0605 60%, #080403 100%)}
  #globe{position:absolute;inset:0;width:100%;height:100%}
  .main-head{position:absolute;top:26px;left:34px;right:34px;display:flex;justify-content:space-between;align-items:flex-start;z-index:5}
  .main-head h1{font-size:40px;letter-spacing:-.02em;line-height:1;white-space:nowrap}
  .main-head .sub{color:var(--muted);margin-top:8px;font-size:14px}
  .head-tools{display:flex;align-items:center;gap:12px}
  .toggle{
    width:56px;height:30px;border-radius:20px;background:var(--panel-3);
    border:1px solid var(--line);position:relative;cursor:pointer;
  }
  .toggle::after{
    content:"";position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;
    background:linear-gradient(180deg,#fff,#d8d8d8);transition:left .25s;
  }
  html[data-theme="light"] .toggle::after{left:29px}
  .pill{width:44px;height:44px;border-radius:13px;background:#fff;display:grid;place-items:center;position:relative}
  .pill .bell{color:#1b1310}
  .pill .dot{position:absolute;top:9px;right:9px;width:8px;height:8px;border-radius:50%;background:var(--accent);border:2px solid #fff}
  .avatar{width:44px;height:44px;border-radius:13px;object-fit:cover;background:var(--accent-soft)}

  .arc-card{
    position:absolute;z-index:6;left:50%;top:52%;transform:translate(-50%,0);
    background:#fff;color:#14100e;border-radius:16px;padding:14px 16px;width:270px;
    box-shadow:0 24px 50px -12px rgba(0,0,0,.5);
  }
  html[data-theme="dark"] .arc-card{background:#fbf7f4}
  .arc-card::after{content:"";position:absolute;top:-8px;left:50%;transform:translateX(-50%);border:8px solid transparent;border-bottom-color:#fbf7f4;border-top:0}
  .arc-top{display:flex;justify-content:space-between;align-items:center;font-weight:700;font-family:'Sora'}
  .arc-top .route{display:flex;align-items:center;gap:7px;font-size:15px}
  .arc-hr{border:0;border-top:1px solid rgba(0,0,0,.1);margin:11px 0}
  .arc-bot{display:flex;justify-content:space-between;align-items:center}
  .seats{display:flex;align-items:center;gap:6px;color:var(--danger);font-size:12px;font-weight:600}
  .book{background:#1b1310;color:#fff;border:0;border-radius:9px;padding:8px 14px;font-size:12px;font-weight:600;cursor:pointer;font-family:'Sora'}
  .book:hover{background:#000}
  .plane-badge{
    position:absolute;left:50%;top:calc(52% - 46px);transform:translate(-50%,-50%);
    width:46px;height:46px;border-radius:14px;background:var(--accent);
    display:grid;place-items:center;color:#fff;z-index:6;
    box-shadow:0 12px 30px -6px var(--accent);
  }
  .plane-badge svg{animation:bob 3s ease-in-out infinite}
  @keyframes bob{50%{transform:translateY(-4px)}}

  .aircraft{
    position:absolute;top:92px;right:34px;width:328px;z-index:5;
    background:linear-gradient(180deg,var(--panel-3),var(--panel-2));
    border:1px solid var(--line-2);border-radius:var(--radius);padding:14px;
    box-shadow:var(--shadow);
  }
  .aircraft.detached{top:96px}
  .ac-photo{position:relative;border-radius:14px;height:154px;display:grid;place-items:center;overflow:hidden;
    background:radial-gradient(120% 140% at 25% 15%, #fdfdfe 0%, #e7ecf3 45%, #c7d2df 100%)}
  .ac-photo::before{content:"";position:absolute;left:-10%;right:-10%;bottom:26%;height:1px;background:rgba(120,140,165,.35)}
  .ac-photo svg{width:94%;position:relative}
  .ac-tag{position:absolute;top:10px;right:10px;background:var(--accent);color:#fff;font-size:11px;font-weight:700;font-family:'Sora';padding:4px 10px;border-radius:8px}
  .ac-airline{display:flex;align-items:center;gap:9px;padding:12px 4px 10px}
  .ac-airline .lot{font-family:'Sora';font-weight:800;font-style:italic;color:#11315e;background:#fff;padding:2px 6px;border-radius:5px;font-size:12px}
  html[data-theme="dark"] .ac-airline .lot{color:#1a4b8f}
  .ac-airline span{font-size:13px;color:var(--muted);font-weight:500}
  .ac-spec{display:flex;justify-content:space-between;padding:11px 6px;font-size:13px;border-top:1px solid var(--line)}
  .ac-spec .k{color:var(--muted)}
  .ac-spec .v{font-weight:600}

  .zoom{position:absolute;right:34px;bottom:26px;display:flex;align-items:center;gap:16px;z-index:5;color:var(--muted)}
  .zoom button{background:transparent;border:0;color:inherit;cursor:pointer;padding:6px}
  .zoom button:hover{color:var(--text)}
  .help{width:46px;height:46px;border-radius:13px;background:#fff;color:#1b1310;display:grid;place-items:center;font-weight:700;cursor:pointer;font-family:'Sora'}

  .credit{position:absolute;left:34px;bottom:24px;z-index:5;color:var(--muted-2);font-size:11px;letter-spacing:.03em}

  @media(max-width:1040px){
    .app{grid-template-columns:1fr}
    .main{min-height:620px}
    .aircraft{position:static;width:auto;margin:14px}
    .main-head{position:static;padding:26px 26px 0}
  }
  @media(max-width:560px){
    body{padding:0}
    .app{border-radius:0;min-height:100vh}
    .main-head h1{font-size:30px}
    .arc-card{width:230px}
  }
'''

GLOBE_JS = r'''function initGlobe(){
/* ---------------- Dotted globe ---------------- */
const cv = document.getElementById('globe');
const ctx = cv.getContext('2d');
const badge = document.querySelector('.plane-badge');
const arcCard = document.querySelector('.arc-card');
let W,H,DPR;
function resize(){
  DPR = Math.min(window.devicePixelRatio||1, 2);
  W = cv.clientWidth; H = cv.clientHeight;
  cv.width = W*DPR; cv.height = H*DPR;
  ctx.setTransform(DPR,0,0,DPR,0,0);
}
window.addEventListener('resize', resize); resize();

/* real world land bitmap: 200x100 equirectangular, 1bpp MSB-first, row 0 = +90 lat */
const LM_W=200, LM_H=100;
const LM_B64="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH//P9/9AAAAAAAAAAAAAAAAAAAAAAAAAAPv+////8AAA+ACAAAB4AAAAAAAAAAAAAAWf9////+AAByAAAAAAAwAAAAAAAAAAADhCf8H////AAAAAAAAwAAPwAAAAAAAAAAABgF+AA///4AAAAAAGAAP/8AAQAAAAAAAAfTNtsAH//4AAAAAAGAQf///4AAAAIAEAAEfw5/wAf//AAAAEAAgd/////f/AAEAf/5/3+fOPgD//AAAA/4AAzf////////ewH////7/7k8D/8AAAA//6f///////////3n///////Acgf4B8AAfPj////////////8AH//////ODwH4AOAAfn9////////////+AP//////AXAA8AAAAfz//////////////AH+3////gB4ABAAAAH8z///////////w6AABgH///8AfYAAAABBuH//////////4AwAABgAP///4H/AAAAAYFj//////////4AeAABAAB////z/8AAAAOBB//////////4APAAAAAAv///8//gAAAHx////////////8BgAAAAAB//////4AAAAO////////////9AAAAAAAAP////+CAAAAA/////////////QAAAAAAAB/////x4AAAA/////////////gAAAAAAAAf////+gAAAAH//4fj///////4AAAAAAAAH////9AAAAAB/n8Dz///////4YAAAAAAAB////+AAAAAH8M+Aef//////4MAAAAAAAAf///+AAAAAB8A2P/3/////+8CAAAAAAAAH///+AAAAAAfAAn/4/////+CAgAAAAAAAA////wAAAAADhwJ//P/////8wwAAAAAAAAH///8AAAAAAf8Ai///////8N8AAAAAAAAAf//8AAAAAAf/AAP///////goAAAAAAAAAF//+AAAAAAH/+eH///////8IAAAAAAAAAA//wgAAAAAB/////v//////AAAAAAAAAAAL/AIAAAAAB////P5//////gAAAAAAAAAAAfwBAAAAAA////7/j/////4AAAAAAAAAAAL8AAAAAAAf////f7B////9AAAAAAAAAAAAfAcAAAAAH////z/4H/3/8AAAAAAAAAAAAHwwQAAAAB////+/+A/x/gAAAAAAAAAAAAA+YAwAAAAf////n/AP4P6AAAAAAAAAAAAAD+AAAAAAH////8/gB8D+AQAAAAAAAAAAAAD8AAAAAB/////PgAcAPwEAAAAAAAAAAAAAPAAAAAAf////7AADgB+AgAAAAAAAAAAAAAwAAAAAH/////AAAwAHgEAAAAAAAAAAAAAMN8AAAA//////AAMAAgCAAAAAAAAAAAAAAP/gAAAH/////wAAgBAAwAAAAAAAAAAAAAB/8AAAA/////4AAAAIAEAAAAAAAAAAAAAAf/4AAAEBf//+AAAAaBwAAAAAAAAAAAAAAH//AAAAAH///AAAADw4AAAAAAAAAAAAAAD//wAAAAB///AAAAAYfQAAAAAAAAAAAAAB///AAAAAf//gAAAADHoEAAAAAAAAAAAAAP//+AAAAH//wAAAAA57AsAAAAAAAAAAAAH///4AAAA//8AAAAAGAgH4gAAAAAAAAAAB////gAAAH//AAAAAAQAAfAAAAAAAAAAAAP///4AAAB//wAAAAAB0AHQIAAAAAAAAAAD///8AAAAf/8AAAAAAAgACAAAAAAAAAAAAf//+AAAAD//AAAAAAAAAAAAAAAAAAAAAAD///AAAAB//4QAAAAAADxAAAAAAAAAAAAA///wAAAAf/+MAAAAAAH8YAAAAAAAAAAAAD//8AAAAH/+HAAAAAAD/uAAAAAAAAAAAAAf//AAAAB//BgAAAAAA//gAAAAAAAAAAAAH//gAAAAf/g4AAAAAB//+AQAAAAAAAAAAB//4AAAAD/8OAAAAAB///wAAAAAAAAAAAAf/wAAAAA//DAAAAAAf//8AAAAAAAAAAAAH/4AAAAAP/AAAAAAAH///gAAAAAAAAAAAB/+AAAAAB/wAAAAAAB///4AAAAAAAAAAAA//AAAAAAf4AAAAAAAP//+AAAAAAAAAAAAP/wAAAAAD8AAAAAAAD///gAAAAAAAAAAAD/4AAAAAA+AAAAAAAA+BfwAAAAAAAAAAAA/wAAAAAAAAAAAAAAAAAH8ACAAAAAAAAAAf8AAAAAAAAAAAAAAAAAA+AAQAAAAAAAAAH+AAAAAAAAAAAAAAAAAABAAGAAAAAAAAAB+AAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAfgAAAAAAAAAAAAAAAAAAEABgAAAAAAAAAHwAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAD4AAAAAAAAAAAAAAAAAAAAAYAAAAAAAAAA+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAADwQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAAAAAAAfkAf/////gAAAAAAAAAAAALgAAAAAAAA7//4f//////4AAAAAAAAAAAD8AAAACH/////8/////////AAAAAAAA4IAPAAAAP////////////////4AAAAP/+D///gAAAH////////////////wAAAB//////+AAAB/////////////////4AAEf//////4AAYP//////////////////AAAAH//////AIfAP////////////////+AAAAf///////4Dv//////////////////wAAAH/////////////////////////////wP//v////////////////////////////////////////////////////////////////////////////////////////////////w==";
const LM_BYTES=(()=>{const bin=atob(LM_B64);const a=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);return a;})();
function isLand(latDeg,lonDeg){
  let x=Math.floor((lonDeg+180)/360*LM_W);
  let y=Math.floor((90-latDeg)/180*LM_H);
  if(x<0)x=0; if(x>=LM_W)x=LM_W-1;
  if(y<0)y=0; if(y>=LM_H)y=LM_H-1;
  const bit=y*LM_W+x;
  return (LM_BYTES[bit>>3] >> (7-(bit&7))) & 1;
}

/* precompute land points on the sphere */
const D2R=Math.PI/180;
const PTS=[];
for(let lat=-88; lat<=88; lat+=2){
  const step = lat>78||lat<-78 ? 6 : 2;
  for(let lon=-180; lon<180; lon+=step){
    if(!isLand(lat,lon)) continue;
    const la=lat*D2R, lo=lon*D2R;
    PTS.push({
      x:Math.cos(la)*Math.cos(lo),
      y:Math.sin(la),
      z:Math.cos(la)*Math.sin(lo),
      hi: (lat>10 && lat<33 && lon>32 && lon<52)   // Arabian peninsula glow
    });
  }
}

/* cities for the ALC -> RUH arc */
function cityVec(lat,lon){const la=lat*D2R,lo=lon*D2R;return {x:Math.cos(la)*Math.cos(lo),y:Math.sin(la),z:Math.cos(la)*Math.sin(lo)};}
const _arc=(cv.dataset.arc||'39.8,-98.6,54,-2.5').split(',').map(Number);
const CITY_A=cityVec(_arc[0],_arc[1]);
const CITY_B=cityVec(_arc[2],_arc[3]);

const VIEW_LON=-18*D2R;   // longitude facing the camera
const VIEW_TILT=22*D2R;   // camera latitude tilt
let spin=0;
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function rotate(p){
  const a=spin+VIEW_LON;
  let x=p.x*Math.cos(a)-p.z*Math.sin(a);
  let z=p.x*Math.sin(a)+p.z*Math.cos(a);
  let y=p.y;
  const y2=y*Math.cos(VIEW_TILT)-z*Math.sin(VIEW_TILT);
  const z2=y*Math.sin(VIEW_TILT)+z*Math.cos(VIEW_TILT);
  return {x, y:y2, z:z2};
}

function draw(){
  spin += 0.0009;
  ctx.clearRect(0,0,W,H);
  const cx = W*0.5, cy = H*0.52;
  const R = Math.min(W*0.9, H*1.5) * 0.5 * zoom;

  const dotCol = cssVar('--globe-dot') || '#7a4a35';
  const hiCol  = cssVar('--globe-hi')  || '#e8763a';

  // atmosphere
  let g = ctx.createRadialGradient(cx,cy,R*0.85,cx,cy,R*1.35);
  g.addColorStop(0,'rgba(232,118,58,0.13)');
  g.addColorStop(1,'rgba(232,118,58,0)');
  ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,R*1.35,0,7); ctx.fill();
  // sphere body — very subtle, just enough to read as a globe
  g = ctx.createRadialGradient(cx-R*0.35,cy-R*0.35,R*0.1,cx,cy,R*1.05);
  g.addColorStop(0,'rgba(78,38,26,0.30)');
  g.addColorStop(0.7,'rgba(20,10,8,0.14)');
  g.addColorStop(1,'rgba(0,0,0,0)');
  ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,R,0,7); ctx.fill();

  // land dots
  for(const p of PTS){
    const r=rotate(p);
    if(r.z<=0.02) continue;
    const px=cx+r.x*R, py=cy-r.y*R;
    const depth=r.z;
    ctx.beginPath();
    ctx.arc(px,py, (1.0+1.15*depth)*Math.min(zoom,1.4), 0, 7);
    if(p.hi){ ctx.fillStyle=hiCol; ctx.globalAlpha=0.6+0.4*depth; }
    else    { ctx.fillStyle=dotCol; ctx.globalAlpha=0.32+0.6*depth; }
    ctx.fill();
  }
  ctx.globalAlpha=1;

  // great-circle arc ALC -> RUH
  const ang=Math.acos(CITY_A.x*CITY_B.x+CITY_A.y*CITY_B.y+CITY_A.z*CITY_B.z);
  const sa=Math.sin(ang);
  const path=[];
  for(let i=0;i<=64;i++){
    const t=i/64;
    const w1=Math.sin((1-t)*ang)/sa, w2=Math.sin(t*ang)/sa;
    let vx=w1*CITY_A.x+w2*CITY_B.x, vy=w1*CITY_A.y+w2*CITY_B.y, vz=w1*CITY_A.z+w2*CITY_B.z;
    const lift=1+0.16*Math.sin(Math.PI*t);
    const r=rotate({x:vx*lift,y:vy*lift,z:vz*lift});
    path.push({x:cx+r.x*R, y:cy-r.y*R, z:r.z, t});
  }
  ctx.lineWidth=2.5; ctx.lineCap='round'; ctx.setLineDash([1,6]); ctx.strokeStyle=hiCol;
  ctx.shadowColor=hiCol; ctx.shadowBlur=8;
  ctx.beginPath();
  let pen=false;
  for(const s of path){
    if(s.z<=0){ pen=false; continue; }
    if(!pen){ ctx.moveTo(s.x,s.y); pen=true; } else ctx.lineTo(s.x,s.y);
  }
  ctx.stroke(); ctx.setLineDash([]); ctx.shadowBlur=0;

  // endpoints
  for(const c of [CITY_A,CITY_B]){
    const r=rotate(c);
    if(r.z<=0) continue;
    const px=cx+r.x*R, py=cy-r.y*R;
    ctx.beginPath(); ctx.arc(px,py,3.5,0,7); ctx.fillStyle=hiCol; ctx.globalAlpha=1; ctx.fill();
    ctx.beginPath(); ctx.arc(px,py,8,0,7); ctx.strokeStyle=hiCol; ctx.globalAlpha=.35; ctx.lineWidth=1.5; ctx.stroke();
    ctx.globalAlpha=1;
  }

  // plane badge + card sit at a stable point near the middle of the globe
  let bx = cx - R*0.05; const by = cy - R*0.08;
  const rightPanel = document.querySelector('.main .aircraft');
  if (rightPanel) {
    const host = cv.getBoundingClientRect();
    const lim = rightPanel.getBoundingClientRect().left - host.left - 16;
    bx = Math.min(bx, lim - arcCard.offsetWidth / 2);
  }
  badge.style.left=bx+'px'; badge.style.top=by+'px';
  badge.style.transform='translate(-50%,-50%)';
  arcCard.style.left=bx+'px'; arcCard.style.top=(by+34)+'px';
  arcCard.style.transform='translate(-50%,0)';

  requestAnimationFrame(draw);
}
draw();

}
'''
