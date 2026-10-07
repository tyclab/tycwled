import sys, colorsys
from PIL import Image, ImageSequence
im=Image.open(sys.argv[1]); W,H=im.size
union=[[0]*W for _ in range(H)]; frames=[]
for fr in ImageSequence.Iterator(im):
    g=fr.convert("RGB"); px=g.load(); m=[[max(px[x,y])>90 for x in range(W)] for y in range(H)]
    frames.append((g,m))
    for y in range(H):
        for x in range(W):
            if m[y][x]: union[y][x]=1
# region = pixels lit in >=5% of frames
cnt=[[0]*W for _ in range(H)]
for g,m in frames:
    for y in range(H):
        for x in range(W):
            cnt[y][x]+=m[y][x]
reg=[(x,y) for y in range(H) for x in range(W) if cnt[y][x]>=0.05*len(frames)]
xs=[p[0] for p in reg]; ys=[p[1] for p in reg]
print("region px",len(reg),"of",W*H,"bbox",min(xs),min(ys),max(xs),max(ys))
lit=[];blue=[];white=[];val=[];sat=[];chg=[];prev=None
for g,m in frames:
    px=g.load(); l=[px[x,y] for x,y in reg if m[y][x]]; lit.append(len(l)/len(reg))
    hs=[colorsys.rgb_to_hsv(r/255,gg/255,b/255) for r,gg,b in l]
    blue.append(sum(1 for h,s,v in hs if 0.5<=h<=0.72 and s>0.35)/max(1,len(l)))
    white.append(sum(1 for h,s,v in hs if s<0.25 and v>0.6)/max(1,len(l)))
    val.append(sum(v for h,s,v in hs)/max(1,len(l))); sat.append(sum(s for h,s,v in hs)/max(1,len(l)))
    cur=[m[y][x] for x,y in reg]
    if prev: chg.append(sum(1 for a,b in zip(prev,cur) if a!=b)/len(reg))
    prev=cur
f=lambda a:sum(a)/len(a)
print(f"video in-region: lit {f(lit):.2f} (min {min(lit):.2f} max {max(lit):.2f}) chg/frame {f(chg):.3f} blue {f(blue):.2f} white {f(white):.2f} val {f(val):.2f} sat {f(sat):.2f} fps? dur={im.info.get('duration')}ms/frame")
