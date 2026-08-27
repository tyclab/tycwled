import json, sys, math, time, threading, wledlab
sys.path.insert(0,".")
from hipsim import W,H,grids
R,T="10.27.4.160","10.27.4.158"; fs=10
def feats(gr):
    t0=gr[0][0]; cells=[(y,x) for y in range(H) for x in range(W) if gr[0][1][y][x] is not None and max(G[y][x] for _,G in gr)>0.05]
    n=int((gr[-1][0]-t0)*fs); out={c:[] for c in cells}; j=0; mean=[]
    for k in range(n):
        t=t0+k/fs
        while j+1<len(gr) and gr[j+1][0]<=t: j+=1
        G=gr[j][1]; m=0
        for c in cells: v=G[c[0]][c[1]]; out[c].append(v); m+=v
        mean.append(m/len(cells))
    tot=[0]*5
    for c,s in out.items():
        m=sum(s)/n; s=[x-m for x in s]
        for k in range(1,n//2):
            f=k*fs/n; re=sum(s[i]*math.cos(2*math.pi*k*i/n) for i in range(n)); im=sum(s[i]*math.sin(2*math.pi*k*i/n) for i in range(n)); p=re*re+im*im
            tot[0 if f<0.1 else 1 if f<0.3 else 2 if f<1 else 3 if f<3 else 4]+=p
    Tt=sum(tot) or 1; bands=[v/Tt*100 for v in tot]
    mm=sum(mean)/n; tstd=(sum((x-mm)**2 for x in mean)/n)**0.5
    sstd=sum((sum((out[c][k]-mean[k])**2 for c in cells)/len(cells))**0.5 for k in range(n))/n
    act=sum(sum(abs((out[c][k]-mean[k])-(out[c][k+5]-mean[k+5])) for c in cells)/len(cells) for k in range(n-5))/(n-5)
    return dict(bands=[round(b,1) for b in bands], fast=round(bands[2]+bands[3]+bands[4],1), ratio=round(sstd/tstd,2), spat_act=round(act,3), mean=round(mm,3), lit=len(cells))
def capture_both(seconds):
    res={}
    t1=threading.Thread(target=lambda: res.__setitem__("ref", wledlab.live(R,seconds)))
    t2=threading.Thread(target=lambda: res.__setitem__("tgt", wledlab.live(T,seconds)))
    t1.start(); t2.start(); t1.join(); t2.join(); return res["ref"],res["tgt"]
def run(seg, seconds=40):
    for ip in (R,T): wledlab.post(ip,"/json/state",{"on":True,"bri":255,"ps":2})
    time.sleep(1); wledlab.post(T,"/json/state",{"seg":[dict(id=0,**seg)]}); time.sleep(1.5)
    fr,ft=capture_both(seconds); time.sleep(3)
    a,b=feats(grids(fr)),feats(grids(ft))
    score=abs(a["fast"]-b["fast"])/10+abs(math.log(a["ratio"]/b["ratio"]))*2+abs(math.log(a["spat_act"]/b["spat_act"]))*2
    print(f"{seg}: ref {a} | tgt {b} | score {score:.2f}",flush=True)
    return score
cands=[dict(sx=112,ix=112,c3=54),dict(sx=64,ix=64,c3=54),dict(sx=80,ix=80,c3=54),dict(sx=48,ix=48,c3=54),dict(sx=64,ix=64,c3=40),dict(sx=64,ix=64,c3=70)]
if len(sys.argv)>1: cands=[json.loads(a) for a in sys.argv[1:]]
res={json.dumps(c):run(c) for c in cands}
best=min(res,key=res.get); print("BEST",best,res[best],flush=True)
for ip in (R,T): wledlab.post(ip,"/json/state",{"on":True,"bri":255,"ps":2})
