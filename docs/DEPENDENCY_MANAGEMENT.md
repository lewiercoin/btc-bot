# Dependency Management

## Overview

This project uses `pip-tools` for deterministic dependency management:

- **`requirements.txt`**: High-level dependencies with version constraints
- **`requirements.lock`**: Lockfile with pinned transitive dependencies + SHA256 hashes
- **`.python-version`**: Python version pinning (3.12.3 = production)

## Installation

### Development (loose versions)
```bash
pip install -r requirements.txt
```

### Production (exact reproducibility)
```bash
pip install -r requirements.lock
```

This ensures:
- Exact same package versions across environments
- SHA256 hash verification for security
- Protection against supply chain attacks
- Reproducible builds

## Updating Dependencies

### 1. Update high-level dependency in requirements.txt
```bash
# Example: update requests constraint
nano requirements.txt
# Change: requests>=2.32.0,<3.0.0
# To:     requests>=2.33.0,<3.0.0
```

### 2. Regenerate lockfile
```bash
pip-compile requirements.txt --output-file=requirements.lock --generate-hashes --allow-unsafe
```

### 3. Test in development
```bash
pip install -r requirements.lock
pytest
```

### 4. Commit both files
```bash
git add requirements.txt requirements.lock
git commit -m "deps: update requests to >=2.33.0"
```

## CI/CD Integration

CI should install from lockfile for reproducibility:

```yaml
# .github/workflows/test.yml
- name: Install dependencies
  run: pip install -r requirements.lock
```

Production deployment should also use lockfile:

```bash
# On production server
pip install -r requirements.lock
```

## Python Version

The project requires **Python 3.12.3** (pinned in `.python-version`).

To check your Python version:
```bash
python --version  # Should output: Python 3.12.3
```

If using `pyenv`:
```bash
pyenv install 3.12.3
pyenv local 3.12.3  # Reads .python-version
```

## Troubleshooting

### "Package version mismatch"
Solution: Install from lockfile instead of requirements.txt:
```bash
pip install -r requirements.lock
```

### "Hash mismatch"
This indicates a potential supply chain attack or corrupted package.

Solution:
1. Regenerate lockfile: `pip-compile requirements.txt --output-file=requirements.lock --generate-hashes --allow-unsafe`
2. Compare hashes manually
3. If suspicious, investigate package on PyPI

### "Dependency conflict"
Solution:
1. Relax version constraints in requirements.txt
2. Regenerate lockfile
3. Test thoroughly

## Background

**Why lockfiles?**

Without a lockfile, `pip install -r requirements.txt` resolves dependencies at install time, which can lead to:
- Different versions across environments
- Breaking changes from transitive dependencies
- Non-reproducible builds
- Supply chain vulnerabilities

With `requirements.lock`:
- **Deterministic**: Same versions every time
- **Secure**: SHA256 hash verification
- **Traceable**: Commit lockfile to git for audit trail
- **Fast**: No dependency resolution at install time
