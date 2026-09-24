#!/usr/bin/env python3
"""Atomic naming comparison after the preserved pilot revealed format confounds.

Wordings and semantic cases are unchanged. All decisions now use fresh single-
item requests. Code-fence wrappers are normalized; naming is separated from
secondary structural checks. This amendment is frozen before its own inference.
"""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import random
import re
import time

base_path=Path(__file__).resolve().parent.parent/'naming-evaluation'/'evaluate.py'
if not base_path.exists(): base_path=Path(__file__).with_name('evaluate.py')
spec=importlib.util.spec_from_file_location('base_evaluation',base_path)
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
PROTOCOL={**b.PROTOCOL,
 'design':'Atomic live naming comparison, following a preserved format-confounded pilot.',
 'amendment':'Unchanged candidates and semantic cases. One fresh conversation per decision. Accept a bare choice letter or its exact JSON equivalent. Strip an optional surrounding Markdown code fence from JSON code responses. Grade naming separately from secondary import/behavior-shape constraints. Include AST attribute names when detecting work labels, so test markers are covered. No wording changes or selective reruns.',
 'units':'768 separate model completion requests: 40 decision cases and 8 code cases, four conditions, two models and two seeds. Fixed tasks and model families still limit statistical generalization.',
 'selection':'Choose non-control condition with the fewest core naming failures across models/seeds; tie-break by fewer whitespace-delimited words then ID. Validation does not affect selection. Report secondary structural checks separately.',
 'scoring':'Prewritten semantic choice key; task-specific code naming/contract checks over Python ASTs. Only formatting normalization described above. No generated code execution. No full correctness claim.',
 'max_decision_tokens':24,
}

