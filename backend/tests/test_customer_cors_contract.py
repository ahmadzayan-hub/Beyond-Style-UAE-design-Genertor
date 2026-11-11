"""Exercise the real CORS configuration without database or network access.

AST literal extraction avoids importing the database-backed application; the
actual pinned Starlette middleware evaluates the repository's allowlists.
Run: python -m unittest discover -s tests -p test_customer_cors_contract.py -v
"""
import ast
from pathlib import Path
import unittest

from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware


class CustomerCorsContractTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / "app/main.py").read_text())
        origins = next(ast.literal_eval(n.value) for n in tree.body
                       if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "_FIRST_PARTY_ORIGINS" for t in n.targets))
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == "add_middleware"
                    and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == "CORSMiddleware")
        options = {k.arg: ast.literal_eval(k.value) for k in call.keywords
                   if k.arg != "allow_origins"}
        self.middleware = CORSMiddleware(None, allow_origins=origins, **options)

    def preflight(self, method, headers, origin="https://frontend-sigma-sable-22.vercel.app"):
        return self.middleware.preflight_response(Headers({
            "origin": origin, "access-control-request-method": method,
            "access-control-request-headers": headers,
        }))

    def test_customer_get_and_post_headers_are_allowed(self):
        for method in ("GET", "POST"):
            with self.subTest(method=method):
                response = self.preflight(method, "content-type,x-customer-token,x-session-token")
                self.assertEqual(response.status_code, 200)
                self.assertIn("x-customer-token", response.headers["access-control-allow-headers"].lower())

    def test_unknown_origin_is_still_refused(self):
        self.assertEqual(self.preflight("POST", "x-customer-token", "https://unknown.invalid").status_code, 400)

    def test_unlisted_headers_are_still_refused(self):
        self.assertEqual(self.preflight("GET", "x-unapproved-token").status_code, 400)


if __name__ == "__main__":
    unittest.main()
