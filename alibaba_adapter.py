"""Alibaba Cloud farm adapter (PC-side worker).

Wraps farm.py as a subprocess — registers a fresh Alibaba Cloud account,
harvests a Model Studio API key (1M free tokens), returns it for the pool.
"""
from __future__ import annotations
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

from .base import NormalizedAccount, ProviderAdapter

_PROVIDERS_DIR = Path(__file__).resolve().parent
_ATMO_WORKER_DIR = _PROVIDERS_DIR.parent.parent
_FARM_DIR = Path(os.environ.get("ALIBABA_FARM_DIR", str(Path.home() / "alibaba-farm")))
_FARM_SCRIPT = _FARM_DIR / "farm.py"
_ENV_FILE = _FARM_DIR / ".env"
_LOG_FILE = _FARM_DIR / "adapter_debug.log"
_SCRIPT_TIMEOUT = 600.0


def _log(msg: str):
    """Log to file and stdout."""
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class AlibabaFarmAdapter(ProviderAdapter):
    name = "alibaba"

    async def parse_account(self, raw_line: str) -> NormalizedAccount:
        line = raw_line.strip()
        domain = line.split(":")[0].strip() if ":" in line else line
        if not domain:
            raise ValueError(f"Missing domain: {raw_line!r}")
        return NormalizedAccount(provider=self.name, identifier=domain, secret="", metadata={}, raw=raw_line)

    async def bootstrap_session(self, account: NormalizedAccount, headless: bool | None = None) -> Any:
        _log(f"bootstrap_session: domain={account.identifier}")
        return {"farm_dir": str(_FARM_DIR)}

    async def authenticate(self, account: NormalizedAccount, session: Any) -> dict[str, Any]:
        _log(f"authenticate: START domain={account.identifier}")
        try:
            return await self._do_authenticate(account, session)
        except Exception as e:
            _log(f"authenticate: ERROR {type(e).__name__}: {e}")
            _log(traceback.format_exc())
            raise

    async def _do_authenticate(self, account: NormalizedAccount, session: Any) -> dict[str, Any]:
        if not _FARM_SCRIPT.exists():
            raise RuntimeError(f"farm.py not found at {_FARM_SCRIPT}")

        domain = account.identifier
        _log(f"farm.py path: {_FARM_SCRIPT}, exists=True")
        _log(f"env file: {_ENV_FILE}, exists={_ENV_FILE.exists()}")

        tmp_fd, tmp_results = tempfile.mkstemp(suffix=".json", prefix="alibaba_farm_", dir=str(_FARM_DIR))
        os.close(tmp_fd)
        with open(tmp_results, "w") as f:
            json.dump([], f)
        _log(f"temp results: {tmp_results}")

        env = os.environ.copy()
        if _ENV_FILE.exists():
            with open(_ENV_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
        _log(f"IMAP_USER={env.get('IMAP_USER','MISSING')}")

        env["MAX_ATTEMPTS"] = "1"
        env["EMAIL_DOMAIN"] = domain
        env["RESULTS_FILE"] = tmp_results
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        venv_python = _ATMO_WORKER_DIR / "venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        _log(f"python_exe: {python_exe}")

        _log(f"launching farm.py for domain={domain}...")
        proc = await asyncio.create_subprocess_exec(
            python_exe, "-u", str(_FARM_SCRIPT),
            cwd=str(_FARM_DIR), env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        _log(f"farm.py PID: {proc.pid}")

        log_lines = []
        try:
            while True:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=_SCRIPT_TIMEOUT)
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    _log(f"[farm] {decoded}")
                    log_lines.append(decoded)
            await proc.wait()
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                os.unlink(tmp_results)
            except Exception:
                pass
            raise RuntimeError(f"farm.py timed out after {_SCRIPT_TIMEOUT}s")

        _log(f"farm.py exit code: {proc.returncode}")

        result = None
        try:
            with open(tmp_results, encoding="utf-8") as f:
                results = json.load(f)
            if results and isinstance(results, list) and len(results) > 0:
                result = results[-1]
                _log(f"result: email={result.get('email')} key={result.get('api_key','')}")
        except Exception as e:
            _log(f"read results error: {e}")
        finally:
            try:
                os.unlink(tmp_results)
            except Exception:
                pass

        if not result:
            tail = "\n".join(log_lines[-15:])
            raise RuntimeError(f"farm.py no results (exit={proc.returncode})\n--- tail ---\n{tail}")

        api_key = result.get("api_key", "")
        if not api_key or not api_key.startswith("sk-"):
            raise RuntimeError(f"invalid api_key: {api_key[:30]}")

        _log(f"SUCCESS: {result.get('email')} key={api_key}")
        return {"result": result, "log_tail": "\n".join(log_lines[-30:]), "tmp_results": tmp_results}

    async def fetch_tokens(self, account: NormalizedAccount, auth_state: dict[str, Any], session: Any) -> dict[str, str]:
        result = auth_state.get("result", {})
        _log(f"fetch_tokens: email={result.get('email')}")
        return {
            "api_key": result.get("api_key", ""),
            "refresh_token": "",
            "web_cookie": "",
            "profile_arn": "",
            "token_expires_at": "0",
            "email": result.get("email", ""),
            "password": result.get("password", ""),
        }

    async def fetch_quota(self, account: NormalizedAccount, tokens: dict[str, str], session: Any) -> dict[str, Any] | None:
        _log("fetch_quota: returning 1M/1M")
        return {"remaining": 1000000.0, "limit": 1000000.0}

    async def cleanup_session(self, session: Any) -> None:
        _log("cleanup_session")
        return None
