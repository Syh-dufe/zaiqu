"""Audit and summarize all registered B/C crossed model/trajectory pairs."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'results/formal_evaluation'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def intervals(delta):
    rng = np.random.default_rng(20261221)
    models = rng.integers(0, 5, (20000, 5))
    traces = rng.integers(0, 20, (20000, 20))
    draws = delta[models[:, :, None], traces[:, None, :]].mean(axis=(1, 2))
    return {'ci95': np.quantile(draws, [.025, .975], axis=0).tolist(),
            'ci97p5': np.quantile(draws, [.0125, .9875], axis=0).tolist()}


def compare(reference, method):
    delta = method - reference
    ci = intervals(delta)
    return {'reference_means': reference.mean(axis=(0, 1)).tolist(),
            'method_means': method.mean(axis=(0, 1)).tolist(),
            'mean_delta': delta.mean(axis=(0, 1)).tolist(), **ci,
            'percent_reduction': (100 * (reference.mean(axis=(0, 1)) - method.mean(axis=(0, 1))) / reference.mean(axis=(0, 1))).tolist(),
            'per_seed_mean_delta': delta.mean(axis=1).tolist(),
            'counts': {metric: {'improved': int((delta[:, :, i] < -1e-9).sum()),
                                'tied': int((abs(delta[:, :, i]) <= 1e-9).sum()),
                                'worsened': int((delta[:, :, i] > 1e-9).sum())}
                       for i, metric in enumerate(('cost', 'backlog'))},
            'stronger_evidence': bool(np.all(delta.mean(axis=(0, 1)) < 0) and np.all(np.asarray(ci['ci97p5'])[1] < 0))}


def suite(name, seed, k, methods, export):
    raw = RAW / name
    progress = read(raw / 'progress.json')
    manifest = read(raw / 'manifest.json')
    assert progress['status'] == 'completed' and len(progress['completed']) == 5
    assert manifest['methods'] == methods and manifest['report_interval'] == k
    config = read(Path(manifest['training_directory']) / 'config.json')['config']
    assert config['seed'] == [seed]
    audit = read(Path(manifest['training_directory']) / 'completion_audit.json')
    assert manifest['model_parameter_sha256'] == audit['model_matches']['official_best']['sha256']
    values = {g: [] for g in methods}
    normal = {g: [] for g in methods}
    paired = []
    dest = export / name
    dest.mkdir()
    shutil.copy2(raw / 'manifest.json', dest / 'manifest.json')
    shutil.copy2(raw / 'progress.json', dest / 'progress.json')
    for number, entry in enumerate(progress['completed']):
        batch = raw / entry['name']
        done = read(batch / 'completed.json')
        assert done['episodes'] == 8 * len(methods) and done['rows'] == 4800 * len(methods)
        assert done['calls'] == done['training_updates'] == 0 and not done['runtime_failures']
        assert all(c['unchanged'] and c['before'] == manifest['model_parameter_sha256'] for c in done['parameter_checks'].values())
        expected_input = manifest['inputs'][number]
        assert digest(Path(expected_input['path'])) == expected_input['sha256']
        assert read(batch / 'input_source.json')['sha256'] == expected_input['sha256']
        inputs = read(batch / 'demands.json')
        original = read(Path(expected_input['path']))
        assert all(inputs[key] == original[key] for key in ('base', 'shock', 'events', 'demand_seed', 'event_seed'))
        with (batch / 'periods.csv').open(encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == done['rows']
        grouped = {}
        for row in rows:
            assert float(row['cost']) == int(row['inventory']) + int(row['backlog'])
            key = (row['group'], row['scenario'], int(row['trace']))
            grouped.setdefault(key, []).append(row)
        episodes = read(batch / 'episodes.json')
        assert len(episodes) == done['episodes']
        lookup = {}
        for episode in episodes:
            key = (episode['group'], episode['scenario'], episode['trace'])
            assert key not in lookup
            subset = grouped[key]
            assert len(subset) == 600
            assert {(int(r['period']), int(r['node'])) for r in subset} == {(p, n) for p in range(1, 201) for n in range(3)}
            assert math.isclose(sum(float(r['cost']) for r in subset) / 600, episode['cost'], abs_tol=1e-9)
            lower = [r for r in subset if int(r['node']) == 0]
            assert math.isclose(sum(int(r['backlog']) for r in lower) / 200, episode['downstream_backlog'], abs_tol=1e-9)
            lookup[key] = episode
        information = read(batch / 'information_audits.json')
        assert len(information) == 1600 * len(methods)
        for item in information:
            completed = item['decision_period'] - 1
            through = completed // k * k
            demand = inputs[item['scenario']][item['trace']]
            history = [sum(demand[i:i+k]) / k for i in range(0, through, k) for _ in range(k)]
            assert item['reconstructed_history'] == history and item['delivered_through_period'] == through
            assert item['report_age'] == completed - through
        for trace in range(4):
            base_rows = grouped[('happo', 'base', trace)]
            for group in methods:
                subset = grouped[(group, 'base', trace)]
                assert [(r['period'], r['node'], r['cost'], r['inventory'], r['backlog'], r['actual_order']) for r in subset] == [(r['period'], r['node'], r['cost'], r['inventory'], r['backlog'], r['actual_order']) for r in base_rows]
                for scenario, target in (('shock', values), ('base', normal)):
                    episode = lookup[(group, scenario, trace)]
                    target[group].append([episode['cost'], episode['downstream_backlog']])
                    paired.append({'suite': name, 'seed': seed, 'k': k, 'trajectory': number * 4 + trace,
                                   'group': group, 'scenario': scenario, 'cost': episode['cost'], 'backlog': episode['downstream_backlog']})
        dest_batch = dest / entry['name']
        dest_batch.mkdir()
        for file in batch.iterdir():
            if file.is_file():
                if file.name in ('periods.csv', 'scores.json', 'information_audits.json'):
                    with file.open('rb') as src, gzip.open(dest_batch / (file.name + '.gz'), 'wb') as sink:
                        shutil.copyfileobj(src, sink)
                else:
                    shutil.copy2(file, dest_batch / file.name)
    return {g: np.asarray(v) for g, v in values.items()}, normal, paired, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    completion = RAW / 'bc_pipeline_v1/completed.json'
    while not completion.exists():
        if not args.wait:
            raise RuntimeError('All evaluations must finish first')
        progress = read(RAW / 'bc_pipeline_v1/progress.json')
        if progress['status'] == 'failed':
            raise RuntimeError('Evaluation pipeline failed; diagnose without overwriting')
        time.sleep(15)
    assert read(completion)['status'] == 'evaluations_completed_analysis_pending'
    out = RAW / 'bc_analysis_v1'
    export = ROOT / 'docs/artifacts/formal_bc_v1'
    if out.exists() or export.exists():
        raise RuntimeError('Preserve existing analysis; do not rerun over it')
    out.mkdir(); export.mkdir()
    groups = {g: [] for g in ('happo', 'llm_library', 'llm_no_screen', 'llm_search_only', 'random_screen')}
    sensitivity = {k: {'happo': [], 'llm_library': []} for k in (1, 5)}
    all_pairs = []; manifests = []; normals = []; training = []
    for seed in range(11, 16):
        name = 'stage_a_seed11_k3_v1' if seed == 11 else f'stage_b_seed{seed}_k3_v1'
        main_values, normal, pairs, manifest = suite(name, seed, 3, ['happo', 'llm_library'], export)
        all_pairs += pairs; manifests.append(manifest); normals.append({'seed': seed, 'means': {g: np.mean(v, axis=0).tolist() for g,v in normal.items()}})
        training.append(read(Path(manifest['training_directory']) / 'completion_audit.json'))
        for group in ('happo', 'llm_library'): groups[group].append(main_values[group])
        values, _, pairs, manifest = suite(f'stage_c_seed{seed}_k3_v1', seed, 3, ['happo', 'llm_no_screen', 'llm_search_only', 'random_screen'], export)
        assert np.array_equal(values['happo'], main_values['happo'])
        all_pairs += pairs; manifests.append(manifest)
        for group in ('llm_no_screen', 'llm_search_only', 'random_screen'): groups[group].append(values[group])
        for k in (1,5):
            values, _, pairs, manifest = suite(f'stage_c_seed{seed}_k{k}_v1', seed, k, ['happo', 'llm_library'], export)
            assert np.array_equal(values['happo'], main_values['happo'])
            for group in sensitivity[k]: sensitivity[k][group].append(values[group])
            all_pairs += pairs; manifests.append(manifest)
    arrays = {g: np.asarray(v) for g,v in groups.items()}
    result = {'training_seeds': list(range(11,16)), 'trajectories': 20, 'metrics': ['cost', 'downstream_backlog'],
              'bootstrap_samples': 20000, 'bootstrap_seed': 20261221, 'resampling': 'Independent model and trajectory resampling retaining crossed structure',
              'main': compare(arrays['happo'], arrays['llm_library']),
              'ablations': {g: compare(arrays[g], arrays['llm_library']) for g in ('llm_no_screen','llm_search_only','random_screen')},
              'sensitivity': {str(k): compare(np.asarray(v['happo']), np.asarray(v['llm_library'])) for k,v in sensitivity.items()},
              'normal_means_by_seed': normals, 'training_audits': training,
              'interpretation': 'Ablations and sensitivity are descriptive, not additional confirmatory claims. Random operators are a diagnostic. Full system uses extra information/computation. All seeds retained; three new seeds did not meet stability criteria.',
              'episodes_executed_including_A': 2000, 'duplicated_audit_episodes': 200, 'calls': 0, 'training_updates_during_evaluation': 0}
    write(out / 'summary.json', result)
    write(out / 'verification.json', {'suites': 20, 'episodes': 2000, 'rows': 1200000, 'input_and_model_audits': 'passed', 'duplicate_HAPPO_metrics_identical': True, 'normal_row_actions_identical': True})
    write(out / 'analysis_manifest.json', {'analyzer_sha256': digest(Path(__file__)), 'suite_manifests': manifests})
    with (out / 'paired.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_pairs[0])); writer.writeheader(); writer.writerows(all_pairs)
    fig, axes = plt.subplots(1,2,figsize=(12,4))
    delta = arrays['llm_library'] - arrays['happo']
    for i, ax in enumerate(axes):
        image = ax.imshow(delta[:,:,i], aspect='auto', cmap='coolwarm', vmin=-max(abs(delta[:,:,i]).max(),1e-9), vmax=max(abs(delta[:,:,i]).max(),1e-9))
        ax.set_yticks(range(5), range(11,16)); ax.set_ylabel('Training seed'); ax.set_xlabel('All 20 trajectories'); ax.set_title(('Cost delta','Downstream backlog delta')[i]); fig.colorbar(image, ax=ax)
    fig.suptitle('LLM library + screening minus frozen HAPPO; negative improves'); fig.tight_layout()
    for suffix in ('png','pdf'): fig.savefig(out / f'paired_matrix.{suffix}',dpi=160)
    plt.close(fig)
    for file in out.iterdir(): shutil.copy2(file, export / file.name)
    input_dest = export / 'inputs'; input_dest.mkdir()
    for file in (RAW / 'stage_a_inputs_v1').iterdir():
        if file.is_file(): shutil.copy2(file,input_dest / file.name)
    write(out / 'completed.json', {'status': 'analysis_completed', 'export': str(export)})
    shutil.copy2(out / 'completed.json', export / 'completed.json')
    print(json.dumps(result['main'], indent=2),flush=True)


if __name__ == '__main__':
    main()
