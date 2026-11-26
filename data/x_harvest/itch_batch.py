import itch_dl,sys,json,time,os,re
# usage: itch_batch.py outroot cap_mb user slug [slug...]
root,cap,user=sys.argv[1],int(sys.argv[2]),sys.argv[3]
log=f'r2/itch_{user}.jsonl' if not os.environ.get('R3') else f'r3/itch_{user}.jsonl'
for slug in sys.argv[4:]:
    page=f'https://{user}.itch.io/{slug}'
    try:
        res=itch_dl.fetch_all(page,f'{root}/{user}_{slug}',maxmb=cap)
        rec=dict(user=user,slug=slug,page=page,files=res)
    except Exception as e:
        rec=dict(user=user,slug=slug,page=page,error=repr(e)[:150])
    open(log,'a').write(json.dumps(rec)+'\n'); print(rec,flush=True); time.sleep(2)
