"""Verify and archive completed independent confirmation; no API or rollouts."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from archive import HEAVY,assert_no_secret,digest,read,write


def load_wrapper():
    path=ROOT/'experiments/online_llm_confirmation/batch.py'
    spec=importlib.util.spec_from_file_location('confirmation_archive_frozen_wrapper',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def hash_stream(stream):
    value=hashlib.sha256()
    while True:
        chunk=stream.read(1024*1024)
        if not chunk:
            return value.hexdigest()
        value.update(chunk)


def archive(source,export):
    if export.exists():
        raise RuntimeError('Refuse archive overwrite')
    if not os.environ.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('Configured credential required for absence audit; never logged or sent')
    completion=read(source/'completed.json');summary=read(source/'summary.json')
    frozen=read(source/'freeze.json');manifest=read(source/'manifest.json')
    assert completion['status']=='completed' and completion['phase']=='independent_confirmation'
    assert completion['episodes']==1000 and completion['node_periods']==600000
    assert digest(source/'summary.json')==completion['summary_sha256']
    assert summary['complete'] and summary['episodes']==1000 and summary['node_periods']==600000
    assert summary['primary']==completion['primary'] and summary['api_requests']==completion['api_requests']
    assert manifest['phase']=='independent_confirmation' and manifest['all_fixed_cases_retained']
    assert frozen['frozen_before_confirmation_input_generation']
    assert not (source/'failed.json').exists() and read(source/'progress.json')['status']=='completed'
    os.environ['DEEPSEEK_MODEL']=frozen['api_model']
    wrapper=load_wrapper()
    wrapper.check_frozen(source,Path(frozen['library_path']))
    print('FROZEN_CONTRACTS_VERIFIED all5models inputs sources runtime',flush=True)
    # The existing analysis recomputes all25 child audits and every summary field.
    # Intercept only its final write in memory, preserving original result bytes.
    original_write=wrapper.write;original_audit=wrapper.audit_run
    captured=[];audited=[]
    def capture(path,value):
        assert path==source/'summary.json','Unexpected source mutation attempt'
        captured.append(value)
    def audited_run(*args,**kwargs):
        value=original_audit(*args,**kwargs)
        audited.append(str(args[0]))
        print('CHILD_AUDITED',len(audited),'/25',Path(args[0]).name,flush=True)
        return value
    wrapper.write=capture;wrapper.audit_run=audited_run
    try:
        recomputed=wrapper.analyze_complete(source,manifest)
    finally:
        wrapper.write=original_write;wrapper.audit_run=original_audit
    assert len(audited)==25 and len(captured)==1 and captured[0]==recomputed==summary
    assert len(summary['fitness'])==1000 and sum(a['raw_rows'] for a in summary['audits'])==600000
    assert len(read(source/'progress.json')['completed'])==25
    for entry in read(source/'progress.json')['completed']:
        child=source/Path(entry['path']).name
        assert digest(child/'protocol.json')==entry['protocol_sha256']
    credential_audit=assert_no_secret(source)
    print('SUMMARY_AND_CREDENTIAL_ABSENCE_VERIFIED',summary['api_requests'],'requests',flush=True)
    # Refuse model weight payloads, retain every remaining result/source/log file.
    export.mkdir(parents=True)
    originals={};copied={};excluded=[];compressed_count=0
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        rel=path.relative_to(source)
        if any(part in ('__pycache__','models','final_models') for part in rel.parts) or path.suffix.lower() in ('.pt','.pth','.ckpt'):
            excluded.append(str(rel));continue
        original_sha=digest(path);originals[str(rel)]=original_sha
        target=export/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if path.name in HEAVY:
            target=target.with_name(target.name+'.gz')
            with path.open('rb') as src,target.open('xb') as raw:
                with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as dst:
                    shutil.copyfileobj(src,dst)
            with gzip.open(target,'rb') as stream:
                assert hash_stream(stream)==original_sha,('lossless_compression',str(rel))
            compressed_count+=1
            if compressed_count%20==0:
                print('COMPRESSED_VERIFIED',compressed_count,'/100',flush=True)
        else:
            shutil.copy2(path,target);assert digest(target)==original_sha
        assert digest(path)==original_sha,('source_mutated_during_archive',str(rel))
        copied[str(target.relative_to(export))]=digest(target)
    assert compressed_count==100
    driver=export/'archive_driver.py';shutil.copy2(Path(__file__),driver)
    copied['archive_driver.py']=digest(driver)
    wrapper.check_frozen(source,Path(frozen['library_path']))
    assert digest(source/'summary.json')==completion['summary_sha256']
    assert assert_no_secret(export)=='Configured credential absent from all text artifacts'
    verification=dict(status='verified',phase='independent_confirmation',development_only=False,
        episodes=1000,node_periods=600000,child_audits=25,compressed_raw_files=100,
        raw_cost_backlog_reports_normal_actions_API_budgets_selector_thresholds='passed',
        all_summary_fields_recomputed_and_equal=True,primary_and_secondary_bootstrap_recomputed=True,
        per_model_adverse_pairs_realized_shock_strata_and_event_metrics='passed',
        source_input_library_model_metadata_runtime_and_snapshot_hashes='passed',
        summary_sha256=completion['summary_sha256'],manifest_sha256=digest(source/'manifest.json'),
        freeze_sha256=digest(source/'freeze.json'),original_completed_sha256=digest(source/'completed.json'),
        api_requests=summary['api_requests'],api_failures=summary['api_failures'],usage=summary['usage'],
        runtime_failures=summary['runtime_failures'],currency_cost=None,
        currency_cost_note='Token usage retained; billing currency cost not independently obtained',
        credential_audit=credential_audit,credential_absent_from_archive_plain_text=True,
        original_outputs_preserved=True,model_weights_not_copied=True,excluded_files=excluded,
        archive_driver_sha256=digest(Path(__file__)),archive_driver_run_no_API_no_rollouts=True,
        raw_module_tag_note=summary['raw_module_tag_note'])
    write(export/'verification.json',verification)
    copied['verification.json']=digest(export/'verification.json')
    write(export/'export_hashes.json',dict(original_sha256=originals,archive_sha256=copied))
    # Verify every retained archive hash once more after manifest creation.
    for name,expected in copied.items():
        assert digest(export/name)==expected,('archive_hash',name)
    print('CONFIRMATION_ARCHIVED_VERIFIED',str(export),'1000 episodes600000 rows',
          summary['api_requests'],'requests',summary['usage']['total_tokens'],'tokens',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'results/online_llm/confirmation_v1')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/artifacts/online_llm_confirmation_v1')
    args=parser.parse_args();archive(args.source.resolve(),args.output.resolve())
