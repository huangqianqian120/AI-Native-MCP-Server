from __future__ import annotations
"""Write rendered files to a temporary output directory."""

from pathlib import Path


class FileWriter:
    """Manages writing generated project files to a temp directory."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.written: list[str] = []

    def write(self, relative_path: str, content: str) -> str:
        """Write content to output_dir/relative_path. Returns full path."""
        full_path = self.output_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        self.written.append(relative_path)
        return str(full_path)

    def copy_static(self, relative_path: str, content: str) -> str:
        """Copy a static file (no template injection). Same as write."""
        return self.write(relative_path, content)

    @property
    def file_count(self) -> int:
        return len(self.written)

    def get_tree(self) -> str:
        """Return a simple tree string for logging."""
        lines = [f"📁 {self.output_dir.name}/"]
        for p in sorted(self.written):
            depth = p.count("/")
            prefix = "  " * depth + "├── "
            lines.append(f"{prefix}{p.split('/')[-1]}")
        return "\n".join(lines)