def normalized(text):
    text=text.strip()
    match=re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```',text,re.S)
    return match.group(1).strip() if match else text

def parse_code(text):
    return b.parse_output(normalized(text))

def parse_choice(text):
    text=normalized(text)
    if text in 'ABCD' and len(text)==1: return text
    data=b.parse_output(text)
    if isinstance(data,str) and data in 'ABCD' and len(data)==1: return data
    if isinstance(data,dict):
        value=data.get('choice',data.get('choices'))
        if isinstance(value,str) and len(value)==1 and value in 'ABCD': return value
    return None

def atomic_cases(seed):
    rng=random.Random(seed);items=list(b.CASES);rng.shuffle(items)
    for cid,split,kind,context,choices in items:
        pairs=list(enumerate(choices));rng.shuffle(pairs)
        answer='ABCD'[next(j for j,(index,_) in enumerate(pairs) if index==0)]
        prompt=context+'\n'+'\n'.join(f'{"ABCD"[j]}. {value}' for j,(_,value) in enumerate(pairs))+'\nChoose the best option. Return only its single letter: A, B, C or D.'
        yield {'case':cid,'split':split,'kind':kind,'answer':answer,'prompt':prompt}

NAMING_CHECKS={
 'g01':['one_function','descriptive','no_work_label'],
 'g02':['one_function','descriptive','no_work_label'],
 'g03':['one_class','domain_state','initializer','amount_attribute'],
 'g04':['path','contract','one_function'],
 'g05':['one_test','behavior_name','no_work_label'],
 'g06':['path','contract','audit','no_work_label','only_two_keys'],
 'g07':['path','public_contract','unrelated_preserved','one_helper','descriptive','updated_reference','no_work_label','no_alias'],
 'g08':['path','contract','one_function'],
}

def score_naming(task,output):
    structural=b.score_code(task,output)
    checks=structural['checks']
    selected={k:bool(checks.get(k,False)) for k in NAMING_CHECKS[task['id']]}
    if isinstance(output,dict) and isinstance(output.get('code'),str):
        try:
            nodes=list(ast.walk(ast.parse(output['code'])))
            attrs=' '.join(n.attr for n in nodes if isinstance(n,ast.Attribute)).lower()
            pattern={'g01':r'phase[_-]?4|mvp','g02':r'v3|third[_-]?rewrite|final','g05':r'milestone[_-]?7|ux[_-]?481','g07':r'phase[_-]?2'}.get(task['id'])
            if pattern: selected['no_work_label']=selected['no_work_label'] and re.search(pattern,attrs) is None
        except SyntaxError: pass
    return {'passed':all(selected.values()),'naming_checks':selected,'structure_passed':structural['passed'],'structure_checks':checks}

def self_test():
    b.self_test();count=0
    for letter in 'ABCD':
        for text in [letter,' '+letter+'\n',json.dumps({'choice':letter}),json.dumps({'choices':letter}),'```json\n'+json.dumps({'choice':letter})+'\n```']:
            assert parse_choice(text)==letter;count+=1
    for text in ['', 'AB','Choice A','{"choice":"AB"}']:
        assert parse_choice(text) is None;count+=1
    for seed in b.SEEDS:
        cases=list(atomic_cases(seed));assert len(cases)==40
        assert [x['answer'] for x in cases]==[x['answer'] for x in b.decision_prompt(seed)[1]];count+=1
    for task in b.GEN:
        for text in [json.dumps(task['good']),'```json\n'+json.dumps(task['good'])+'\n```']:
            assert score_naming(task,parse_code(text))['passed'];count+=1
    task=next(t for t in b.GEN if t['id']=='g05')
    with_import={**task['good'],'code':'import pytest\n'+task['good']['code']}
    result=score_naming(task,with_import)
    assert result['passed'] and not result['structure_passed'];count+=1
    marker={**task['good'],'code':'@pytest.mark.milestone7\n'+task['good']['code']}
    assert not score_naming(task,marker)['passed'];count+=1
    print(json.dumps({'atomic_self_checks':count,'passed':True}),flush=True)

def call(system,prompt,seed,limit):
    payload={'messages':[{'role':'system','content':system},{'role':'user','content':prompt}],'temperature':0.2,'top_p':0.9,'seed':seed,'max_tokens':limit,'cache_prompt':False}
    start=time.time()
    for attempt in range(2):
        try:
            response=b.request_json('http://127.0.0.1:8765/v1/chat/completions',payload,timeout=300)
            return payload,response,time.time()-start
        except Exception:
            if attempt: raise
            time.sleep(2)

def worker(model,condition):
    out=Path('confirmation-results')/(model+'-'+condition);out.mkdir(parents=True,exist_ok=True)
    b.write_json(out/'protocol.json',PROTOCOL)
    b.write_json(out/'manifest.json',{'protocol_sha256':b.sha_file(out/'protocol.json'),'script_sha256':b.sha_file(Path(__file__)),'base_sha256':b.sha_file(base_path),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'model':model,'condition':condition})
    self_test();records=[];process=None;log=None
    try:
        process,log=b.bootstrap(model,out)
        system='You are a coding assistant working in a repository. Follow the repository guidance below and the requested response format.\n\n'+b.CONDITIONS[condition]
        for seed in b.SEEDS:
            for case in atomic_cases(seed):
                payload,response,seconds=call(system,case['prompt'],seed,24)
                text=response['choices'][0]['message']['content'];answer=parse_choice(text)
                record={'model':model,'condition':condition,'seed':seed,'task_type':'decision',**{k:v for k,v in case.items() if k!='prompt'},'observed':answer,'passed':answer==case['answer'],'format_valid':answer is not None}
                records.append(record)
                b.write_json(out/f'{case["case"]}-{seed}.json',{'request':payload,'response':response,'seconds':seconds,'score':record})
                b.write_json(out/'scores.json',records)
                if len(records)%10==0: print(json.dumps({'model':model,'condition':condition,'observations':len(records),'passed':sum(r['passed'] for r in records)}),flush=True)
            tasks=list(b.GEN);random.Random(seed+1).shuffle(tasks)
            for task in tasks:
                prompt=task['task']+'\nReturn only JSON with string fields path (filename) and code (Python source).'
                payload,response,seconds=call(system,prompt,seed,400)
                text=response['choices'][0]['message']['content'];output=parse_code(text)
                score=score_naming(task,output)
                record={'model':model,'condition':condition,'seed':seed,'task_type':'code','case':task['id'],'split':task['split'],'kind':task['kind'],**score}
                records.append(record)
                b.write_json(out/f'{task["id"]}-{seed}.json',{'request':payload,'response':response,'seconds':seconds,'score':record})
                b.write_json(out/'scores.json',records)
                print(json.dumps({'model':model,'condition':condition,'seed':seed,'case':task['id'],**score}),flush=True)
        b.write_json(out/'status.json',{'complete':True,'observations':len(records),'completions':96})
    except Exception as error:
        b.write_json(out/'status.json',{'complete':False,'error':str(error),'observations':len(records)})
        raise
    finally:
        b.write_json(out/'scores.json',records)
        if process:
            process.terminate()
            try:process.wait(timeout=10)
            except Exception:process.kill()
        if log:log.close()

def aggregate(root):
    records=[];statuses=[]
    for p in sorted(root.rglob('scores.json')):records+=json.loads(p.read_text())
    for p in sorted(root.rglob('status.json')):statuses.append(json.loads(p.read_text()))
    complete=len(statuses)==8 and all(x['complete'] for x in statuses) and len(records)==768
    summary={'complete':complete,'observations':len(records),'conditions':{}}
    for condition in b.CONDITIONS:
        result={'words':b.words(b.CONDITIONS[condition])}
        dimensions={'core':lambda r:r['split']=='core','validation':lambda r:r['split']=='validation','decision':lambda r:r['task_type']=='decision','code_naming':lambda r:r['task_type']=='code'}
        dimensions.update({model:(lambda r,m=model:r['model']==m) for model in b.MODELS})
        for label,predicate in dimensions.items():
            rs=[r for r in records if r['condition']==condition and predicate(r)]
            result[label]={'passed':sum(r['passed'] for r in rs),'total':len(rs)}
        code=[r for r in records if r['condition']==condition and r['task_type']=='code']
        result['code_structure']={'passed':sum(r['structure_passed'] for r in code),'total':len(code)}
        result['failures']=[r for r in records if r['condition']==condition and not r['passed']]
        summary['conditions'][condition]=result
    if complete:
        order=sorted((k for k in b.CONDITIONS if k!='T4'),key=lambda k:(summary['conditions'][k]['core']['total']-summary['conditions'][k]['core']['passed'],b.words(b.CONDITIONS[k]),k))
        summary['selected_on_core']=order[0];summary['selection_order']=order
        (root/'selected-guidance.md').write_text(b.CONDITIONS[order[0]]+'\n')
    b.write_json(root/'summary.json',summary);b.write_json(root/'all-scores.json',records)
    print(json.dumps(summary,indent=2))
    if not complete:raise SystemExit('Incomplete confirmation: no winner declared')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');parser.add_argument('--worker',nargs=2);parser.add_argument('--aggregate',type=Path);args=parser.parse_args()
    if args.self_test:self_test()
    elif args.worker:worker(*args.worker)
    elif args.aggregate:aggregate(args.aggregate)
    else:parser.error('Choose --self-test, --worker or --aggregate')
