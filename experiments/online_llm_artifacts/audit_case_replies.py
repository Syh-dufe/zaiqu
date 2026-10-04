"""Parse archived replies only; no API, environment rollout or model update."""
import ast
import collections
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/deepseek_refinement'))


def main():
    spec=importlib.util.spec_from_file_location('case_reply_audit_client',ROOT/'experiments/online_llm_case_only/client.py')
    client=importlib.util.module_from_spec(spec);sys.modules[spec.name]=client;spec.loader.exec_module(client)
    sources=[]
    for rel in ('online_llm/development_v1','online_llm/confirmation_v1',
                'online_llm_targeted/development_v2','online_llm_neutral/development_v3'):
        sources.extend(sorted((ROOT/'results'/rel).rglob('calls.json')))
    counts=collections.Counter();rescued=[];remaining=[];hashes={}
    for path in sources:
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        for index,call in enumerate(json.loads(path.read_text(encoding='utf-8-sig'))):
            response=call.get('response') or {}
            choices=response.get('choices') or []
            if not choices:
                counts['responses_without_candidate_document']+=1;continue
            try:
                document=json.loads(choices[0]['message']['content'])
                values=document['candidates']
                if not isinstance(values,list):raise ValueError('Not array')
            except (ValueError,KeyError,TypeError):
                counts['responses_without_candidate_document']+=1;continue
            for candidate_index,value in enumerate(values):
                saved=copy.deepcopy(value);before=after=None;original_error=fixed_error=None
                try:before=client.ORIGINAL_COMPILE(value)
                except Exception as error:original_error=str(error)
                try:after=client.compatible_compile_rule(value)
                except Exception as error:fixed_error=str(error)
                assert value==saved, 'Raw candidate modified'
                counts['candidate_documents']+=1
                identity=dict(file=str(path.relative_to(ROOT)),call_index=index,candidate_index=candidate_index,
                    group=call.get('group'),trace=call.get('trace'),event=call.get('event'),stage=call.get('stage'))
                if before is not None:
                    assert after is not None, ('Valid rule rejected',identity,fixed_error)
                    assert [[ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False)] for a,b in before]==[[ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False)] for a,b in after]
                    normalized,changes=client.normalize_candidate(value)
                    assert normalized==value and not changes
                    counts['originally_valid_AST_identical']+=1
                elif after is not None:
                    normalized,changes=client.normalize_candidate(value)
                    assert changes
                    assert client.ORIGINAL_COMPILE(normalized)
                    rescued.append(dict(identity,original_error=original_error,normalization_changes=changes))
                    counts['rescued_boolean_candidates']+=1
                else:
                    if not client.AUDIT[-1]['normalization_used']:
                        assert original_error==fixed_error, ('Unrelated error changed',identity,original_error,fixed_error)
                        counts['unrelated_error_message_identical']+=1
                    remaining.append(dict(identity,original_error=original_error,compatibility_error=fixed_error))
                    counts['still_invalid_candidates']+=1
    output=ROOT/'results/online_llm_case_only/archived_reply_audit_v2'
    output.mkdir(parents=True,exist_ok=False)
    result=dict(no_API=True,no_environment_rollout=True,no_performance_counterfactual=True,
        input_sha256=hashes,counts=dict(counts),rescued=rescued,remaining_invalid=remaining,
        raw_inputs_unchanged=True,all_originally_valid_AST_identical=True,
        scope='Candidate parsing audit includes recorded retries; candidate counts are not independent episodes or avoided HTTP counts')
    (output/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ARCHIVED_BOOLEAN_REPLY_AUDIT_OK',json.dumps(dict(counts)),flush=True)


if __name__=='__main__':
    main()
