import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.diff_analysis import classify_changed_file, summarize_categories


class DiffFileContext(BaseModel):
    path: str
    categories: list[str]
    patch: str = ""
    additions: int = 0
    deletions: int = 0
    truncated: bool = False


class GitDiffContext(BaseModel):
    repo_path: str
    changed_files: list[DiffFileContext] = Field(default_factory=list)
    category_summary: dict[str, int] = Field(default_factory=dict)
    total_patch_chars: int = 0
    truncated: bool = False


class GitDiffContextService:
    def __init__(self, max_total_patch_chars: int = 12000, max_file_patch_chars: int = 4000) -> None:
        self._max_total_patch_chars = max_total_patch_chars
        self._max_file_patch_chars = max_file_patch_chars

    def build(self, repo_path_value: str | None) -> GitDiffContext | None:
        if repo_path_value is None:
            return None

        repo_path = Path(repo_path_value).expanduser().resolve()
        if not repo_path.exists() or not (repo_path / ".git").exists():
            return None

        changed_files = self._changed_files(repo_path)
        remaining_budget = self._max_total_patch_chars
        file_contexts: list[DiffFileContext] = []
        was_truncated = False

        for path in changed_files:
            patch = self._file_patch(repo_path, path)
            additions, deletions = self._count_patch_lines(patch)
            truncated = False

            if len(patch) > self._max_file_patch_chars:
                patch = patch[: self._max_file_patch_chars]
                truncated = True

            if len(patch) > remaining_budget:
                patch = patch[: max(remaining_budget, 0)]
                truncated = True

            remaining_budget -= len(patch)
            was_truncated = was_truncated or truncated or remaining_budget <= 0

            file_contexts.append(
                DiffFileContext(
                    path=path,
                    categories=classify_changed_file(path),
                    patch=patch,
                    additions=additions,
                    deletions=deletions,
                    truncated=truncated,
                )
            )

            if remaining_budget <= 0:
                break

        return GitDiffContext(
            repo_path=str(repo_path),
            changed_files=file_contexts,
            category_summary=summarize_categories(changed_files),
            total_patch_chars=self._max_total_patch_chars - max(remaining_budget, 0),
            truncated=was_truncated or len(file_contexts) < len(changed_files),
        )

    def _changed_files(self, repo_path: Path) -> list[str]:
        names = set()
        for args in (
            ["diff", "--name-only"],
            ["diff", "--name-only", "--cached"],
            ["ls-files", "--others", "--exclude-standard"],
        ):
            output = self._git(repo_path, args)
            names.update(line.strip() for line in output.splitlines() if line.strip())
        return sorted(names)

    def _file_patch(self, repo_path: Path, path: str) -> str:
        patch_parts = [
            self._git(repo_path, ["diff", "--", path]),
            self._git(repo_path, ["diff", "--cached", "--", path]),
        ]
        patch = "\n".join(part for part in patch_parts if part)
        if patch:
            return patch

        file_path = repo_path / path
        if not file_path.exists() or file_path.is_dir():
            return ""

        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "[binary or non-UTF-8 file omitted]"
        return f"+++ {path}\n{text}"

    def _count_patch_lines(self, patch: str) -> tuple[int, int]:
        additions = 0
        deletions = 0
        for line in patch.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                additions += 1
            if line.startswith("-"):
                deletions += 1
        return additions, deletions

    def _git(self, repo_path: Path, args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
