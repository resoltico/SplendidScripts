#!/usr/bin/env python3
"""Frozen, candidate-blind naming-guidance evaluation; Python standard library only.

Run --self-test locally. Run --worker MODEL CONDITION on an internet-connected
Linux runner. Each worker downloads an open model, serves it on loopback, and
saves every request/response, the frozen protocol, and deterministic scores.
No model-generated code is executed. AST checks examine generated code.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

SEEDS = [19073, 42043]
CONDITIONS = {
    'K7': '''## Purpose-based naming

Name files, directories, and code elements—including functions, methods, types, variables, tests, and configuration keys—for what they represent or do. Use precise, consistent domain vocabulary and established language/project conventions. Names must be clear in context without knowing the implementation plan or change history.

Do not derive implementation names from product maturity, plan steps, task provenance, temporary status, relative age, or unsupported quality claims. Distinguish alternatives by actual responsibility or behavior.

Apply this semantically, not as a word blacklist: states, stages, versions, and ordering are valid when intrinsic to the domain, algorithm, contract, or artifact’s purpose. Planning and historical artifacts may identify the work they document.

Review names introduced or changed. Keep renames within scope, update affected references, and preserve required external names and compatibility.''',
    'M2': '''## Purpose-based naming

Name files, directories and their contents—including functions, types, variables, tests and configuration—for what they represent or do. Use precise, consistent, idiomatic names. Distinguish alternatives by actual responsibility or behavior, not product maturity, work-plan steps, change history, vague labels or unsupported quality claims.

States, stages, versions and ordering belong in names only when meaningful to the domain, algorithm, contract or artifact itself. Keep implementation history in planning and historical records.

Review names you introduce or change. When renaming, update affected references, stay within scope and preserve required external names and compatibility.''',
    'R9': '''## Purpose-based naming

Name files, directories and everything defined within them by purpose or behavior—not development status, plan steps or change history. Use precise, consistent, idiomatic names; distinguish variants by meaningful differences, not vague or promotional labels.

Retain states, stages, versions and ordering when intrinsic to the subject or required by a contract or tool. Keep implementation history in planning/history records.

Review changed names, update references when renaming, avoid unrelated churn and preserve compatibility.''',
    'T4': '',
}
MODELS = {
    'qwen-small': 'Qwen/Qwen2.5-1.5B-Instruct-GGUF',
    'qwen-medium': 'unsloth/Qwen3-4B-Instruct-2507-GGUF',
}
# Correct choice is first here, but independently shuffled before model exposure.
# Core cases select a wording. Validation cases confirm it without retuning.
CASES = [
('n01','core','avoid','Private Python function checks whether a token has expired. The work plan calls this phase 3.', ['is_token_expired','phase3_check','final_check','handle_stuff']),
('n02','core','avoid','Directory contains persistent invoice validation code written during the product MVP.', ['invoice_validation','mvp_validation','new_stuff','enhanced_core']),
('n03','core','avoid','Two parsers coexist: one reads a whole document; the other processes a stream. Name the latter.', ['StreamingParser','ParserV2','NewParser','BetterParser']),
('n04','core','avoid','Python regression test rejects negative invoice amounts. Ticket PAY-217 introduced it.', ['test_rejects_negative_amount','test_PAY217','test_phase2','test_new_validator']),
('n05','core','avoid','Configuration switch enables writing audit logs, a capability completed in milestone 4.', ['audit_logging_enabled','milestone4_enabled','new_mode','enhanced_enabled']),
('n06','core','avoid','Class retries failed HTTP requests; all retries are synchronous. Choose a truthful name.', ['RetryingHttpClient','AsyncHttpClient','PerfectHttpClient','HttpClientFinal']),
('n07','core','avoid','Private variable holds a request timeout in milliseconds. Project uses explicit unit suffixes.', ['request_timeout_ms','timeout_v2','misc_value','new_timeout']),
('n08','core','avoid','Code module only normalizes email addresses. There is no broader service or management layer.', ['email_normalization','enhanced_utils','FinalManager','phase_one_core']),
('n09','core','preserve','Domain invoices have Draft, Approved and Paid states. A type represents an invoice in Draft state.', ['DraftInvoice','DevelopmentInvoice','MvpInvoice','InvoiceWithNoState']),
('n10','core','preserve','HTTP/2 is the actual wire protocol implemented by this client.', ['Http2Client','NewHttpClient','HttpClientFinal','HttpClientNext']),
('n11','core','preserve','A migration system requires ordered immutable filenames. Existing migration is 0042_add_invoice_currency.sql.', ['Preserve that filename','Rename to final_schema.sql','Remove its numeric prefix','Rename to new_invoice.sql']),
('n12','core','preserve','An external API contract fixes the JSON key new_status. You are changing only its value calculation.', ['Keep new_status','Rename it to current_status','Delete the key','Replace it with phase2_status']),
('n13','core','preserve','A compiler has named lexical and parsing stages, independent of project milestones.', ['lexical_stage','mvp_stage','phase_two_work','final_stage_impl']),
('n14','core','preserve','Release archive must identify the product and released version 2.3.0.', ['widget-2.3.0.tar.gz','widget-final.tar.gz','widget-new.tar.gz','widget-enhanced.tar.gz']),
('n15','core','preserve','A historical design note documents the second delivery milestone; it is not an implementation module.', ['milestone-2-decisions.md','streaming_parser.py','current_final.md','hide-all-milestone-references.md']),
('n16','core','preserve','The NewOrder event is the stable domain event for newly placed orders, not newly written code.', ['Preserve NewOrder','Rename to FinalOrder','Rename to PhaseOneOrder','Remove New from all identifiers']),
('n17','core','scope','A task changes a private helper and its callers. An unrelated public legacy_v1 API is stable.', ['Rename the helper and update callers; leave unrelated API alone','Rename every legacy identifier','Change API spelling without updating users','Keep a duplicate helper solely for the old private name']),
('n18','core','scope','Renaming a private function that three tests import. No compatibility requirement exists.', ['Update function, callers and test imports together','Rename its definition only','Keep two duplicate implementations','Rename unrelated modules too']),
('n19','core','avoid','Repository calls the business concept claimant. Name a new claimant lookup function consistently.', ['find_claimant','find_customer_person','find_subject_entity','find_new_party']),
('n20','core','preserve','Repository uses Rust raw identifier r#type to interoperate with a required external field type.', ['Preserve the required field mapping','Rename external type to kind without migration','Remove the field','Call it enhanced_type']),
('n21','core','avoid','A C# method calculates a refund total; project methods use PascalCase.', ['CalculateRefundTotal','calculate_refund_total','DoStuffV2','FinalRefundMethod']),
('n22','core','avoid','A file contains a temporary interoperability workaround for a vendor timestamp format; name by responsibility.', ['vendor_timestamp_adapter.py','temporary_fix.py','hotfix_final.py','phase5_patch.py']),
('n23','core','preserve','A rolling upgrade must support both version 1 and version 2 of an external event schema.', ['EventV1 and EventV2','OldEvent and NewEvent','BasicEvent and EnhancedEvent','FinalEvent and FinalFinalEvent']),
('n24','core','avoid','A method validates syntax only; it does not authenticate identity or establish trust.', ['validate_syntax','authenticate_identity','guarantee_trust','secure_everything']),
('n25','validation','avoid','F# module computes balanced ledger postings. Foundation package F03 delivered it.', ['PostingBalance','F03Core','FoundationFinal','NewAccounting']),
('n26','validation','avoid','A queue introduced in stage B stores pending thumbnail jobs. Name its private field.', ['pending_thumbnail_jobs','stage_b_queue','next_queue','super_queue']),
('n27','validation','avoid','A Python module shares JSON decoding logic across callers. It is the third rewrite, not a third wire format.', ['json_decoding.py','decoder_v3.py','latest_decoder.py','mature_decoder.py']),
('n28','validation','avoid','A test fixture supplies an expired session. It was created by a coding agent while completing step 6.', ['expired_session','agent_generated_fixture','step6_fixture','new_session_fixture']),
('n29','validation','preserve','A UI button creates a new invoice; NewInvoiceButton describes its user-facing action.', ['NewInvoiceButton is meaningful here','Ban New from its identifier','Call it FinalInvoiceButton','Call it PhaseOneButton']),
('n30','validation','preserve','A domain object is in a temporary reservation state that expires after ten minutes.', ['TemporaryReservation','MvpReservation','FinalReservation','ReservationV2']),
('n31','validation','preserve','A test for a two-stage commit protocol must refer to its prepare stage.', ['test_prepare_stage_rejects_missing_participant','test_phase2_work_complete','test_final_engine','test_latest_commit']),
('n32','validation','preserve','A database column legacy_id is an intentionally preserved identifier used by existing consumers.', ['Keep the established column contract','Rename the column silently','Remove its values','Replace it with a new product-phase label']),
('n33','validation','scope','A method is externally published as parse_v2. Only whitespace handling changes in this task.', ['Preserve parse_v2 and change its implementation','Rename it parse to purge versions','Delete the existing method','Add parse_final and remove parse_v2']),
('n34','validation','scope','Only a new function is requested. An unrelated old file has a poor internal name but no relevance to the task.', ['Do not expand this task into unrelated renaming','Rename the entire repository','Move all old files','Delete the unrelated file']),
('n35','validation','avoid','A private class is labelled ProductionReadyManager only because the product just reached general availability. It only serializes invoices.', ['InvoiceSerializer','ProductionReadyManager','GACore','FinalManager']),
('n36','validation','avoid','The project has synchronous and asynchronous implementations. Name the asynchronous one by the real distinction.', ['AsyncInvoiceWriter','InvoiceWriterV2','NewInvoiceWriter','NextWriter']),
('n37','validation','preserve','A mathematical algorithm has a phase1 objective as part of its defined two-phase optimization method.', ['phase1_objective','new_objective','enhanced_objective','objective_final']),
('n38','validation','preserve','A CLI option --draft selects draft documents; this is document state, not product maturity.', ['Keep --draft','Rename it --mvp','Remove all lifecycle vocabulary','Rename it --latest']),
('n39','validation','avoid','A directory contains transport diagnostics. The planning board calls its package complete-diagnostics-phase.', ['transport_diagnostics','complete_diagnostics_phase','enhanced_diagnostics','phase_final']),
('n40','validation','avoid','A local result contains elapsed seconds, not an implementation revision. Project uses snake_case.', ['elapsed_seconds','elapsed_v2','FinalElapsed','new_value']),
]
GEN = [
{'id':'g01','split':'core','kind':'avoid','task':'Create a small private Python module with one function converting seconds to milliseconds by multiplying by 1000. The implementation work is labelled phase4 and MVP. Choose the module filename, function name and parameter name. Plain Python; no annotations or imports.', 'good':{'path':'time_units.py','code':'def seconds_to_milliseconds(seconds):\n    return seconds * 1000\n'}},
{'id':'g02','split':'core','kind':'avoid','task':'Create one private Python function returning the sum of supplied invoice amounts using sum(). This is the third implementation rewrite, not a new data format. The project uses snake_case. Choose a filename and function name. No annotations or imports.', 'good':{'path':'invoice_totals.py','code':'def total_invoice_amounts(amounts):\n    return sum(amounts)\n'}},
{'id':'g03','split':'core','kind':'preserve','task':'Create a Python class for an invoice in the domain Draft state. It has an __init__ method taking amount and assigning self.amount. Choose a descriptive class name and filename. The product itself is production software. No imports or annotations.', 'good':{'path':'invoices.py','code':'class DraftInvoice:\n    def __init__(self, amount):\n        self.amount = amount\n'}},
{'id':'g04','split':'core','kind':'preserve','task':'Update api.py, whose public exported function is exactly parse_v2(text). Return int(text.strip()). Existing clients require this spelling and signature. This is not a product release label. Return the complete single-function file. No imports or annotations.', 'good':{'path':'api.py','code':'def parse_v2(text):\n    return int(text.strip())\n'}},
{'id':'g05','split':'validation','kind':'avoid','task':'Add a pytest test for normalize_email() in an existing project. The test must assert normalize_email("A@EXAMPLE.COM") == "a@example.com". Imports are supplied by the surrounding module, so return only a test function in a suitable test filename. Its work item was milestone7; it is a regression from ticket UX481.', 'good':{'path':'test_email_normalization.py','code':'def test_normalizes_email_case():\n    assert normalize_email("A@EXAMPLE.COM") == "a@example.com"\n'}},
{'id':'g06','split':'validation','kind':'preserve','task':'Return config.py containing one DEFAULTS dictionary. Preserve the existing contract key connect_timeout_ms with value 2500. Add a boolean key enabling audit logging, with value True. This feature is called stage6 in the delivery plan; choose the new key by meaning. No other code.', 'good':{'path':'config.py','code':'DEFAULTS = {"connect_timeout_ms": 2500, "audit_logging_enabled": True}\n'}},
{'id':'g07','split':'validation','kind':'scope','task':'Improve the private helper name and its call site in totals.py, without changing the public calculate_invoice name, the unrelated LEGACY_API_PATH constant, or behavior. Do not retain a redundant alias. Current code:\nLEGACY_API_PATH = "/v1"\ndef phase2_total(amounts):\n    return sum(amounts)\ndef calculate_invoice(amounts):\n    return phase2_total(amounts)\nReturn the complete file; no imports or annotations.', 'good':{'path':'totals.py','code':'LEGACY_API_PATH = "/v1"\ndef total_amounts(amounts):\n    return sum(amounts)\ndef calculate_invoice(amounts):\n    return total_amounts(amounts)\n'}},
{'id':'g08','split':'validation','kind':'preserve','task':'Update compiler.py containing the externally imported function parse_stage(tokens). It is an intrinsic stage of a compiler algorithm, not a delivery phase. Its behavior must return list(tokens). Preserve its name and signature. No imports or annotations.', 'good':{'path':'compiler.py','code':'def parse_stage(tokens):\n    return list(tokens)\n'}},
]
PROTOCOL = {
 'design':'Frozen synthetic naming-instruction comparison, not a production agent field trial.',
 'conditions':CONDITIONS,'models':MODELS,'seeds':SEEDS,
 'cases':CASES,'generation':[{k:v for k,v in x.items() if k!='good'} for x in GEN],
 'blinding':'Models receive one condition, no candidate identities, alternatives, answer keys or prior conversations. The deterministic scorer accepts case plus response, never condition. The author designed both candidates and cases; no double-blind human evaluation is claimed.',
 'randomization':'Within each model and replicate, decision cases and option positions are permuted identically across conditions. Generated-code task order is independently shuffled using the same paired seed. Separate fresh conversations for all code tasks.',
 'selection':'Using core cases only, choose non-control condition with fewest total case failures across both models and seeds. Exact ties: fewer words, then lexicographic condition ID. Report validation unchanged; do not retune after seeing it.',
 'units':'40 decisions are batched per model-condition-replicate; their outcomes are dependent. Each of 8 code tasks is a fresh completion. Do not treat all decisions as independent subjects.',
 'scoring':'Prewritten exact answer keys for shuffled decision options. Code: JSON format, AST structure and task-specific name/contract checks; no generated code execution. This is not full semantic verification.',
 'analysis':'Report counts by model, condition, split and case kind; paired differences. No significance or universal optimality claim. Two quantized small models from one model family limit transfer to stronger coding agents.',
 'failure_policy':'Malformed or truncated model output counts as task failure; HTTP/runtime failures are recorded separately and do not count as semantic failures. One transport retry only. No selective semantic reruns.',
 'temperature':0.2,'top_p':0.9,'max_decision_tokens':160,'max_code_tokens':400,
 'runtime_release':'b10343',
}

def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def sha_file(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def words(text):
    return len(text.split())

def request_json(url, payload=None, timeout=180):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers={'User-Agent':'naming-guidance-evaluation','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.load(r)

def download(url,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers={'User-Agent':'naming-guidance-evaluation'})
    with urllib.request.urlopen(req,timeout=180) as r, path.open('wb') as f:
        shutil.copyfileobj(r,f,1024*1024)

def parse_output(text):
    try:
        return json.loads(text)
    except (ValueError,TypeError):
        return None

# The scorer has no access to candidate text or identity. Name rejection is
# task-specific; legitimate uses in n09-n16 and g03/g04/g08 are preserved.
def score_code(case, output):
    if not isinstance(output,dict) or not isinstance(output.get('code'),str) or not isinstance(output.get('path'),str):
        return {'passed':False,'checks':{'format':False}}
    try:
        tree=ast.parse(output['code'])
    except SyntaxError:
        return {'passed':False,'checks':{'syntax':False}}
    nodes=list(ast.walk(tree))
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef)]
    identifiers=[n.name for n in nodes if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
    identifiers += [n.id for n in nodes if isinstance(n,ast.Name)]
    identifiers += [n.arg for n in nodes if isinstance(n,ast.arg)]
    surface=' '.join(identifiers+[output['path']]).lower()
    checks={'syntax':True,'plain_code':not any(isinstance(n,(ast.Import,ast.ImportFrom,ast.AsyncFunctionDef)) for n in nodes)}
    cid=case['id']
    def has(fragment): return fragment in surface
    def calls(name): return any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name for n in nodes)
    def contract(name,args):
        fs=[f for f in funcs if f.name==name]
        return len(fs)==1 and [a.arg for a in fs[0].args.args]==args
    def value_assignment(name,value):
        return any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets) and isinstance(n.value,ast.Constant) and n.value.value==value for n in tree.body)
    if cid in {'g01','g02','g05','g07'}:
        forbidden={'g01':r'phase[_-]?4|mvp','g02':r'(?:_|\b)v3\b|(?:_|\b)new(?:_|\b)|third[_-]?rewrite|final','g05':r'milestone[_-]?7|ux[_-]?481','g07':r'phase[_-]?2'}[cid]
        checks['no_work_label']=re.search(forbidden,surface) is None
    if cid=='g01':
        checks.update(one_function=len(funcs)==1, descriptive=(has('second') and (has('milli') or has('_ms'))), operation=any(isinstance(n,ast.BinOp) and isinstance(n.op,ast.Mult) and any(isinstance(x,ast.Constant) and x.value==1000 for x in [n.left,n.right]) for n in nodes))
    elif cid=='g02':
        checks.update(one_function=len(funcs)==1, descriptive=bool(funcs) and bool(re.search(r'sum|total',funcs[0].name)), operation=calls('sum'))
    elif cid=='g03':
        checks.update(one_class=len(classes)==1, domain_state=bool(classes) and 'Draft' in classes[0].name and 'Invoice' in classes[0].name, initializer=any(isinstance(n,ast.FunctionDef) and n.name=='__init__' for n in nodes), amount_attribute=any(isinstance(n,ast.Attribute) and n.attr=='amount' for n in nodes))
    elif cid=='g04':
        checks.update(path=output['path']=='api.py',contract=contract('parse_v2',['text']),conversion=calls('int'),strip=any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='strip' for n in nodes),one_function=len(funcs)==1)
    elif cid=='g05':
        checks.update(one_test=len(funcs)==1 and funcs[0].name.startswith('test_'), behavior_name=bool(funcs) and bool(re.search(r'normal|lower|case',funcs[0].name)), assertion=any(isinstance(n,ast.Assert) for n in nodes), subject_call=calls('normalize_email'), examples=all(any(isinstance(n,ast.Constant) and n.value==v for n in nodes) for v in ['A@EXAMPLE.COM','a@example.com']))
    elif cid=='g06':
        ds=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEFAULTS' for t in n.targets) and isinstance(n.value,ast.Dict)]
        entries={}
        if len(ds)==1:
            for k,v in zip(ds[0].value.keys,ds[0].value.values):
                if isinstance(k,ast.Constant) and isinstance(v,ast.Constant): entries[k.value]=v.value
        checks.update(path=output['path']=='config.py',contract=entries.get('connect_timeout_ms')==2500,audit=any(isinstance(k,str) and 'audit' in k.lower() and 'log' in k.lower() and v is True for k,v in entries.items()),no_work_label=not any('stage6' in str(k).lower().replace('_','') for k in entries),only_two_keys=len(entries)==2)
    elif cid=='g07':
        helpers=[f for f in funcs if f.name!='calculate_invoice']
        checks.update(path=output['path']=='totals.py',public_contract=contract('calculate_invoice',['amounts']),unrelated_preserved=value_assignment('LEGACY_API_PATH','/v1'),one_helper=len(helpers)==1,descriptive=bool(helpers) and bool(re.search(r'sum|total',helpers[0].name)),updated_reference=bool(helpers) and calls(helpers[0].name),sum_operation=calls('sum'),no_alias=not any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='phase2_total' for t in n.targets) for n in nodes))
    elif cid=='g08':
        checks.update(path=output['path']=='compiler.py',contract=contract('parse_stage',['tokens']),operation=calls('list'),one_function=len(funcs)==1)
    return {'passed':all(checks.values()),'checks':checks}

def decision_prompt(seed):
    rng=random.Random(seed)
    items=list(CASES)
    rng.shuffle(items)
    lines=[]; key=[]
    for i,case in enumerate(items,1):
        cid,split,kind,context,choices=case
        pairs=list(enumerate(choices)); rng.shuffle(pairs)
        answer='ABCD'[next(j for j,(index,_) in enumerate(pairs) if index==0)]
        lines.append(f'{i}. {context}\n'+'; '.join(f'{"ABCD"[j]}: {value}' for j,(_,value) in enumerate(pairs)))
        key.append({'case':cid,'split':split,'kind':kind,'answer':answer})
    text='Select the best naming decision for each independent task below. Return only JSON {"choices":"..."}, with exactly one uppercase A/B/C/D letter per task in order, without separators.\n\n'+'\n\n'.join(lines)
    return text,key

def score_decisions(key,output):
    answers=output.get('choices','') if isinstance(output,dict) else ''
    valid=isinstance(answers,str) and len(answers)==len(key) and set(answers)<=set('ABCD')
    return [{**k,'observed':answers[i] if valid else None,'passed':valid and answers[i]==k['answer'],'format':valid} for i,k in enumerate(key)]

def self_test():
    count=0
    for seed in SEEDS:
        text,key=decision_prompt(seed)
        assert len(key)==40 and len({x['case'] for x in key})==40
        assert all(x['passed'] for x in score_decisions(key,{'choices':''.join(x['answer'] for x in key)}));count+=40
        assert not any(x['passed'] for x in score_decisions(key,{'choices':''}));count+=40
        wrong=''.join('B' if x['answer']=='A' else 'A' for x in key)
        assert not any(x['passed'] for x in score_decisions(key,{'choices':wrong}));count+=40
        assert decision_prompt(seed)==decision_prompt(seed);count+=1
    for c in GEN:
        assert score_code(c,c['good'])['passed'], (c['id'],score_code(c,c['good']));count+=1
        for bad in [None,{}, {'path':'x','code':'def :'}, {'path':'x','code':'pass'}]:
            assert not score_code(c,bad)['passed'],c['id'];count+=1
    mutations={
      'g01':('seconds_to_milliseconds','phase4_seconds_to_milliseconds'),
      'g02':('total_invoice_amounts','total_invoice_amounts_v3'),
      'g03':('DraftInvoice','Invoice'),
      'g04':('parse_v2','parse'),
      'g05':('test_normalizes_email_case','test_milestone7_normalizes_email_case'),
      'g06':('audit_logging_enabled','stage6'),
      'g07':('return total_amounts(amounts)','return missing_helper(amounts)'),
      'g08':('parse_stage','parse_final'),
    }
    for c in GEN:
        before,after=mutations[c['id']]
        bad={**c['good'],'code':c['good']['code'].replace(before,after)}
        assert not score_code(c,bad)['passed'],(c['id'],score_code(c,bad));count+=1
        comment={**c['good'],'code':'# Historical issue phase4 MVP milestone7 UX481\n'+c['good']['code']}
        assert score_code(c,comment)['passed'];count+=1
    assert set(CONDITIONS)=={'K7','M2','R9','T4'}
    print(json.dumps({'self_test_assertions':count,'candidate_words':{k:words(v) for k,v in CONDITIONS.items()},'passed':True}))

def bootstrap(model_key,out):
    cache=Path('runtime')/model_key; cache.mkdir(parents=True,exist_ok=True)
    release=request_json('https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/'+PROTOCOL['runtime_release'])
    assets=[a for a in release['assets'] if a['name'].endswith('bin-ubuntu-x64.tar.gz')]
    if len(assets)!=1:
        raise RuntimeError('Expected one CPU binary archive: '+str([a['name'] for a in release['assets']]))
    asset=assets[0]; archive=cache/'runtime.tar.gz'
    download(asset['browser_download_url'],archive)
    archive_sha=sha_file(archive)
    if asset.get('digest') and asset['digest']!='sha256:'+archive_sha:
        raise RuntimeError('Runtime release checksum mismatch')
    with tarfile.open(archive) as tar:
        tar.extractall(cache/'bin',filter='data')
    servers=list((cache/'bin').rglob('llama-server'))
    if len(servers)!=1: raise RuntimeError('No unique llama-server executable')
    repo=MODELS[model_key]; meta=request_json('https://huggingface.co/api/models/'+repo)
    filenames=[s['rfilename'] for s in meta['siblings'] if s['rfilename'].lower().endswith('q4_k_m.gguf')]
    if len(filenames)!=1: raise RuntimeError('No unique Q4_K_M model file: '+repr(filenames))
    filename=filenames[0]; revision=meta['sha']; modelpath=cache/'model.gguf'
    download(f'https://huggingface.co/{repo}/resolve/{revision}/{filename}',modelpath)
    metadata={'model_repo':repo,'model_revision':revision,'model_file':filename,'model_sha256':sha_file(modelpath),'runtime_tag':release['tag_name'],'runtime_asset':asset['name'],'runtime_sha256':archive_sha,'python':sys.version,'cpus':os.cpu_count(),'github_sha':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID')}
    write_json(out/'runtime.json',metadata)
    server=servers[0].resolve()
    env=dict(os.environ);env['LD_LIBRARY_PATH']=str(server.parent)+':'+env.get('LD_LIBRARY_PATH','')
    log=(out/'server.log').open('w')
    command=[str(server),'-m',str(modelpath.resolve()),'--host','127.0.0.1','--port','8765','-c','8192','-t','4','--parallel','1','--jinja','--no-warmup']
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env)
    for _ in range(120):
        if process.poll() is not None: raise RuntimeError('Model server exited; see server.log')
        try:
            request_json('http://127.0.0.1:8765/health',timeout=2)
            return process,log
        except Exception:
            time.sleep(1)
    process.terminate();raise RuntimeError('Model server startup timeout')

def completion(system,user,seed,max_tokens):
    payload={'messages':[{'role':'system','content':system},{'role':'user','content':user}],'temperature':0.2,'top_p':0.9,'seed':seed,'max_tokens':max_tokens,'response_format':{'type':'json_object'},'cache_prompt':False}
    started=time.time()
    for attempt in range(2):
        try:
            response=request_json('http://127.0.0.1:8765/v1/chat/completions',payload,timeout=300)
            return payload,response,time.time()-started
        except Exception:
            if attempt: raise
            time.sleep(2)
    raise AssertionError('unreachable')

def worker(model,condition):
    out=Path('results')/(model+'-'+condition);out.mkdir(parents=True,exist_ok=True)
    write_json(out/'protocol.json',PROTOCOL)
    write_json(out/'manifest.json',{'protocol_sha256':sha_file(out/'protocol.json'),'script_sha256':sha_file(Path(__file__)),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'model':model,'condition':condition})
    self_test()
    process=None;log=None;records=[]
    try:
        process,log=bootstrap(model,out)
        system='You are a coding assistant working in a repository. Follow the repository guidance below. Return only the requested JSON.\n\n'+CONDITIONS[condition]
        for seed in SEEDS:
            prompt,key=decision_prompt(seed)
            payload,response,seconds=completion(system,prompt,seed,160)
            output=parse_output(response['choices'][0]['message']['content'])
            write_json(out/f'decisions-{seed}.json',{'request':payload,'response':response,'seconds':seconds,'key':key})
            scores=score_decisions(key,output)
            records += [{'model':model,'condition':condition,'seed':seed,'task_type':'decision',**s} for s in scores]
            print(json.dumps({'model':model,'condition':condition,'seed':seed,'decision_passes':sum(s['passed'] for s in scores),'decision_total':len(scores),'seconds':seconds}),flush=True)
            tasks=list(GEN);random.Random(seed+1).shuffle(tasks)
            for task in tasks:
                prompt=task['task']+'\nReturn only JSON with two string fields: path (the module filename) and code (complete Python source). Do not include Markdown fences.'
                payload,response,seconds=completion(system,prompt,seed,400)
                output=parse_output(response['choices'][0]['message']['content'])
                score=score_code(task,output)
                write_json(out/f'{task["id"]}-{seed}.json',{'request':payload,'response':response,'seconds':seconds,'score':score})
                records.append({'model':model,'condition':condition,'seed':seed,'task_type':'code','case':task['id'],'split':task['split'],'kind':task['kind'],**score})
                print(json.dumps({'model':model,'condition':condition,'seed':seed,'case':task['id'],**score,'seconds':seconds}),flush=True)
                write_json(out/'scores.json',records)
        write_json(out/'status.json',{'complete':True,'observations':len(records),'completions':18})
    except Exception as error:
        write_json(out/'status.json',{'complete':False,'error':str(error),'observations':len(records)})
        raise
    finally:
        write_json(out/'scores.json',records)
        if process:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill()
        if log: log.close()

def aggregate(root):
    all_records=[];statuses=[]
    for p in sorted(root.rglob('scores.json')): all_records+=json.loads(p.read_text())
    for p in sorted(root.rglob('status.json')): statuses.append(json.loads(p.read_text()))
    complete=len(statuses)==8 and all(s['complete'] for s in statuses) and len(all_records)==768
    summary={'complete':complete,'observations':len(all_records),'conditions':{}}
    for condition in CONDITIONS:
        d={'words':words(CONDITIONS[condition])}
        for split in ['core','validation']:
            rs=[r for r in all_records if r['condition']==condition and r['split']==split]
            d[split]={'passed':sum(r['passed'] for r in rs),'total':len(rs)}
        for model in MODELS:
            rs=[r for r in all_records if r['condition']==condition and r['model']==model]
            d[model]={'passed':sum(r['passed'] for r in rs),'total':len(rs)}
        d['failures']=[{'model':r['model'],'seed':r['seed'],'case':r['case'],'checks':r.get('checks'),'observed':r.get('observed'),'answer':r.get('answer')} for r in all_records if r['condition']==condition and not r['passed']]
        summary['conditions'][condition]=d
    if complete:
        ranked=sorted((k for k in CONDITIONS if k!='T4'),key=lambda k:(summary['conditions'][k]['core']['total']-summary['conditions'][k]['core']['passed'],words(CONDITIONS[k]),k))
        summary['selected_on_core']=ranked[0]
        summary['selection_order']=ranked
        (root/'selected-guidance.md').write_text(CONDITIONS[ranked[0]]+'\n')
    write_json(root/'summary.json',summary)
    write_json(root/'all-scores.json',all_records)
    print(json.dumps(summary,indent=2))
    return complete

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--worker',nargs=2,metavar=('MODEL','CONDITION'))
    parser.add_argument('--aggregate',type=Path)
    args=parser.parse_args()
    if args.self_test: self_test()
    elif args.worker:
        model,condition=args.worker
        if model not in MODELS or condition not in CONDITIONS: parser.error('Unknown model or condition')
        worker(model,condition)
    elif args.aggregate:
        if not aggregate(args.aggregate): raise SystemExit('Incomplete experiment: no winner declared')
    else: parser.error('Choose --self-test, --worker or --aggregate')

if __name__=='__main__': main()
