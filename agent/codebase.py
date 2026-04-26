"""Read-only codebase indexer.

Builds a compact textual snapshot of the target repo suitable for inclusion
in a Claude prompt. Respects .gitignore via pathspec.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path

import pathspec

# File extensions considered source code
SOURCE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".swift", ".kt",
    ".md", ".toml", ".yaml", ".yml", ".json",
}

MAX_FILE_BYTES = 8_000   # truncate large files
MAX_TOTAL_CHARS = 60_000  # cap total snapshot size


@dataclass
class CodebaseIndex:
    root: Path
    files: dict[str, str] = field(default_factory=dict)  # rel_path → content

    @classmethod
    async def build(cls, repo_path: str) -> "CodebaseIndex":
        root = Path(repo_path).expanduser().resolve()
        index = cls(root=root)
        await asyncio.to_thread(index._scan)
        return index

    def _scan(self) -> None:
        ignore_spec = self._load_gitignore()
        total = 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Prune hidden dirs and common noise
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in {"node_modules", "__pycache__", ".venv", "venv"}
            ]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                rel = fpath.relative_to(self.root)
                if fpath.suffix not in SOURCE_EXTS:
                    continue
                if ignore_spec and ignore_spec.match_file(str(rel)):
                    continue
                try:
                    raw = fpath.read_text(errors="replace")
                except OSError:
                    continue
                content = raw[:MAX_FILE_BYTES]
                self.files[str(rel)] = content
                total += len(content)
                if total >= MAX_TOTAL_CHARS:
                    return

    def _load_gitignore(self) -> pathspec.PathSpec | None:
        gi = self.root / ".gitignore"
        if not gi.exists():
            return None
        return pathspec.PathSpec.from_lines("gitwildmatch", gi.read_text().splitlines())

    def summary(self) -> str:
        """Compact snapshot: file tree + truncated source content."""
        lines: list[str] = [f"Root: {self.root}", f"Files: {len(self.files)}", ""]
        for rel, content in sorted(self.files.items()):
            lines.append(f"### {rel}")
            lines.append(content[:2000])  # keep per-file portion small in summary
            lines.append("")
        return "\n".join(lines)[:MAX_TOTAL_CHARS]
