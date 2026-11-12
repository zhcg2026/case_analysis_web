"""Offline comparison only. No SSH, Docker, database access or file writes."""
import argparse
import json
from pathlib import Path
import posixpath
import re
import shlex
import sys

import yaml

HERE = Path(__file__).resolve().parent
SENSITIVE = re.compile(r'PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|ACCESS_KEY|PRIVATE_KEY', re.I)


def audit(document, baseline):
    issues = []
    services = document.get('services', {})
    if len(services) != 1:
        issues.append('Expected exactly one application service; dependency services must remain separate')
    service = services.get('case-analysis-app', {})
    if service.get('container_name') != baseline['container_name']:
        issues.append('Container name differs')
    if 'build' in service:
        issues.append('Unverified fresh build must not replace the observed runtime')
    if not str(service.get('image', '')).startswith('${CASE_ANALYSIS_RECOVERY_IMAGE:?'):
        issues.append('Explicit verified recovery-image guard is missing')
    command = service.get('command', [])
    if isinstance(command, str):
        command = shlex.split(command)
    if command != baseline['command']:
        issues.append('Startup command differs')
    if service.get('working_dir') != baseline['working_dir']:
        issues.append('Working directory differs')
    actual = {m['Destination']: (m['Source'], m['RW'], m['Propagation']) for m in baseline['mounts']}
    configured = {}
    for mount in service.get('volumes', []):
        if isinstance(mount, str):
            source, target, *mode = mount.split(':')
            writable, propagation = not mode or mode[0] != 'ro', 'rprivate'
        else:
            if mount.get('type') != 'bind':
                issues.append('Expected bind mount type')
            source, target = mount['source'], mount['target']
            writable = not mount.get('read_only', False)
            propagation = mount.get('bind', {}).get('propagation', 'rprivate')
        if not source.startswith('/'):
            source = posixpath.normpath(baseline['project_root'] + '/' + source)
        if target in configured:
            issues.append('Duplicate mount target: ' + target)
        configured[target] = (source, writable, propagation)
    missing = sorted(set(actual) - set(configured))
    extra = sorted(set(configured) - set(actual))
    changed = sorted(k for k in set(actual) & set(configured) if actual[k] != configured[k])
    if missing or extra or changed:
        issues.append('Mount coverage or mode differs')
    environment = service.get('environment', {})
    if isinstance(environment, list):
        environment = dict(item.split('=', 1) for item in environment)
    secret_keys = sorted(k for k, v in environment.items() if SENSITIVE.search(k) and v not in (None, '') and not str(v).startswith('${'))
    if secret_keys:
        issues.append('Literal credential values are forbidden; keys: ' + ', '.join(secret_keys))
    missing_env = sorted(set(baseline['safe_environment']) - set(environment))
    env_differences = sorted(k for k, v in baseline['safe_environment'].items() if k in environment and str(environment[k]) != v)
    if env_differences or missing_env:
        issues.append('Explicit non-secret environment does not fully preserve the reference')
    env_files = service.get('env_file', [])
    if isinstance(env_files, str):
        env_files = [env_files]
    if env_files != [baseline['environment_file']]:
        issues.append('Environment-file reference differs; values are never read by this tool')
    health = service.get('healthcheck', {})
    expected_health = baseline['healthcheck']
    if health.get('test') != expected_health['Test'] or health.get('retries') != expected_health['Retries']:
        issues.append('Healthcheck test or retry count differs')
    for configured_key, runtime_key in [('interval', 'Interval'), ('timeout', 'Timeout'), ('start_period', 'StartPeriod')]:
        expected = str(expected_health[runtime_key] // 1_000_000_000) + 's'
        if health.get(configured_key) != expected:
            issues.append('Healthcheck duration differs: ' + configured_key)
    if service.get('restart') != baseline['restart_policy']['Name']:
        issues.append('Restart policy differs')
    networks = service.get('networks', ['default'])
    names = []
    for key in networks:
        definition = document.get('networks', {}).get(key, {})
        if definition.get('external') is not True:
            issues.append('Production network must remain external')
        names.append(definition.get('name', key))
    if sorted(names) != sorted(baseline['networks']):
        issues.append('Network differs')
    if service.get('ports') != ['5001:5000']:
        issues.append('Expected explicit port mapping 5001:5000')
    for configured_key, runtime_key, default in [('privileged', 'privileged', False), ('read_only', 'readonly_rootfs', False)]:
        if service.get(configured_key, default) != baseline[runtime_key]:
            issues.append('Container security option differs: ' + configured_key)
    for key in ('cap_add', 'cap_drop', 'extra_hosts'):
        if (service.get(key) or []) != (baseline[key] or []):
            issues.append('Container option differs: ' + key)
    if service.get('entrypoint') is not None and service['entrypoint'] != baseline['entrypoint']:
        issues.append('Entrypoint override differs')
    if 'user' in service and service['user'] != baseline['user']:
        issues.append('User override differs')
    return {
        'mode': 'offline-read-only', 'configuration_matches_reference': not issues,
        'ready_to_rebuild': False, 'issues': issues, 'expected_mounts': len(actual),
        'configured_mounts': len(configured), 'missing_mounts': missing, 'extra_mounts': extra,
        'different_mounts': changed, 'different_safe_environment_keys': env_differences,
        'missing_explicit_safe_environment_keys': missing_env,
        'environment_comparison_scope': 'Explicit values only; env_file and image inheritance are not resolved',
        'known_legacy_directory_targets': baseline['known_legacy_directory_targets'],
        'remaining_checks': ['Verify current host paths and types', 'Verify recovery image and runtime dependencies',
                             'Secure environment-file recovery', 'Preserve mounted business files',
                             'Validate restoration in isolation under separate authorization'],
        'note': 'Exit 0 means static reference match only. No command is executed and no rebuild is authorized.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose', type=Path, default=HERE / 'compose.recovery.reference.yml')
    parser.add_argument('--baseline', type=Path, default=HERE / 'runtime-baseline.json')
    args = parser.parse_args()
    try:
        document = yaml.safe_load(args.compose.read_text(encoding='utf-8-sig'))
        baseline = json.loads(args.baseline.read_text(encoding='utf-8-sig'))
        result = audit(document, baseline)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError) as error:
        # Never echo parsed environment values in exceptions.
        print(json.dumps({'mode': 'offline-read-only', 'configuration_matches_reference': False,
                          'ready_to_rebuild': False, 'error_type': type(error).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['configuration_matches_reference'] else 2


if __name__ == '__main__':
    sys.exit(main())
