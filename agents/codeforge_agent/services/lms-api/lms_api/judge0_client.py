import base64
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from .errors import ApiError

# JavaScript (Node.js 12.14.0) and Bash, judge0 v1.13.1 db/languages/active.rb.
NODE_LANGUAGE_ID = 63
BASH_LANGUAGE_ID = 46
NODE_BINARY = "/usr/local/node-12.14.0/bin/node"
# Judge0's largest allowed memory limit (judge0.conf MAX_MEMORY_LIMIT).
NODE_MEMORY_LIMIT_KB = 512000


def node_wrapper(source_code):
    """A Bash script that runs the JavaScript with Node.js tuned for the sandbox.

    Judge0 limits memory per process here (address space, not real use), and
    Node.js reserves far more address space than it uses: its default V8
    worker threads alone push it past 512 MB, so every program -- even
    console.log("Hello") -- crashed or hung as "Time Limit Exceeded". One V8
    worker and one libuv thread keep it to ~30 MB of real memory. The code
    goes in as base64, so nothing in it can change the script around it.
    """
    encoded = base64.b64encode(source_code.encode("utf-8")).decode("ascii")
    return (
        f"printf '%s' '{encoded}' | base64 -d > main.js && "
        f"UV_THREADPOOL_SIZE=1 exec {NODE_BINARY} --v8-pool-size=1 --max-old-space-size=256 main.js\n"
    )


def expects_no_output(expected_output):
    return expected_output is not None and not str(expected_output).strip()


class Judge0Client:
    def execute(self, source_code, language_id, stdin_text, expected_output):
        """Run the code once. A test whose correct answer is no output at all
        (Woof n times with n = 0) is judged here, not by Judge0: Judge0 stores
        "printed nothing" as null and compares it with the expected "", so a
        correct program came back Wrong Answer. Judge0 runs it with no expected
        output (Accepted if it ran cleanly) and we check nothing was printed."""
        if expects_no_output(expected_output):
            result = self.execute(source_code, language_id, stdin_text, None)
            if result["passed"] and result["stdout"].strip():
                return {**result, "passed": False, "status": "Wrong Answer"}
            return result
        language_id = int(language_id)
        memory_limit = 128000
        if language_id == NODE_LANGUAGE_ID:
            source_code, language_id, memory_limit = node_wrapper(source_code), BASH_LANGUAGE_ID, NODE_MEMORY_LIMIT_KB
        payload = {
            "source_code": source_code,
            "language_id": language_id,
            "stdin": stdin_text,
            "expected_output": expected_output,
            "cpu_time_limit": 2,
            "wall_time_limit": 5,
            "memory_limit": memory_limit,
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
