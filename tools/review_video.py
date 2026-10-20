"""M7.1 review cuts from a Demonstrator 01 recording (`--autoplay --record-exit`, log.txt beside the .avi): the full walkthrough as
H.264 MP4 with chapter marks from the WF_DEMO_CHAPTER lines, a ~65 s highlight (M7 sections, ARRIVAL and INSPECT) and a contact sheet
with one frame per chapter plus INSPECT off and on. Presentation only; the original capture is left untouched.

    python3 tools/review_video.py <recording run dir> <output dir>      # FFMPEG=<path> picks the encoder (needs libx264)
"""
import subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont
FF=os.environ.get('FFMPEG', 'ffmpeg'); W, R = sys.argv[1], sys.argv[2]; os.makedirs(R, exist_ok=True)
src=f'{W}/m7_demo01_full.avi'
marks=[l.split() for l in open(f'{W}/log.txt') if l.startswith('WF_DEMO_CHAPTER')]
import json; rec=json.loads(next(l for l in open(f'{W}/log.txt') if l.startswith('WF_DEMO_RECORDING')).split(' ',1)[1]); end=rec['display_s']
T={n:float(t) for _,n,t in marks}
with open(f'{R}/chapters.ffmeta','w') as f:
    f.write(';FFMETADATA1\ntitle=Wayfarer Demonstrator 01 - M7 walkthrough (SIMULATION_ONLY)\n')
    for i,(_,n,t) in enumerate(marks):
        e=float(marks[i+1][2]) if i+1<len(marks) else end
        f.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(float(t)*1000)}\nEND={int(e*1000)}\ntitle={i+1} {n}\n')
x264=['-an','-c:v','libx264','-preset','slow','-pix_fmt','yuv420p','-movflags','+faststart']
subprocess.run([FF,'-v','error','-y','-i',src,'-i',f'{R}/chapters.ffmeta','-map','0:v','-map_metadata','1','-map_chapters','1','-crf','22',*x264,f'{R}/m7_demo01_full.mp4'],check=True)
segs=[(0,6),(T['ENTRY'],T['MICROGRAVITY']),(T['MICROGRAVITY'],T['MODE']),(70,82),(125,137),(T['ARRIVAL'],end)]
f=''.join(f'[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];' for i,(a,b) in enumerate(segs))+''.join(f'[v{i}]' for i in range(len(segs)))+f'concat=n={len(segs)}:v=1:a=0[out]'
subprocess.run([FF,'-v','error','-y','-i',src,'-filter_complex',f,'-map','[out]','-crf','21',*x264,f'{R}/m7_highlight.mp4'],check=True)
I=T['INSPECT']; flip=2.5
shots=[(5,'1 EXTERIOR','docked ship; M7.EXT.PORT is at the port, beyond the 28 m detail range here'),(T['ENTRY']+6,'2 ENTRY','entry chamber and trunk: M7.ENT / M7.TRK'),(T['MICROGRAVITY']+3.5,'3 MICROGRAVITY','trunk push-off and catch: M7.TRK'),
 (T['MODE']+9,'4 MODE','DOCKED -> COAST, rings spin up'),(80,'5 TRANSFER','despun drum, closures PROTOTYPE: M7.XFR'),(130,'6 DESCENT','ring A crew tube: M7.SPK'),
 (T['GRAVITY']+1.5,'7 GRAVITY','ring A aisle in spin gravity'),(T['ARRIVAL']+2.5,'8 ARRIVAL','ring A sector 1 habitat stop (M7.RA1 is overhead, mostly out of frame)'),
 (I+1.2,'9 INSPECT - layer OFF','entry chamber stop: engineering + route fit-out only'),(I+flip+1.2,'9 INSPECT - layer ON','same view: M7.ENT production layer')]
tw,th=640,400; cols=2; rows=(len(shots)+1)//2; pad=44
sheet=Image.new('RGB',(cols*tw,rows*(th+pad)+70),(12,14,18)); d=ImageDraw.Draw(sheet)
def font(sz,b=False):
    p='/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf'%('-Bold' if b else '')
    return ImageFont.truetype(p,sz) if os.path.exists(p) else ImageFont.load_default()
d.text((16,14),'WAYFARER 001 - Demonstrator 01 M7 walkthrough - contact sheet',fill=(240,170,40),font=font(22,True))
d.text((16,44),f'Godot 4.7 Compatibility, 1280x800 @ 30 fps, {end:.1f} s, autoplay ended by itself after INSPECT (exit 0). SIMULATION_ONLY; production-layer maturity per the manifest.',fill=(200,205,212),font=font(13))
for i,(t,title,sub) in enumerate(shots):
    fn=f'{R}/frame_{i+1:02d}.png'
    subprocess.run([FF,'-v','error','-y','-ss',str(t),'-i',src,'-frames:v','1',fn],check=True)
    im=Image.open(fn).resize((tw,th)); x=(i%cols)*tw; y=70+(i//cols)*(th+pad); sheet.paste(im,(x,y))
    d.text((x+10,y+th+4),f'{title}  ({t:.0f} s)',fill=(240,170,40),font=font(16,True)); d.text((x+10,y+th+24),sub,fill=(200,205,212),font=font(12))
sheet.save(f'{R}/m7_contact_sheet.jpg',quality=88)
print(json.dumps(dict(highlight_s=round(sum(b-a for a,b in segs),2), full_s=end)))
