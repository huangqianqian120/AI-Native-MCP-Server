"""Package a generated project directory into a ZIP file."""

import shutil
from pathlib import Path


def pack_to_zip(source_dir: Path, output_path: Path) -> Path:
    """Create a ZIP of source_dir at output_path. Returns output_path."""
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # shutil.make_archive adds .zip extension automatically
    base_path = output_path.with_suffix("")
    archive_path = shutil.make_archive(
        base_name=str(base_path),
        format="zip",
        root_dir=source_dir,
    )
    return Path(archive_path)
