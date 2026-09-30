"""Contract, transport, candidate retention, and distribution checks.

All API data is synthetic. No API key, hosted inference, or model weights needed.
"""

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/recon3d-cross-cell-deg/scripts"
sys.path.insert(0, str(SCRIPTS))
from recon3d_bridge import APIError, ContractError, JevClient, load_instructions, prioritize
from recon3d_bridge.client import validate_request, validate_response

spec = importlib.util.spec_from_file_location("manage", ROOT / "tools/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def request():
    return json.loads((ROOT / "examples/decision.json").read_text())


def response():
    return {
        "model": "jev-1.13.0",
        "answers": {
            "has_unmeasured_transfer": {"type": "noul", "noul": 0.95},
            "review_queue": {"type": "choice", "choice": "needs_input",
                             "probabilities": {"needs_input": 0.9, "ready_to_inspect": 0.1}, "confidence": 0.8},
            "review_priority": {"type": "score", "score": 0.3,
                                "legend": {"0": "Insufficient detail", "1": "Some checkable detail", "2": "Clear detail"},
                                "probabilities": {"0": 0.7, "1": 0.3, "2": 0.0}, "confidence": 0.55},
        },
        "usage": {"input_tokens": 123, "output_tokens": 0},
    }


class ContractTests(unittest.TestCase):
    def test_mixed_primitives(self):
        validate_request(request())
        validate_response(response(), request()["questions"])

    def test_structured_criteria_and_instructions(self):
        payload = request()
        payload["questions"]["review_queue"]["instructions"] = {"question": "Which queue?"}
        payload["questions"]["review_queue"]["criteria"]["needs_input"] = None
        payload["questions"]["review_priority"]["criteria"][0] = {"level": "insufficient"}
        validate_request(payload)

    def test_request_limits_and_finite_json(self):
        for mutate in (
            lambda p: p["questions"]["review_priority"].update(criteria=["one"]),
            lambda p: p["questions"]["review_queue"].update(criteria={"one": None}),
            lambda p: p.update(state={"x": float("nan")}),
            lambda p: p["questions"]["has_unmeasured_transfer"].update(type="chat"),
        ):
            payload = request()
            mutate(payload)
            with self.assertRaises(ContractError):
                validate_request(payload)

    def test_response_missing_answer_is_not_success(self):
        value = response()
        del value["answers"]["review_queue"]
        with self.assertRaises(ContractError):
            validate_response(value, request()["questions"])

    def test_invalid_distributions_types_and_scores(self):
        for mutate in (
            lambda r: r["answers"]["review_priority"].update(score=float("nan")),
            lambda r: r["answers"]["review_priority"].update(score=1.8),
            lambda r: r["answers"]["review_queue"].update(choice="ready_to_inspect"),
            lambda r: r["answers"]["review_queue"].update(probabilities={"needs_input": 0.5}),
            lambda r: r["answers"]["has_unmeasured_transfer"].update(noul=True),
            lambda r: r["usage"].update(input_tokens=-1),
        ):
            value = response()
            mutate(value)
            with self.assertRaises(ContractError):
                validate_response(value, request()["questions"])

    def test_endpoint_configuration(self):
        with self.assertRaises(ContractError):
            JevClient(base_url="http://example.com/v1", api_key="synthetic-key")
        with self.assertRaises(ContractError):
            JevClient(base_url="https://example.com/v1?key=secret", api_key="synthetic-key")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ContractError):
                JevClient()
            client = JevClient(base_url="http://127.0.0.1:8000/v1", api_key="")
            self.assertEqual(client.api_key, "")


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.replies = []
        test = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle_request(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                test.calls.append({"path": self.path, "method": self.command,
                                   "headers": dict(self.headers), "body": json.loads(body) if body else None})
                status, payload, headers = test.replies.pop(0)
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(encoded)

            do_POST = handle_request
            do_GET = handle_request

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def client(self, **kwargs):
        return JevClient(base_url=self.base_url, api_key="synthetic-test-key", **kwargs)

    def test_real_http_roundtrip_and_models(self):
        self.replies = [(200, response(), {}), (200, {"models": [{"name": "laya"}]}, {})]
        payload = request()
        value = self.client().evaluate(**payload)
        self.assertEqual(value["model"], "jev-1.13.0")
        self.assertEqual(self.calls[0]["path"], "/v1/systemone")
        self.assertEqual(self.calls[0]["headers"]["Authorization"], "Bearer synthetic-test-key")
        self.assertEqual(self.calls[0]["body"], payload)
        self.assertEqual(self.client().list_models()["models"][0]["name"], "laya")
        self.assertEqual(self.calls[1]["method"], "GET")

    def test_local_laya_no_key_and_zero_output_tokens(self):
        value = response()
        value["model"] = "laya-english"
        value["answers"]["has_unmeasured_transfer"]["action"] = "yes"
        self.replies = [(200, value, {})]
        result = JevClient(base_url=self.base_url, api_key="", model="laya").evaluate(
            state=request()["state"], questions=request()["questions"])
        self.assertNotIn("Authorization", self.calls[0]["headers"])
        self.assertEqual(self.calls[0]["body"]["model"], "laya")
        self.assertEqual(result["usage"]["output_tokens"], 0)

    def test_rate_limits_retry_and_honor_retry_after(self):
        self.replies = [(429, {}, {"Retry-After": "3"}), (529, {}, {}), (200, response(), {})]
        with patch("recon3d_bridge.client.time.sleep") as sleep:
            self.client().evaluate(**request())
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [3, 2])
        self.assertEqual(len(self.calls), 3)

    def test_failed_auth_sanitized_and_not_retried(self):
        self.replies = [(401, {"detail": "secret-key or private state should never be echoed"}, {})]
        with self.assertRaises(APIError) as caught:
            self.client().evaluate(**request())
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(len(self.calls), 1)

    def test_context_failure_is_not_truncated_or_retried(self):
        self.replies = [(422, {"detail": "context exceeds model limit"}, {})]
        payload = request()
        payload["state"] = "S" * 70_000
        with self.assertRaises(APIError):
            self.client().evaluate(**payload)
        self.assertEqual(self.calls[0]["body"]["state"], payload["state"])
        self.assertEqual(len(self.calls), 1)

    def test_redirect_does_not_forward_credentials(self):
        self.replies = [(307, {}, {"Location": self.base_url + "/stolen"})]
        with self.assertRaises(APIError) as caught:
            self.client().evaluate(**request())
        self.assertEqual(caught.exception.status, 307)
        self.assertEqual(len(self.calls), 1)

    def test_retry_budget_stops_cleanly(self):
        self.replies = [(429, {}, {"Retry-After": "1000"})]
        with self.assertRaises(APIError):
            self.client(max_retry_delay=5).evaluate(**request())
        self.assertEqual(len(self.calls), 1)

    def test_invalid_response_fails_closed(self):
        value = response()
        value["answers"]["review_priority"]["score"] = "high"
        self.replies = [(200, value, {})]
        with self.assertRaises(ContractError):
            self.client().evaluate(**request())


