#!/usr/bin/env python3
import subprocess
from pathlib import Path

# When True, print ripgrep commands to stderr before running (set by caller)
VERBOSE_RG = False


def build_rg_exclude_args(cfg=None):
    """Return list of ripgrep `-g` args built from cfg include/exclude globs.

    If cfg contains `include_globs` those are added first, followed by
    `exclude_globs`. If cfg is None or neither key is present, returns an
    empty list.
    """
    args = []
    if not cfg:
        return args
    # backward-compatible: accept both new `ripgrep_*_patterns` keys and
    # the older `include_globs`/`exclude_globs` names
    incs = cfg.get('ripgrep_include_patterns') or cfg.get('include_globs') or []
    excs = cfg.get('ripgrep_exclude_patterns') or cfg.get('exclude_globs') or []
    for p in incs:
        args.extend(['-g', p])
    for p in excs:
        args.extend(['-g', p])
    return args


def run_ripgrep(cmd):
    if VERBOSE_RG:
        import sys
        try:
            print('rg command:', ' '.join(cmd), file=sys.stderr)
        except Exception:
            print('rg command: (failed to render)', file=sys.stderr)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode not in (0, 1):
        import sys
        # Print full debug info to stderr so callers can separate it from stdout
        try:
            print('rg command:', ' '.join(cmd), file=sys.stderr)
        except Exception:
            print('rg command: (failed to render)', file=sys.stderr)
        if p.stderr:
            print(p.stderr, file=sys.stderr)
        else:
            print('rg failed with no stderr output', file=sys.stderr)
        raise RuntimeError(p.stderr or 'rg failed')
    return [Path(x) for x in p.stdout.splitlines() if x.strip()]


def run_rg_files(root, cfg=None):
    cmd = ['rg'] + build_rg_exclude_args(cfg) + ['--files', '-g', '*.java', str(root)]
    return run_ripgrep(cmd)


def get_files(root, files_cache=None, cfg=None):
    return files_cache if files_cache is not None else run_rg_files(root, cfg)


def precompute_files_cache(cfg, root):
    # Use import include patterns (new name) or fall back to legacy whitelist_regex.
    include_pat = cfg.get('import_include_patterns') or cfg.get('whitelist_regex')
    if include_pat:
        try:
            pattern = rf'^package\s+{include_pat}'
            cmd = ['rg', '--files-with-matches', '-g', '*.java', '-e', pattern, str(root)]
            res = run_ripgrep(cmd)
            return res if res else None
        except RuntimeError:
            return None
    return None
