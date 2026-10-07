import re, json, sys, time, subprocess, urllib.request, os, colorsys
H="http://10.27.4.221"; W=sys.argv[1]; OUT=sys.argv[2]; CAP=sys.argv[3]
os.makedirs(CAP, exist_ok=True)
def get(p): return json.load(urllib.request.urlopen(H+p, timeout=8))
def post(o):
    r=urllib.request.Request(H+"/json/state", json.dumps(o).encode(), {"Content-Type":"application/json"}); urllib.request.urlopen(r, timeout=8).read()
eff=get("/json/eff")
import urllib.request as U
raw=U.urlopen(H+"/json/fxdata",timeout=8).read().decode(errors="replace").strip()
fxd=[x.strip('"') for x in re.findall(r'"(?:[^"\\]|\\.)*"|[^,\[\]]+', raw[1:-1])]
if len(fxd)<len(eff): fxd+=[""]*(len(eff)-len(fxd))
done={json.loads(l)["fx"] for l in open(OUT)} if os.path.exists(OUT) else set()
def hsv(c):
    r,g,b=int(c[:2],16)/255,int(c[2:4],16)/255,int(c[4:],16)/255
    return colorsys.rgb_to_hsv(r,g,b)
for i,name in enumerate(eff):
    if name.startswith("RSVD") or i in done: continue
    try:
        post({"on":True,"bri":100,"seg":[{"id":0,"fx":i,"fxdef":True}]}); time.sleep(0.3)
        post({"seg":[{"id":0,"sx":200,"ix":180,"pal":9}]}); time.sleep(1.5)
        cap=f"{CAP}/fx{i:03d}.json"
        subprocess.run(["python3",W,"--width","68","--height","42","capture","--host","10.27.4.221","--seconds","3.5","--out",cap],capture_output=True,timeout=40)
        fr=json.load(open(cap))["frames"]
        n=len(fr[0][1]); lit=[];chg=[];blue=[];white=[];val=[];sat=[]
        for k,f in enumerate(fr):
            L=f[1]; l=[c for c in L if c!="000000"]; lit.append(len(l)/n)
            hs=[hsv(c) for c in l]
            blue.append(sum(1 for h,s,v in hs if 0.5<=h<=0.72 and s>0.35)/max(1,len(l)))
            white.append(sum(1 for h,s,v in hs if s<0.25 and v>0.6)/max(1,len(l)))
            val.append(sum(v for h,s,v in hs)/max(1,len(l))); sat.append(sum(s for h,s,v in hs)/max(1,len(l)))
            if k: chg.append(sum(1 for a,b in zip(fr[k-1][1],L) if a!=b)/n)
        seg=get("/json/state")["seg"][0]
        rec={"fx":i,"name":name,"fxdata":fxd[i],"frames":len(fr),"lit":sum(lit)/len(lit),"lit_min":min(lit),"lit_max":max(lit),
             "chg":sum(chg)/max(1,len(chg)),"blue":sum(blue)/len(blue),"white":sum(white)/len(white),"val":sum(val)/len(val),"sat":sum(sat)/len(sat),
             "seg":{k:seg[k] for k in ("sx","ix","pal","c1","c2","c3","o1","o2","o3","si")}}
    except Exception as e:
        rec={"fx":i,"name":name,"error":str(e)}
    with open(OUT,"a") as f: f.write(json.dumps(rec)+"\n")
    print(i,name,rec.get("lit"),rec.get("chg"),rec.get("error",""),flush=True)
post({"seg":[{"id":0,"fx":175,"sx":200,"ix":180,"pal":9,"c1":128}]})
print("DONE",flush=True)
