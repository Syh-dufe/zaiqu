"""Reuse exact completed two-episode fixture after reference-table audit repair."""
import shutil
import runner
ROOT=runner.ROOT;core=runner.core
def main():
 source=ROOT/'results/sundial_multiscale_cost/no_api_fixture_v2';target=ROOT/'results/sundial_multiscale_cost/no_api_fixture_v3';assert not target.exists()
 files={str(p.relative_to(source)):core.digest(p) for p in source.rglob('*') if p.is_file()};shutil.copytree(source,target)
 for p,sha in files.items():assert core.digest(target/p)==sha
 protocol=core.read(target/'protocol.json');data=core.read(target/'demands.json');auditor=runner.module('multiscale_fixture_reauditor',runner.HERE/'audit.py')
 result=auditor.audit(runner,target,data,protocol['expected_parameter_sha256'],True)
 core.write(target/'preflight_passed.json',dict(**result,network_requests=0,fixed_old_replies_not_live_performance=True,raw_fixture_copied_without_simulation=True,original_files_sha256=files))
 print('MULTISCALE_DOUBLE_FIXTURE_REAUDIT_PASSED',flush=True)
if __name__=='__main__':main()
