"""Original clients, isolated boolean NAME compatibility, and normalization audit."""
import ast
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import tokenize

ROOT=Path(__file__).resolve().parents[2]

def load_module(name,path):
    if name in sys.modules:
        module=sys.modules[name]
        if Path(module.__file__).resolve()!=path.resolve():
            raise RuntimeError('Module alias collision: '+name)
        return module
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

# Original run establishes the original shadow import before these aliases load.
BASELINE=load_module('case_only_baseline_client',ROOT/'experiments/online_llm/client.py')
COMPAT=load_module('case_only_compat_client',ROOT/'experiments/online_llm/client.py')
V1Client=BASELINE.Client
CaseClient=COMPAT.Client
FatalAPIError=BASELINE.FatalAPIError
write=BASELINE.write
ORIGINAL_COMPILE=BASELINE.compile_rule
ORIGINAL_PARSE=ORIGINAL_COMPILE.__globals__['parse_expression']
AUDIT=[]
AUDIT_PATH=None
AUDIT_IDENTITY={}
AUDIT_CONTEXT=None


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def normalize_expression(text):
    # Enforce original input limits before normalization can remove AST Name/Load.
    if not isinstance(text,str) or len(text)>300:
        raise ValueError('expression must be a string of at most 300 characters')
    original_tree=ast.parse(text,mode='eval').body
    if len(list(ast.walk(original_tree)))>120:
        raise ValueError('expression is too large')
    lines=text.splitlines(keepends=True)
    offsets=[0]
    for line in lines:
        offsets.append(offsets[-1]+len(line))
    edits=[]
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type==tokenize.NAME and token.string in ('true','false'):
            start=offsets[token.start[0]-1]+token.start[1]
            end=offsets[token.end[0]-1]+token.end[1]
            edits.append(dict(start=start,end=end,before=token.string,after=token.string.capitalize()))
    repaired=text
    for edit in reversed(edits):
        repaired=repaired[:edit['start']]+edit['after']+repaired[edit['end']:]
    return repaired,edits


def normalize_candidate(value,changes=None):
    normalized=copy.deepcopy(value)
    if changes is None:
        changes=[]
    # Preserve original compile_rule structural errors and permissive candidate keys.
    if not isinstance(normalized,dict) or not isinstance(normalized.get('rules'),list) or not 1<=len(normalized['rules'])<=4:
        raise ValueError('expected one to four rules')
    for index,entry in enumerate(normalized['rules']):
        if not isinstance(entry,dict) or set(entry)!={'when','delta'}:
            raise ValueError('rule must contain when and delta only')
        for field in ('when','delta'):
            original=entry[field];repaired,edits=normalize_expression(original)
            entry[field]=repaired
            if edits:
                changes.append(dict(rule_index=index,field=field,original=original,repaired=repaired,edits=edits))
            # Validate in original rule/field order, retaining the first noncase
            # error and its exact repair-request message.
            ORIGINAL_PARSE(repaired)
    return normalized,changes


def compile_rule(value):
    started=time.perf_counter()
    identity=AUDIT_CONTEXT() if AUDIT_CONTEXT is not None else AUDIT_IDENTITY
    record=dict(**identity,index=len(AUDIT),raw_candidate_sha256=canonical_hash(value),changes=[],status='started')
    try:
        normalized,changes=normalize_candidate(value,record['changes'])
        record.update(changes=changes,normalized_candidate_sha256=canonical_hash(normalized),
                      normalization_used=bool(changes),replaced_tokens=sum(len(c['edits']) for c in changes))
        compiled=ORIGINAL_COMPILE(normalized)
        record.update(status='valid',compiled_ast=[[ast.dump(a),ast.dump(b)] for a,b in compiled])
        return compiled
    except Exception as exc:
        record.update(status='failed',failure_type=type(exc).__name__,failure=str(exc)[:400])
        raise
    finally:
        record['normalization_used']=bool(record['changes'])
        record['replaced_tokens']=sum(len(c['edits']) for c in record['changes'])
        record['seconds']=time.perf_counter()-started
        AUDIT.append(record)
        if AUDIT_PATH is not None:
            write(AUDIT_PATH,AUDIT)

# Only the compatibility module reference changes. No mutation of shadow/rules/baseline.
COMPAT.compile_rule=compile_rule

compatible_compile_rule=compile_rule