class GuidanceTests(unittest.TestCase):
    def candidates(self):
        return [{"id": "a", "summary": "Synthetic A", "private_extra": "not sent"},
                {"id": "b", "summary": "Synthetic B"},
                {"id": "c", "summary": "Synthetic C"}]

    def test_retention_errors_and_pending_review(self):
        calls = []

        class Client:
            base_url = "https://synthetic.invalid/v1"
            model = "test-model"

            def evaluate(self, *, state, questions):
                calls.append(state)
                if len(calls) == 2:
                    raise APIError("Synthetic error", 422)
                return {"model": "test-version", "usage": {"input_tokens": 1, "output_tokens": 0},
                        "answers": {"review_priority": {"score": len(calls) / 2, "confidence": 0.5}}}

        checkpoints = []
        items = self.candidates()
        original = copy.deepcopy(items)
        report = prioritize(items, client=Client(), checkpoint=lambda r: checkpoints.append(copy.deepcopy(r)))
        self.assertEqual(items, original)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all("private_extra" not in json.dumps(c) for c in calls))
        self.assertEqual([e["candidate"]["id"] for e in report["entries"]], ["c", "a", "b"])
        self.assertEqual(report["scored_count"], 2)
        self.assertFalse(report["guidance_complete"])
        self.assertFalse(report["review_complete"])
        self.assertEqual(report["review_pending_count"], 3)
        self.assertEqual(checkpoints[0]["candidate_count"], 3)
        self.assertEqual(len(checkpoints[0]["entries"]), 3)
        self.assertEqual(report["entries"][-1]["guidance_status"], "error")

    def test_no_model_retains_all_and_duplicate_ids_fail(self):
        items = self.candidates()
        report = prioritize(items)
        self.assertEqual([e["candidate"] for e in report["entries"]], items)
        self.assertFalse(report["review_complete"])
        with self.assertRaises(ContractError):
            prioritize([items[0], items[0]])


