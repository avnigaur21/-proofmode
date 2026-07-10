import subprocess
import time
from pathlib import Path

from app.schemas.runs import CheckStatus, ProofCheck, ProofRun, TestCommandCheck


class TestCommandVerifier:
    layer = "tests"
    output_limit = 6000

    def verify(self, run: ProofRun) -> ProofCheck:
        if not run.test_commands:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No test commands were configured, so test evidence was not captured.",
            )

        results = [self._run_command(command, run.repo_path) for command in run.test_commands]
        failed_results = [result for result in results if result["exit_code"] != 0]
        timed_out = [result for result in results if result.get("timed_out")]

        if failed_results or timed_out:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary=f"Test command evidence found {len(failed_results) + len(timed_out)} failing command(s).",
                evidence={"commands": results},
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.PASSED,
            summary=f"Captured passing test evidence from {len(results)} command(s).",
            evidence={"commands": results},
        )

    def _run_command(self, command: TestCommandCheck, repo_path: str | None) -> dict[str, object]:
        working_directory = self._working_directory(command, repo_path)
        started_at = time.perf_counter()

        try:
            completed = subprocess.run(
                command.command,
                cwd=working_directory,
                shell=True,
                text=True,
                capture_output=True,
                timeout=command.timeout_seconds,
            )
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            return {
                "name": command.name,
                "command": command.command,
                "working_directory": str(working_directory) if working_directory else None,
                "exit_code": completed.returncode,
                "duration_ms": duration_ms,
                "stdout": self._truncate(completed.stdout),
                "stderr": self._truncate(completed.stderr),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as error:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            return {
                "name": command.name,
                "command": command.command,
                "working_directory": str(working_directory) if working_directory else None,
                "exit_code": -1,
                "duration_ms": duration_ms,
                "stdout": self._truncate(error.stdout or ""),
                "stderr": self._truncate(error.stderr or ""),
                "timed_out": True,
                "error": f"Command exceeded {command.timeout_seconds}s timeout.",
            }
        except Exception as error:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            return {
                "name": command.name,
                "command": command.command,
                "working_directory": str(working_directory) if working_directory else None,
                "exit_code": -1,
                "duration_ms": duration_ms,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "error": str(error),
            }

    def _working_directory(self, command: TestCommandCheck, repo_path: str | None) -> Path | None:
        if command.working_directory:
            return Path(command.working_directory)
        if repo_path:
            return Path(repo_path)
        return None

    def _truncate(self, output: str | bytes | None) -> str:
        if output is None:
            return ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        if len(output) <= self.output_limit:
            return output
        return f"{output[:self.output_limit]}\n...[truncated]"
