"""LOOK-004 comparison sheet (S&E 15!A140): composes the hero_look3 stills with their metadata into one PNG for the owner's review.
Presentation only; reads renders/p1/hero_look3/look3.json and the stills, writes look3_sheet.png beside them.

    python3 src/wayfarer/presentation/look_sheet.py [--dir renders/p1/hero_look3]
"""
from pathlib import Path
import argparse
import json
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
TITLES = {'tq_physical': '1 working camera (50 deg off aft, az 120): strict physical', 'tq_fill': '2 same camera: ILLUSTRATIVE FILL (concept, not physical)',
          'alt_physical': '3 alternative angle (establishing camera): strict physical', 'eye_physical': '4 Brow/EYE, strict physical: EYE dark (outward burn)',
          'eye_fill': '5 Brow/EYE: ILLUSTRATIVE FILL (concept, not physical)', 'eye_offburn': '6 off-burn orientation study (COAST; attitude OPEN)'}


def sheet(d):
    meta = json.loads((d/'look3.json').read_text()); views = [v for v in TITLES if v in meta['views']]
    W, H, pad, head = 800, 450, 12, 44; cols = 2; rows = (len(views)+1)//2
    out = Image.new('RGB', (cols*(W+pad)+pad, 70+rows*(H+head+pad)), (17, 17, 17)); g = ImageDraw.Draw(out)
    g.text((pad, 10), 'WAYFARER 001 - First Ignition exterior comparison (LOOK-004, 15!A140): WORKING CAMERA CHOICE / FINAL SIGNOFF OPEN', fill=(240, 240, 240))
    tq, es = meta['three_quarter'], meta['establishing']
    g.text((pad, 30), f"working camera: {tq['off_axis_deg']} deg off aft, azimuth {tq['azimuth_deg']:g} deg, blade score {tq['blade_score']}  |  "
                      f"establishing: azimuth {es['azimuth_deg']:g} deg, blade score {es['blade_score']}  |  REP_PROXY grey, no plume, no field glow", fill=(190, 190, 190))
    for i, v in enumerate(views):
        x, y = pad+(i % cols)*(W+pad), 70+(i//cols)*(H+head+pad)
        im = Image.open(d/meta['views'][v]['file']).convert('RGB').resize((W, H)); out.paste(im, (x, y+head))
        g.text((x, y+4), TITLES[v], fill=(255, 210, 120) if 'FILL' in TITLES[v] or 'off-burn' in TITLES[v] else (235, 235, 235))
        g.text((x, y+22), ('physical' if meta['views'][v]['physical'] else 'NOT PHYSICAL / labelled') + f" | state {meta['views'][v]['state']}", fill=(170, 170, 170))
    out.save(d/'look3_sheet.png'); return d/'look3_sheet.png'


if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('--dir', type=Path, default=ROOT/'renders/p1/hero_look3'); print(sheet(a.parse_args().dir))
