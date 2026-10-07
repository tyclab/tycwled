"""Re-score census captures with the video's thresholds (lit = V>0.35) and rank against the video."""
import json, sys, os, colorsys
CAP=sys.argv[1]; EFF=sys.argv[2]; N=int(sys.argv[3]) if len(sys.argv)>3 else 25
SOLID=None
V=dict(lit=0.73, chg=0.10, blue=0.89, white=0.0, sat=0.71, val=0.68)
if len(sys.argv)>4:
    V=json.load(open(sys.argv[4]))
def hsv(c): return colorsys.rgb_to_hsv(int(c[:2],16)/255,int(c[2:4],16)/255,int(c[4:],16)/255)
rows=[json.loads(l) for l in open(EFF)]
res={}
for r in rows:
    if "error" in r: continue
    p=f"{CAP}/fx{r['fx']:03d}.json"
    if not os.path.exists(p): continue
    fr=json.load(open(p))["frames"]; n=len(fr[0][1])
    lit=[];chg=[];blue=[];white=[];sat=[];val=[];prev=None
    for f in fr:
        hs=[hsv(c) for c in f[1]]; on=[v>0.35 for h,s,v in hs]; l=[x for x,o in zip(hs,on) if o]
        lit.append(sum(on)/n)
        blue.append(sum(1 for h,s,v in l if 0.5<=h<=0.72 and s>0.35)/max(1,len(l)))
        white.append(sum(1 for h,s,v in l if s<0.25)/max(1,len(l)))
        sat.append(sum(s for h,s,v in l)/max(1,len(l))); val.append(sum(v for h,s,v in l)/max(1,len(l)))
        if prev is not None: chg.append(sum(1 for a,b in zip(prev,on) if a!=b)/n)
        prev=on
    m=lambda a:sum(a)/max(1,len(a))
    res[r["fx"]]=dict(name=r["name"],fxdata=r["fxdata"],seg=r["seg"],lit=m(lit),lit_min=min(lit),lit_max=max(lit),chg=m(chg),blue=m(blue),white=m(white),sat=m(sat),val=m(val))
SOLID=res[0]["lit"] if 0 in res and res[0]["lit"]>0 else 0.2731
out=[]
for fx,r in res.items():
    lit=r["lit"]/SOLID; chg=r["chg"]/SOLID
    d=((lit-V["lit"])**2*4 + (r["blue"]-V["blue"])**2*2 + r["white"]**2*2 + min(abs(chg-V["chg"]),0.5)**2*2 + (r["sat"]-V["sat"])**2)**0.5
    r.update(lit_n=lit,chg_n=chg,score=d); out.append((d,fx))
out.sort()
json.dump({"solid_baseline":SOLID,"video":V,"effects":{str(k):v for k,v in res.items()}}, open(f"{CAP}/../census-scored.json","w"), indent=1)
print(f"solid baseline {SOLID:.3f}; {len(res)} effects scored")
print(f"{'rank':>4} {'fx':>3} {'name':<22} {'lit':>5} {'range':>9} {'chg':>5} {'blue':>5} {'white':>5} {'sat':>5} flags  c1,c2,c3,o1")
for i,(d,fx) in enumerate(out[:N],1):
    r=res[fx]; fl=r["fxdata"].split(";")[3] if r["fxdata"].count(";")>=3 else ""; s=r["seg"]
    print(f"{i:>4} {fx:>3} {r['name']:<22} {r['lit_n']:5.2f} {r['lit_min']/SOLID:4.2f}-{r['lit_max']/SOLID:4.2f} {r['chg_n']:5.2f} {r['blue']:5.2f} {r['white']:5.2f} {r['sat']:5.2f} {fl:<6} {s['c1']},{s['c2']},{s['c3']},{s['o1']}  {d:.2f}")
