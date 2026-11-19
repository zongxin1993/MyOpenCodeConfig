#!/usr/bin/env python3
"""Tool-only paired observations. This does not measure LLM or task completion speed."""
import argparse,json,statistics,subprocess,tempfile,time
from pathlib import Path

def timed(argv,**kwargs):
    started=time.perf_counter();r=subprocess.run(argv,capture_output=True,text=True,check=True,**kwargs)
    return (time.perf_counter()-started)*1000,r.stdout

def benchmark(rtk,ast):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);f=root/'sample.py';f.write_text('def clamp(value):\n    return value\n'+''.join('def noise_'+str(i)+'(value):\n    return value + 1\n' for i in range(400)))
        rows=[]
        for i in range(3):
            modes=['native','filtered'] if i%2==0 else ['filtered','native']
            for mode in modes:
                raw_ms,raw=timed(['rg','--with-filename','--line-number','return',str(f)])
                filter_ms=0;out=raw
                if mode=='filtered':filter_ms,out=timed([rtk,'pipe','--filter','grep'],input=raw)
                rows.append({'round':i+1,'mode':mode,'search_ms':raw_ms,'filter_ms':filter_ms,'raw_chars':len(raw),'display_chars':len(out)})
        for i in range(3):
            rg_ms,rgout=timed(['rg','--line-number','^def clamp\\(',str(f)])
            ast_ms,out=timed([ast,'run','--lang','python','--pattern','def clamp($$$ARGS):\n    $$$BODY','--json=compact','--stdin'],input=f.read_text())
            hits=json.loads(out);assert len(hits)==1 and len(rgout.strip().splitlines())==1
            rows.append({'round':i+1,'mode':'syntax-vs-known-text','rg_ms':rg_ms,'ast_ms':ast_ms,'expected_matches':1})
    return {'scope':'CLI only; no claim of model or end-to-end speedup','observations':rows}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rtk',required=True);p.add_argument('--ast',required=True);a=p.parse_args();print(json.dumps(benchmark(a.rtk,a.ast),indent=2))
