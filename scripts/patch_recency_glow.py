#!/usr/bin/env python3
"""Patch already-generated site/p*.html with recency-glow on last 5 fixations.

Saves re-running the full Playwright rebuild. Idempotent: looks for the
halo marker and skips files that already have it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

OLD_CIRCLES = (
    "const lE=[],cE=[],tE=[];\n"
    "for(let i=0;i<N;i++){const f=F[i],r=rF(f.d),c=cF(i,N);\n"
    "if(i>0){const p=F[i-1];const l=se('line',{x1:p.x,y1:p.y,x2:f.x,y2:f.y,stroke:c,'stroke-width':1.5,'stroke-opacity':.4});svg.appendChild(l);lE.push(l)}else lE.push(null);\n"
    "const cr=se('circle',{cx:f.x,cy:f.y,r,fill:c,'fill-opacity':.25,stroke:c,'stroke-width':2,'stroke-opacity':.8});svg.appendChild(cr);cE.push(cr);\n"
)

NEW_CIRCLES = (
    "const lE=[],cE=[],hE=[],tE=[];\n"
    "for(let i=0;i<N;i++){const f=F[i],r=rF(f.d),c=cF(i,N);\n"
    "if(i>0){const p=F[i-1];const l=se('line',{x1:p.x,y1:p.y,x2:f.x,y2:f.y,stroke:c,'stroke-width':1.5,'stroke-opacity':.4});svg.appendChild(l);lE.push(l)}else lE.push(null);\n"
    "const hr=se('circle',{cx:f.x,cy:f.y,r:r+6,fill:'none',stroke:'#fff','stroke-width':6,'stroke-opacity':0});svg.appendChild(hr);hE.push(hr);\n"
    "const cr=se('circle',{cx:f.x,cy:f.y,r,fill:c,'fill-opacity':.25,stroke:c,'stroke-width':2,'stroke-opacity':.8});svg.appendChild(cr);cE.push(cr);\n"
)

OLD_UV = (
    "for(let i=0;i<N;i++){const v=i>=lo&&i<=ci;cE[i].style.display=v?'':'none';tE[i].style.display=v?'':'none';\n"
    "if(lE[i])lE[i].style.display=(v&&i>lo)?'':'none';cE[i].setAttribute('stroke-width',pl&&i===ci?4:2);cE[i].setAttribute('stroke-opacity',pl&&i===ci?1:.8)}\n"
)

NEW_UV = (
    "const GLOW_OP=[.9,.55,.32,.18,.08],GLOW_R=[10,8,6,5,4];\n"
    "for(let i=0;i<N;i++){const v=i>=lo&&i<=ci;cE[i].style.display=v?'':'none';tE[i].style.display=v?'':'none';\n"
    "if(lE[i])lE[i].style.display=(v&&i>lo)?'':'none';cE[i].setAttribute('stroke-width',pl&&i===ci?4:2);cE[i].setAttribute('stroke-opacity',pl&&i===ci?1:.8);\n"
    "const rec=ci-i;if(v&&rec>=0&&rec<5){const br=parseFloat(cE[i].getAttribute('r'));hE[i].setAttribute('r',br+GLOW_R[rec]);hE[i].setAttribute('stroke-opacity',GLOW_OP[rec]);hE[i].style.display=''}else{hE[i].style.display='none'}}\n"
)

MARKER = "hE.push(hr)"


def patch(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "skip (already patched)"
    if OLD_CIRCLES not in text:
        return "FAIL: circle-init block not found"
    if OLD_UV not in text:
        return "FAIL: uv() block not found"
    text = text.replace(OLD_CIRCLES, NEW_CIRCLES, 1)
    text = text.replace(OLD_UV, NEW_UV, 1)
    path.write_text(text, encoding="utf-8")
    return "patched"


def main() -> int:
    files = sorted(SITE.glob("p*.html"))
    if not files:
        print(f"no matches in {SITE}", file=sys.stderr)
        return 1
    fails = 0
    for f in files:
        result = patch(f)
        print(f"{f.name}: {result}")
        if result.startswith("FAIL"):
            fails += 1
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
