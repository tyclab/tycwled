import socket, struct, time, json, threading, sys
sys.path.insert(0, sys.argv[2]); import wledlab
H="10.27.4.221"; N=2856; OUT=sys.argv[1]; MAXB=int(sys.argv[3]); SECS=3.5
sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
def ddp(rgb):
    data=bytes(rgb)*N; off=0
    while off<len(data):
        chunk=data[off:off+MAXB]; last=off+len(chunk)>=len(data)
        sock.sendto(struct.pack(">BBBBIH",0x40|(1 if last else 0),0,1,1,off,len(chunk))+chunk,(H,4048)); off+=len(chunk); time.sleep(0.0015)
res={}; T0=time.time()
t=threading.Thread(target=lambda: res.update(fr=wledlab.live(H,30.0))); t.start(); time.sleep(1.0)
sched=[]
def phase(name,col,hz):
    sched.append((name,time.time()-T0)); half=0.5/hz; te=time.time()+SECS; on=False; n=0
    while time.time()<te:
        on=not on; ddp(col if on else (0,0,0)); n+=1
        time.sleep(max(0,half-0.0015*((N*3+MAXB-1)//MAXB)))
    sched.append((name+"-sent-frames",n))
for col,cn in (((255,255,255),"white"),((0,0,255),"blue")):
    for hz in (5,10,20): phase(f"{cn}-{hz}Hz",col,hz)
sched.append(("black-gap",time.time()-T0)); ddp((0,0,0)); time.sleep(1.0)
sched.append(("white-hold",time.time()-T0)); ddp((255,255,255)); time.sleep(SECS)
sched.append(("black",time.time()-T0)); ddp((0,0,0)); time.sleep(0.5); sched.append(("end",time.time()-T0))
t.join(); fr=res["fr"]
# wledlab stamps frames relative to its own start (~T0+1.0 incl. handshake); the first non-black frame after 'white-hold' pins the offset
json.dump({"meta":{"maxb":MAXB,"capture_offset_s":1.0,"phases":sched},"frames":fr}, open(OUT,"w"))
n=len(fr[0][1]); lit=lambda f: sum(1 for c in f[1] if int(c[:2],16)+int(c[2:4],16)+int(c[4:],16)>120)/n/0.2731
ph=[(a,b) for a,b in sched if not a.endswith("sent-frames")]
print("frames",len(fr),"rate %.1f Hz"%(len(fr)/(fr[-1][0]-fr[0][0])))
for (a,t0),(b,t1) in zip(ph,ph[1:]):
    seq=[lit(f) for f in fr if t0-1.0<=f[0]<t1-1.0]
    tog=sum(1 for x,y in zip(seq,seq[1:]) if (x>0.5)!=(y>0.5))
    sent=dict(sched).get(a+"-sent-frames","")
    print(f"{a:<12} frames {len(seq):>3}  lit min {min(seq) if seq else 0:.2f} max {max(seq) if seq else 0:.2f} mean {sum(seq)/len(seq) if seq else 0:.2f}  toggles {tog}  sent {sent}")