class DistributionTests(unittest.TestCase):
    def test_instructions_and_package_validation(self):
        self.assertTrue(load_instructions().startswith("# Recon3D"))
        self.assertEqual(manage.validate()["status"], "PASS")

    def test_all_native_targets_and_copied_cli(self):
        with tempfile.TemporaryDirectory(prefix="recon3d path with spaces ") as name:
            home = Path(name)
            for framework, relative in manage.FRAMEWORK_PATHS.items():
                manage.install(framework, home=home)
                target = home / relative / manage.NAME
                self.assertEqual(manage.fingerprint(target), manage.fingerprint(manage.SOURCE))
                run = subprocess.run([sys.executable, str(target / "scripts/recon3d.py"), "prompt", "--json"],
                                     check=True, capture_output=True, text=True)
                self.assertEqual(json.loads(run.stdout)["content"], load_instructions())

    def test_no_clobber_idempotence_and_recoverable_replace(self):
        with tempfile.TemporaryDirectory() as name:
            destination = Path(name) / "skills"
            manage.install("agents", destination=destination)
            self.assertEqual(manage.install("agents", destination=destination)["status"], "unchanged")
            target = destination / manage.NAME
            (target / "user-note.txt").write_text("local edits")
            with self.assertRaises(ValueError):
                manage.install("agents", destination=destination)
            self.assertEqual((target / "user-note.txt").read_text(), "local edits")
            result = manage.install("agents", destination=destination, replace=True)
            self.assertEqual((Path(result["backup"]) / "user-note.txt").read_text(), "local edits")
            self.assertFalse((target / "user-note.txt").exists())

    def test_archives_contain_runnable_skill_and_no_repo_secrets(self):
        with tempfile.TemporaryDirectory() as name:
            for kind in ("plugin", "skill"):
                output = Path(name) / f"{kind}.zip"
                manage.pack(output, kind=kind)
                with zipfile.ZipFile(output) as archive:
                    names = archive.namelist()
                    prefix = "skills/recon3d-cross-cell-deg/" if kind == "plugin" else ""
                    self.assertIn(prefix + "SKILL.md", names)
                    self.assertIn(prefix + "scripts/recon3d_bridge/client.py", names)
                    self.assertFalse(any(".git/" in n or "__pycache__" in n or ".env" in n for n in names))
                    if kind == "plugin":
                        self.assertIn(".claude-plugin/plugin.json", names)
                        self.assertIn(".codex-plugin/plugin.json", names)

    def test_cli_dry_run_and_full_queue_without_credentials(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "result.json"
            subprocess.run([sys.executable, str(SCRIPTS / "recon3d.py"), "evaluate",
                            "--input", str(ROOT / "examples/decision.json"), "--output", str(output), "--dry-run"],
                           check=True, capture_output=True)
            self.assertEqual(json.loads(output.read_text()), request())
            subprocess.run([sys.executable, str(SCRIPTS / "recon3d.py"), "prioritize",
                            "--input", str(ROOT / "examples/candidates.json"), "--output", str(output), "--no-model"],
                           check=True, capture_output=True)
            self.assertEqual(json.loads(output.read_text())["candidate_count"], 2)


if __name__ == "__main__":
    unittest.main()
