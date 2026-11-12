import copy
import importlib.util
import json
from pathlib import Path
import unittest

import yaml

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery_preflight', HERE / 'preflight.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.reference = yaml.safe_load((HERE / 'compose.recovery.reference.yml').read_text(encoding='utf-8'))
        self.baseline = json.loads((HERE / 'runtime-baseline.json').read_text(encoding='utf-8'))

    def test_reference_matches_but_never_authorizes_rebuild(self):
        result = preflight.audit(self.reference, self.baseline)
        self.assertTrue(result['configuration_matches_reference'])
        self.assertFalse(result['ready_to_rebuild'])
        self.assertEqual(result['configured_mounts'], 50)

    def test_missing_mount_is_rejected(self):
        self.reference['services']['case-analysis-app']['volumes'].pop()
        result = preflight.audit(self.reference, self.baseline)
        self.assertFalse(result['configuration_matches_reference'])
        self.assertEqual(len(result['missing_mounts']), 1)

    def test_duplicate_target_is_rejected(self):
        service = self.reference['services']['case-analysis-app']
        service['volumes'].append(copy.deepcopy(service['volumes'][0]))
        self.assertFalse(preflight.audit(self.reference, self.baseline)['configuration_matches_reference'])

    def test_knowledge_configuration_change_is_rejected(self):
        self.reference['services']['case-analysis-app']['environment']['MILVUS_COLLECTION'] = 'wrong_collection'
        result = preflight.audit(self.reference, self.baseline)
        self.assertIn('MILVUS_COLLECTION', result['different_safe_environment_keys'])

    def test_image_guard_and_build_are_rejected(self):
        service = self.reference['services']['case-analysis-app']
        service['image'] = 'unverified:latest'
        service['build'] = '.'
        self.assertFalse(preflight.audit(self.reference, self.baseline)['configuration_matches_reference'])

    def test_secret_value_not_echoed(self):
        service = self.reference['services']['case-analysis-app']
        service['environment']['DB_PASSWORD'] = 'synthetic-test-value'
        result = preflight.audit(self.reference, self.baseline)
        self.assertFalse(result['configuration_matches_reference'])
        self.assertNotIn('synthetic-test-value', json.dumps(result))

    def test_healthcheck_change_is_rejected(self):
        self.reference['services']['case-analysis-app']['healthcheck']['start_period'] = '20s'
        self.assertFalse(preflight.audit(self.reference, self.baseline)['configuration_matches_reference'])

    def test_privileged_mode_is_rejected(self):
        self.reference['services']['case-analysis-app']['privileged'] = True
        self.assertFalse(preflight.audit(self.reference, self.baseline)['configuration_matches_reference'])

    def test_legacy_config_does_not_match_runtime(self):
        legacy = yaml.safe_load((HERE.parents[1] / 'docker-compose.internal.yml').read_text(encoding='utf-8-sig'))
        result = preflight.audit(legacy, self.baseline)
        self.assertFalse(result['configuration_matches_reference'])
        self.assertEqual(len(result['missing_mounts']), 27)
        self.assertEqual(len(result['extra_mounts']), 17)


if __name__ == '__main__':
    unittest.main()
