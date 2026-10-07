import sys, colorsys, json
from PIL import Image, ImageSequence
im=Image.open(sys.argv[1]); X0,Y0,X1,Y1=75,70,250,450
lit=[];blue=[];white=[];sat=[];val=[];chg=[];prev=None
for fr in ImageSequence.Iterator(im):
    g=fr.convert("RGB").crop((X0,Y0,X1,Y1)); px=g.load(); w,h=g.size; n=w*h
    on=[]; l=[]
    for y in range(h):
        for x in range(w):
            r,gg,b=px[x,y]; m=max(r,gg,b); o=m>150; on.append(o)
            if o: l.append(colorsys.rgb_to_hsv(r/255,gg/255,b/255))
    lit.append(len(l)/n)
    blue.append(sum(1 for h_,s,v in l if 0.5<=h_<=0.72 and s>0.35)/max(1,len(l)))
    white.append(sum(1 for h_,s,v in l if s<0.25)/max(1,len(l)))
    sat.append(sum(s for h_,s,v in l)/max(1,len(l))); val.append(sum(v for h_,s,v in l)/max(1,len(l)))
    if prev: chg.append(sum(1 for a,b in zip(prev,on) if a!=b)/n)
    prev=on
f=lambda a:sum(a)/len(a)
V=dict(lit=f(lit),lit_min=min(lit),lit_max=max(lit),chg=f(chg),blue=f(blue),white=f(white),sat=f(sat),val=f(val))
print(json.dumps(V)); json.dump(V,open(sys.argv[2],"w"))
