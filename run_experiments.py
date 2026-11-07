"""Run unmodified OSTEP simulators and preserve genuine command output."""
import sys, subprocess, pathlib, json, hashlib, platform, re
ROOT = pathlib.Path(__file__).resolve().parent
EXPERIMENTS = []
def add(name, script, args):
    EXPERIMENTS.append((name, script, args.split()))
for a in ('1m','2m','4m'):
    add('table_'+a, 'paging-linear-translate.py', f'-P 1k -a {a} -p 512m -v -n 0 -c')
for p in ('2k','4k'):
    add('pagesize_'+p,'paging-linear-translate.py',f'-P {p} -a 4m -p 512m -v -n 0 -c')
for u in (0,25,50,100):
    add('allocation_'+str(u),'paging-linear-translate.py',f'-P 1k -a 16k -p 32k -v -u {u} -c')
for name,args in [('seed_1','-P 8 -a 32 -p 1024 -v -s 1'),('seed_2','-P 8k -a 32k -p 1m -v -s 2'),('seed_3','-P 1m -a 256m -p 512m -v -s 3'),('over_physical','-P 1k -a 64k -p 32k -v'),('equal_physical','-P 1k -a 32k -p 32k -v'),('tiny_page','-P 1 -a 16 -p 32 -v'),('whole_space_page','-P 16k -a 16k -p 32k -v'),('oversized_page','-P 32k -a 16k -p 64k -v'),('nonpower_page','-P 3k -a 16k -p 64k -v'),('size_cap','-P 1m -a 256m -p 1g -v')]:
    add(name,'paging-linear-translate.py',args+' -c')
base='-a 128 -p 512 -b 0 -l 20 -B 512 -L 20'
for s in (0,1,2): add('seg_seed_'+str(s),'segmentation.py',base+f' -s {s} -c')
add('seg_boundaries','segmentation.py',base+' -A 0,19,20,63,64,107,108,127 -c')
add('seg_all_addresses','segmentation.py',base+' -A '+','.join(map(str,range(128)))+' -c')
add('seg_empty','segmentation.py','-a 128 -p 512 -b 0 -l 0 -B 512 -L 0 -A '+','.join(map(str,range(128)))+' -c')
def main():
    (ROOT/'logs').mkdir(exist_ok=True)
    records=[]
    for name,script,args in EXPERIMENTS:
        cmd=[sys.executable,'source/'+script]+args
        result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=30)
        out=result.stdout+result.stderr
        shown='python3 source/'+script+' '+' '.join(args)
        (ROOT/'logs'/f'{name}.txt').write_text('$ '+shown+'\n'+out+f'\nExit status: {result.returncode}\n')
        entries=re.findall(r'^\s*\[\s*\d+\]\s+(0x[0-9a-f]+)',out,re.M)
        records.append(dict(name=name,command=shown,exit_status=result.returncode,entries=len(entries),valid_entries=sum(int(x,16)!=0 for x in entries),valid_translations=len(re.findall(r'--> (?:[0-9a-f]{8}|VALID)',out)),invalid_translations=out.count('-->  Invalid')+out.count('SEGMENTATION VIOLATION')))
    checks={}
    by={r['name']:r for r in records}
    checks['table_counts']=[by['table_'+a]['entries'] for a in ('1m','2m','4m')]==[1024,2048,4096]
    checks['page_size_counts']=[by['pagesize_'+p]['entries'] for p in ('2k','4k')]==[2048,1024]
    checks['allocation_constant_size']=all(by['allocation_'+str(u)]['entries']==16 for u in (0,25,50,100))
    checks['segmentation_all']=by['seg_all_addresses']['valid_translations']==40 and by['seg_all_addresses']['invalid_translations']==88
    checks['empty_segments']=by['seg_empty']['valid_translations']==0 and by['seg_empty']['invalid_translations']==128
    checks['expected_rejections']=all(by[n]['exit_status']==1 for n in ('over_physical','equal_physical','oversized_page','nonpower_page','size_cap'))
    checks['remaining_runs_succeeded']=all(r['exit_status']==0 for r in records if r['name'] not in ('over_physical','equal_physical','oversized_page','nonpower_page','size_cap'))
    metadata=dict(python=sys.version,platform=platform.platform(),sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'source').glob('*.py')},checks=checks,runs=records)
    (ROOT/'results.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))
    assert all(checks.values()),checks
if __name__=='__main__':main()
