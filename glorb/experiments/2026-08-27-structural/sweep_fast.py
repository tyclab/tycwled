import json, time, wledlab
R,T="10.27.4.160","10.27.4.158"
for ps in (1,3,4,5,2,14,12,13,7,9,10,11):
    fr,ft=wledlab.simultaneous(R,T,40,preset=ps); time.sleep(3)
    json.dump({"ref":fr,"tgt":ft},open(f"captures/fast-p{ps}.json","w"))
    a,b=wledlab.fast_share(fr),wledlab.fast_share(ft)
    print(f"p{ps:>2}: fast_share ref {a:.3f} tgt {b:.3f} ratio {b/a if a else float('nan'):.2f}",flush=True)
print("SWEEP DONE",flush=True)
for ip in (R,T): wledlab.post(ip,"/json/state",{"on":True,"bri":255,"ps":4})
