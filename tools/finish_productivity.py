#!/usr/bin/env python3
"""One-time, repository-scoped, verification-driven PR continuation.

No admin override, force push, check suppression, or failing-test retry is used.
The source integration and this driver are removed from the final feature tree.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import traceback

ROOT = Path(__file__).resolve().parent.parent
REPO = 'wieslawsoltes/KestrelCAD'
BRANCH = 'feature/productivity-tools-20260908'
REVIEWED_PR10 = 'a95f1dd3c2a20b2f2c66f0ee5c18205f61dfd52e'
EVIDENCE = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'kestrel-continuation-evidence'
EVIDENCE.mkdir(exist_ok=True)
status = {'repository': REPO, 'stages': [], 'complete': False}

def record(stage, **values):
    item = {'stage': stage, **values}
    status['stages'].append(item)
    (EVIDENCE / 'status.json').write_text(json.dumps(status, indent=2))
    print(json.dumps(item), flush=True)

def run(*args, cwd=ROOT, capture=False, env=None):
    print('RUN', ' '.join(map(str, args)), flush=True)
    result = subprocess.run(list(map(str, args)), cwd=cwd, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            env=env)
    return result.stdout.strip() if capture else None

def api(path, method='GET', fields=None):
    args = ['gh', 'api', '--method', method, path]
    if fields is not None:
        args += ['--input', '-']
    result = subprocess.run(args, check=True, text=True, input=json.dumps(fields) if fields is not None else None, stdout=subprocess.PIPE)
    return json.loads(result.stdout) if result.stdout.strip() else None

def sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise RuntimeError('Invalid repository commit identifier.')
    return value

def current_main():
    return sha(api('repos/' + REPO + '/git/ref/heads/main')['object']['sha'])

def evidence_reports(source, prefix):
    dest = EVIDENCE / prefix
    dest.mkdir(exist_ok=True)
    for path in (source / 'tests/results').glob('*.json'):
        shutil.copy2(path, dest / path.name)
    for name in ('build-info.json', 'verification.json'):
        if (source / name).is_file():
            shutil.copy2(source / name, dest / name)

def verify(source, head, prefix):
    run(sys.executable, 'tools/verify.py', '--previews', cwd=source,
        env={**os.environ, 'SOURCE_HEAD': sha(head)})
    evidence_reports(source, prefix)
    record(prefix, source_head=head, verification='complete suite succeeded')

def review_and_checks(number, head):
    reviews = api('repos/' + REPO + '/pulls/' + str(number) + '/reviews?per_page=100')
    effective = {}
    for review in reviews:
        if review['state'] in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
            effective[review['user']['login']] = review['state']
    if 'CHANGES_REQUESTED' in effective.values():
        raise RuntimeError('A reviewer requested changes; no automatic merge is permitted.')
    for _ in range(90):
        checks = api('repos/' + REPO + '/commits/' + head + '/check-runs?per_page=100')['check_runs']
        combined = api('repos/' + REPO + '/commits/' + head + '/status')
        if any(c['status'] == 'completed' and c['conclusion'] not in ('success', 'neutral', 'skipped') for c in checks):
            raise RuntimeError('A check failed on the exact proposed head.')
        if any(s['state'] in ('failure', 'error') for s in combined.get('statuses', [])):
            raise RuntimeError('A commit status failed on the exact proposed head.')
        if all(c['status'] == 'completed' for c in checks) and not any(s['state'] == 'pending' for s in combined.get('statuses', [])):
            return
        time.sleep(5)
    raise RuntimeError('Checks remain pending; the PR was not merged.')

def merge(number, head, base, title):
    pr = api('repos/' + REPO + '/pulls/' + str(number))
    if pr.get('merged'):
        record('pr-' + str(number), merged=True, merge_commit=pr.get('merge_commit_sha'), already_merged=True)
        return pr['merge_commit_sha']
    if pr['state'] != 'open' or pr['head']['sha'] != head or pr['base']['sha'] != base or current_main() != base:
        raise RuntimeError('PR head or base moved after verification; no stale merge was attempted.')
    if pr['head']['repo']['full_name'] != REPO:
        raise RuntimeError('Unexpected cross-repository head.')
    review_and_checks(number, head)
    if pr.get('draft'):
        run('gh', 'pr', 'ready', str(number), '--repo', REPO)
    result = api('repos/' + REPO + '/pulls/' + str(number) + '/merge', 'PUT',
                 {'sha': head, 'merge_method': 'squash', 'commit_title': title})
    if not result.get('merged'):
        raise RuntimeError('GitHub did not merge the verified PR: ' + json.dumps(result))
    record('pr-' + str(number), merged=True, merge_commit=result['sha'], verified_head=head)
    api('repos/' + REPO + '/issues/' + str(number) + '/comments', 'POST', {'body':
        'Merged after complete verification of source `' + head + '` against main `' + base + '` and normal review/check gates. Evidence is retained by workflow run ' + os.environ.get('GITHUB_SERVER_URL', 'https://github.com') + '/' + REPO + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID', '') + '. No administrator override or check suppression was used.'})
    return result['sha']

def verify_pr10():
    pr = api('repos/' + REPO + '/pulls/10')
    if pr.get('merged'):
        record('pr-10', merged=True, already_merged=True, merge_commit=pr.get('merge_commit_sha'))
        return
    if pr['state'] != 'open' or pr['head']['sha'] != REVIEWED_PR10:
        record('pr-10', merged=False, reason='Current head differs from the previously reviewed revision; requires inspection.')
        return
    base = current_main()
    run('git', 'fetch', 'origin', 'main', 'feature/source-preservation-binary-dxf')
    # Only merge the reviewed source when it already incorporates current main.
    check = subprocess.run(['git', 'merge-base', '--is-ancestor', base, REVIEWED_PR10], cwd=ROOT)
    if check.returncode:
        record('pr-10', merged=False, reason='Current main is not an ancestor of the reviewed head; requires reconciliation.')
        return
    work = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'kestrel-pr10'
    run('git', 'worktree', 'add', '--detach', str(work), REVIEWED_PR10)
    try:
        if (work / '.transfer').exists() or (work / '.import').exists():
            raise RuntimeError('PR #10 still contains a source transfer instead of a final readable tree.')
        verify(work, REVIEWED_PR10, 'pr10-verification')
        merge(10, REVIEWED_PR10, base, 'fix: preserve DXF precision, significant text spaces and Unicode blocks')
    finally:
        run('git', 'worktree', 'remove', '--force', str(work))

def find_feature_pr():
    for _ in range(60):
        prs = api('repos/' + REPO + '/pulls?state=open&head=wieslawsoltes:' + BRANCH + '&per_page=100')
        if len(prs) == 1:
            return prs[0]['number']
        if len(prs) > 1:
            raise RuntimeError('Ambiguous feature PR.')
        time.sleep(5)
    raise RuntimeError('Feature branch is committed but no open PR was found; no merge was attempted.')

def external_verification(head):
    api('repos/' + REPO + '/actions/workflows/verify.yml/dispatches', 'POST', {'ref': BRANCH})
    for _ in range(180):
        runs = api('repos/' + REPO + '/actions/workflows/verify.yml/runs?branch=' + BRANCH + '&event=workflow_dispatch&head_sha=' + head + '&per_page=20')['workflow_runs']
        runs = [r for r in runs if r['head_sha'] == head]
        if runs:
            latest = max(runs, key=lambda r:r['id'])
            if latest['status'] == 'completed':
                record('independent-ci', run=latest['html_url'], conclusion=latest['conclusion'], source_head=head)
                if latest['conclusion'] != 'success':
                    raise RuntimeError('Independent complete verification did not succeed; no merge is permitted.')
                return
        time.sleep(5)
    raise RuntimeError('Independent verification remains pending; the feature PR was not merged.')

def capture_source():
    excluded = {'.git', '.venv', '_site', '.transfer', '.import', 'node_modules', '__pycache__', 'results'}
    font_extensions = {'.ttf', '.otf', '.woff', '.woff2', '.shx', '.shp', '.ttc'}
    with tarfile.open(EVIDENCE / 'readable-source.tar.gz', 'w:gz') as archive:
        for path in sorted(ROOT.rglob('*')):
            relative = path.relative_to(ROOT)
            if any(part in excluded for part in relative.parts) or path.is_symlink() or not path.is_file() or path.suffix.lower() in font_extensions or path.suffix in ('.zip', '.pyc'):
                continue
            archive.add(path, arcname=relative.as_posix(), recursive=False)

try:
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF_NAME') != BRANCH:
        raise RuntimeError('This one-time continuation is restricted to its explicit repository and feature branch.')
    run('git', 'config', 'user.name', 'github-actions[bot]')
    run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    verify_pr10()
    run('git', 'fetch', 'origin', 'main')
    base = sha(run('git', 'rev-parse', 'origin/main', capture=True))
    run('git', 'merge', '--no-edit', 'origin/main')
    run(sys.executable, 'tools/integrate_productivity.py')
    Path(__file__).unlink(missing_ok=True)
    run('git', 'add', '--all')
    run('git', 'commit', '-m', 'feat: integrate tested drafting productivity into the real editor')
    head = sha(run('git', 'rev-parse', 'HEAD', capture=True))
    verify(ROOT, head, 'productivity-verification')
    if current_main() != base:
        raise RuntimeError('Main advanced during tests; retain the candidate for reconciliation rather than merging stale source.')
    run('git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH)
    record('feature-source', committed=True, head=head, branch=BRANCH)
    number = find_feature_pr()
    external_verification(head)
    merged = merge(number, head, base, 'feat: drafting productivity, analytic stations, quantities and layer states')
    api('repos/' + REPO + '/actions/workflows/pages.yml/dispatches', 'POST', {'ref':'main'})
    record('pages', dispatched=True, merged_commit=merged, note='Deployment success must be verified separately; dispatch is not a successful deployment.')
    status['complete'] = True
except Exception as error:
    status['error'] = str(error)
    traceback.print_exc()
finally:
    (EVIDENCE / 'status.json').write_text(json.dumps(status, indent=2))
    try:
        evidence_reports(ROOT, 'latest-reports')
        capture_source()
    except Exception:
        traceback.print_exc()
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write('## Verified continuation status\n\n```json\n' + json.dumps(status, indent=2) + '\n```\n')
if not status['complete']:
    sys.exit(1)
