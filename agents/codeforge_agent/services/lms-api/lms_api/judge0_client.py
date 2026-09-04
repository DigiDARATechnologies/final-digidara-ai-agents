import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from .errors import ApiError


class Judge0Client:
    def execute(self, source_code, language_id, stdin_text, expected_output):
        payload = {
            "source_code": source_code,
            "language_id": int(language_id),
            "stdin": stdin_text,
            "expected_output": expected_output,
            "cpu_time_limit": 2,
            "wall_time_limit": 5,
            "memory_limit": 128000,
            "max_processes_and_or_threads": 32,
            "enable_network": False,
            "enable_per_process_and_thread_time_limit": True,
            "enable_per_process_and_thread_memory_limit": True,
        }
        result = self._request("POST", "/submissions", payload, {"base64_encoded": "false", "wait": "true"})
        token = result.get("token")
        for _attempt in range(40):
            status_id = int((result.get("status") or {}).get("id", 0))
            if status_id > 2:
                if status_id == 13:
                    current_app.logger.error("Judge0 returned an internal execution error: %s", result.get("message"))
                    raise ApiError("The secure evaluator worker is unhealthy.", 503, "evaluator_worker_error")
                return self._safe_result(result)
            if not token:
                break
            time.sleep(0.25)
            result = self._request("GET", f"/submissions/{token}", query={"base64_encoded": "false"})
        raise ApiError("The code evaluator did not finish in time.", 504, "evaluator_timeout")

    def health(self):
        try:
            self._request("GET", "/about")
            return True
        except ApiError:
            return False

    def languages(self):
        # Judge0's language list is static reference data (rarely changes),
        # so a short in-process cache avoids hitting Judge0 on every call.
        import time as _time
        now = _time.time()
        cached = getattr(self, "_languages_cache", None)
        if cached and now - cached[0] < 3600:
            return cached[1]
        result = self._request("GET", "/languages")
        self._languages_cache = (now, result)
        return result

    def _request(self, method, path, payload=None, query=None):
        config = current_app.config
        url = config["JUDGE0_URL"].rstrip("/") + path
        if query:
            url += "?" + urlencode(query)
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if config["JUDGE0_AUTHN_TOKEN"]:
            headers[config["JUDGE0_AUTHN_HEADER"]] = config["JUDGE0_AUTHN_TOKEN"]
        if config["JUDGE0_AUTHZ_TOKEN"]:
            headers[config["JUDGE0_AUTHZ_HEADER"]] = config["JUDGE0_AUTHZ_TOKEN"]
        request = Request(url, method=method, headers=headers, data=json.dumps(payload).encode() if payload is not None else None)
        try:
            with urlopen(request, timeout=config["JUDGE0_TIMEOUT_SECONDS"]) as response:
                return json.loads(response.read().decode())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            current_app.logger.warning("Judge0 request failed: %s", exc)
            raise ApiError("Secure code execution is temporarily unavailable.", 503, "evaluator_unavailable") from exc

    @staticmethod
    def _safe_result(result):
        status = result.get("status") or {}
        return {
            "passed": int(status.get("id", 0)) == 3,
            "status": str(status.get("description") or "Unknown")[:80],
            "stdout": str(result.get("stdout") or "")[:4000],
            "stderr": str(result.get("stderr") or "")[:4000],
            "compileOutput": str(result.get("compile_output") or "")[:4000],
            "message": str(result.get("message") or "")[:1000],
            "time": result.get("time"),
            "memory": result.get("memory"),
        }
