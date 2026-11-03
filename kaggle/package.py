"""Offline validation and command rendering only. Never launches a kernel."""
import argparse
import json
import re
import shlex
import os
from pathlib import Path


# A tripwire, not a substitute for auditor review. Never echo matched values.
SECRET_PATTERNS = (
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|KGAT_[A-Za-z0-9_-]{16,})",
    r"\bAKIA[A-Z0-9]{16}\b",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"(?i)[\"']?(?:kaggle_key|kaggle_api_token|api_key|access_token|auth_token|password|token|key)[\"']?\s*[:=]\s*[\"'][^\"'\r\n]{8,}[\"']",
    r"(?i)authorization\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._-]{8,}",
    r"https?://[^\s/@]+:[^\s/@]+@",
)


def secret_scan(text):
    """Return pattern identifiers only; secret material must never enter logs."""
    return [f"pattern-{i + 1}" for i, pattern in enumerate(SECRET_PATTERNS)
            if re.search(pattern, text)]


def validate_job_spec(directory):
    root = Path(directory).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Job spec must be a directory")
    # Scan every bundled file, including metadata and incidental attachments.
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Job spec must not contain symlinks or escaped paths")
        if path.is_file() and secret_scan(path.read_bytes().decode('utf-8', errors='replace')):
            raise ValueError(f"Secret-scan tripwire in {path.relative_to(root)}")
    metadata = json.loads((root / 'kernel-metadata.json').read_text(encoding='utf-8'))
    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a JSON object")
    code_file = metadata.get('code_file')
    if not isinstance(code_file, str) or not code_file:
        raise ValueError("Metadata must name code_file")
    script = (root / code_file).resolve()
    if not script.is_relative_to(root) or not script.is_file():
        raise ValueError("code_file must exist inside the job spec")
    if metadata.get('language') != 'python' or metadata.get('kernel_type') != 'script':
        raise ValueError("Expected a Python script kernel")
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+', metadata.get('id', '')):
        raise ValueError("Metadata needs an owner/kernel id")
    return metadata


def push_command(directory, krun='krun.py'):
    validate_job_spec(directory)
    # External krun.py owns account selection/authentication. No credentials here.
    argv = ['python', str(krun), 'kernels', 'push', '-p', str(Path(directory).resolve())]
    if os.name == 'nt':
        # PowerShell single quotes prevent variable/command interpolation.
        return ' '.join(arg if re.fullmatch(r'[A-Za-z0-9_./:\\-]+', arg)
                        else "'" + arg.replace("'", "''") + "'" for arg in argv)
    return shlex.join(argv)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_spec', type=Path)
    parser.add_argument('--krun', type=Path, default=Path('krun.py'))
    args = parser.parse_args()
    try:
        print(push_command(args.job_spec, args.krun))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Package validation failed: {exc}\n')


if __name__ == '__main__':
    main()
