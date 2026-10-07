"""Contact sheet: video frames (top row) vs liveview frames of given effects (one row each)."""
import json, sys
from PIL import Image, ImageDraw
gif, cap, out = sys.argv[1], sys.argv[2], sys.argv[3]; fxs=[int(x) for x in sys.argv[4:]]
names=json.load(open(f"{cap}/../census-scored.json"))["effects"]
W,H=34,42; SC=4; COLS=6; TW=W*SC; TH=H*SC; PAD=6; LAB=16
im=Image.open(gif); n=im.n_frames; vid=[im.seek(i) or im.convert("RGB").crop((75,70,250,450)) for i in range(0,n,max(1,n//COLS))][:COLS]
rows=1+len(fxs); sheet=Image.new("RGB",(COLS*(TW+PAD)+PAD, rows*(TH+PAD+LAB)+PAD),(24,24,24)); d=ImageDraw.Draw(sheet)
y=PAD; d.text((PAD,y),"video 2026-10-05 04:42 (phone, window crop)",fill=(220,220,220)); y+=LAB
for c,f in enumerate(vid):
    sheet.paste(f.resize((TW,TH)), (PAD+c*(TW+PAD), y))
y+=TH+PAD
for fx in fxs:
    fr=json.load(open(f"{cap}/fx{fx:03d}.json"))["frames"]; step=max(1,len(fr)//COLS)
    r=names[str(fx)]; d.text((PAD,y),f"fx {fx} {r['name']}  lit {r['lit_n']:.2f} chg {r['chg_n']:.2f} blue {r['blue']:.2f}",fill=(220,220,220)); y+=LAB
    for c,f in enumerate(fr[::step][:COLS]):
        t=Image.new("RGB",(W,H)); px=t.load()
        for i,col in enumerate(f[1]):
            px[i%W,i//W]=(int(col[:2],16),int(col[2:4],16),int(col[4:],16))
        sheet.paste(t.resize((TW,TH),Image.NEAREST),(PAD+c*(TW+PAD),y))
    y+=TH+PAD
sheet.save(out); print(out, sheet.size)
