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
const CITY_A=cityVec(38.28,-0.56);   // Alicante
const CITY_B=cityVec(24.96,46.74);   // Riyadh

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
  const bx = cx - R*0.05, by = cy - R*0.08;
  badge.style.left=bx+'px'; badge.style.top=by+'px';
  badge.style.transform='translate(-50%,-50%)';
  arcCard.style.left=bx+'px'; arcCard.style.top=(by+34)+'px';
  arcCard.style.transform='translate(-50%,0)';

  requestAnimationFrame(draw);
}
draw();
