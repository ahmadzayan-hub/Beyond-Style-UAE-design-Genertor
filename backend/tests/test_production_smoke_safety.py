"""Isolated no-network tests of production smoke safety gates."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("production_smoke", Path(__file__).parents[2] / "scripts" / "production-smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

class SmokeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"SMOKE_ALLOW_WRITES": "", "SMOKE_APPROVED_BACKEND_URL": ""})
        self.env.start()
        self.backend = patch.object(smoke, "BACKEND_URL", "https://synthetic.invalid")
        self.frontend = patch.object(smoke, "FRONTEND_URL", "https://frontend.invalid")
        self.backend.start(); self.frontend.start()
        self.addCleanup(self.env.stop); self.addCleanup(self.backend.stop); self.addCleanup(self.frontend.stop)

    @staticmethod
    def response(method, url, **kwargs):
        if url.endswith('/health'): return 200, {}, b'{"status":"ok","schema_version":"synthetic"}'
        if url.endswith('/ready'): return 200, {}, b'{"status":"ready"}'
        if method == 'OPTIONS': return 200, {
            'access-control-allow-origin': 'https://frontend.invalid',
            'access-control-allow-methods': 'GET, POST',
            'access-control-allow-headers': 'content-type,x-session-token,x-customer-token',
        }, b''
        if method == 'POST': return 404, {}, b'{}'
        return 200, {}, b'{}'

    def test_default_probe_never_writes(self):
        with patch.object(smoke, "request", side_effect=self.response) as req:
            self.assertEqual(smoke.main(), 0)
            self.assertTrue(all(c.args[0] in {'GET', 'OPTIONS'} for c in req.call_args_list))

    def test_transport_blocks_writes_even_if_called_directly(self):
        with patch.object(smoke.urllib.request, "urlopen") as network:
            with self.assertRaises(PermissionError): smoke.request('POST', smoke.BACKEND_URL + '/api/designs')
            network.assert_not_called()

    def test_rejected_preflight_with_allowed_origin_is_not_a_pass(self):
        def rejected(method, url, **kwargs):
            status, headers, body = self.response(method, url, **kwargs)
            return (400, headers, b'Disallowed CORS headers') if method == 'OPTIONS' else (status, headers, body)
        with patch.object(smoke, 'request', side_effect=rejected):
            self.assertEqual(smoke.main(), 1)

    def test_preflight_must_allow_customer_token(self):
        def missing(method, url, **kwargs):
            status, headers, body = self.response(method, url, **kwargs)
            if method == 'OPTIONS':
                self.assertIn('x-customer-token', kwargs['headers']['Access-Control-Request-Headers'])
                headers['access-control-allow-headers'] = 'content-type,x-session-token'
            return status, headers, body
        with patch.object(smoke, 'request', side_effect=missing):
            self.assertEqual(smoke.main(), 1)

    def test_mismatched_approved_target_refused_before_network(self):
        os.environ.update(SMOKE_ALLOW_WRITES='1', SMOKE_APPROVED_BACKEND_URL='https://other.invalid')
        with patch.object(smoke, 'request') as req:
            self.assertEqual(smoke.main(), 2); req.assert_not_called()

    def test_explicit_matching_target_exercises_write_path_with_stub_only(self):
        os.environ.update(SMOKE_ALLOW_WRITES='1', SMOKE_APPROVED_BACKEND_URL=smoke.BACKEND_URL)
        with patch.object(smoke, 'request', side_effect=self.response) as req:
            self.assertEqual(smoke.main(), 1)  # synthetic 404, never a real write
            self.assertTrue(any(c.args[0] == 'POST' for c in req.call_args_list))

if __name__ == '__main__': unittest.main()
