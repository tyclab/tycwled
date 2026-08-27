import json, math, sys, wledlab
lm=json.load(open("glorb/wled16-port/ledmap.json")); W,H=lm["width"],lm["height"]; mp=lm["map"]
def grids(frames):
    out=[]
    for t,leds in frames:
        G=[[None]*W for _ in range(H)]
        for i,p in enumerate(mp):
            if p>=0: G[i//W][i%W]=wledlab.hsv(leds[p])[2]
        out.append((t,G))
    return out
def stats(gr, label):
    means=[]; sstd=[]
    for t,G in gr:
        v=[x for r in G for x in r if x is not None]; m=sum(v)/len(v); means.append((t,m)); sstd.append((sum((x-m)**2 for x in v)/len(v))**0.5)
    ts=[t for t,_ in means]; ms=[m for _,m in means]; mm=sum(ms)/len(ms); tstd=(sum((m-mm)**2 for m in ms)/len(ms))**0.5
    # autocorr of frame mean at 0.25 s resampling
    dt=0.25; rs=[]; t=ts[0]; j=0
    while t<=ts[-1]:
        while j+1<len(ts) and ts[j+1]<=t: j+=1
        rs.append(ms[j]-mm); t+=dt
    den=sum(x*x for x in rs) or 1
    ac=[sum(rs[i]*rs[i+l] for i in range(len(rs)-l))/den for l in range(min(len(rs)//2,80))]
    pk=[l for l in range(2,len(ac)-1) if ac[l]>ac[l-1] and ac[l]>=ac[l+1] and ac[l]>0.2]
    per=pk[0]*dt if pk else None
    # spatial-demeaned activity per 0.5 s
    j=0; act=[]
    for i,(t,G) in enumerate(gr):
        while j<len(gr) and gr[j][0]<t+0.5: j+=1
        if j>=len(gr): break
        A=[x for r in G for x in r if x is not None]; B=[x for r in gr[j][1] for x in r if x is not None]
        ma=sum(A)/len(A); mb=sum(B)/len(B)
        act.append(sum(abs((a-ma)-(b-mb)) for a,b in zip(A,B))/len(A))
    # x-profile autocorr on middle rows (wavelength)
    print(f"{label:>22}: mean {mm:.2f} temporal-std {tstd:.3f} spatial-std {sum(sstd)/len(sstd):.3f} ratio {sum(sstd)/len(sstd)/tstd:.2f} global-period {per} spatial-activity/0.5s {sum(act)/len(act):.3f}")
def sin8(x): return int(128+127.5*math.sin(2*math.pi*(x%256)/256))&255
def cos8(x): return int(128+127.5*math.cos(2*math.pi*(x%256)/256))&255
def sim(sx,ix,c3,seconds=40,fps=20,lo=175/255,hi=1.0):
    fr=[]
    for k in range(int(seconds*fps)):
        now=int(k*1000/fps); a=now//((c3>>1)+1)
        G=[[None]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                idx=sin8(cos8(x*sx//16 + a//3) + sin8(y*ix//16 + a//4) + a)
                G[y][x]=lo+(hi-lo)*idx/255
        for i,p in enumerate(mp):
            if p<0: G[i//W][i%W]=None
        fr.append((k/fps,G))
    return fr
if __name__=="__main__":
    d=json.load(open("captures/p2-recapture.json"))
    stats(grids(d["ref"]),"ref .160"); stats(grids(d["tgt"]),"tgt .158")
    for p in [(112,112,12)]+[tuple(map(int,a.split(","))) for a in sys.argv[1:]]:
        stats(sim(*p),"sim %s"%(p,))
