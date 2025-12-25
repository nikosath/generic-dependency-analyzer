#!/usr/bin/env python3
import re
from pathlib import Path


def parse_package_and_imports(path: Path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # package
    pkg_match = re.search(r'^\s*package\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*;', content, re.MULTILINE)
    pkg = pkg_match.group(1) if pkg_match else ''

    # imports (keep as list of FQNs)
    imports = re.findall(r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_.]*\*?)\s*;', content, re.MULTILINE)

    # build import map: simple name -> FQN, and collect wildcard packages
    import_map = {}
    wildcard_pkgs = []
    for imp in imports:
        if imp.endswith('.*'):
            wildcard_pkgs.append(imp[:-2])
        else:
            simple = imp.split('.')[-1]
            import_map[simple] = imp

    # class declaration: collect extends + implements, resolve via imports when possible
    related = []
    # Work with the header portion up to the first '{' to handle multi-line declarations
    header = content.split('{', 1)[0]
    class_match = re.search(r'\b(class|interface|enum)\b', header)

    def resolve_name(name: str) -> str:
        name = name.strip()
        if not name:
            return name
        # extract a valid Java identifier token at the end, discarding stray words
        m = re.search(r'([A-Za-z_][A-Za-z0-9_.]*)$', name)
        if not m:
            return ''
        token = m.group(1)
        if '.' in token:
            return token
        if token in import_map:
            return import_map[token]
        if wildcard_pkgs:
            return f"{wildcard_pkgs[0]}.{token}"
        if pkg:
            return f"{pkg}.{token}"
        return token


    if class_match:
        # extract extends/implements clauses from the header
        extends_m = re.search(r'extends\s+([a-zA-Z0-9_.\s,]+)', header)
        implements_m = re.search(r'implements\s+([a-zA-Z0-9_.\s,]+)', header)
        if extends_m:
            extends_str = extends_m.group(1)
            for e in re.split(r'\s*,\s*', extends_str):
                r = resolve_name(e)
                if r:
                    related.append(r)
        if implements_m:
            implements_str = implements_m.group(1)
            for i in re.split(r'\s*,\s*', implements_str):
                r = resolve_name(i)
                if r:
                    related.append(r)

    return pkg, imports, related


def apply_filters(item, whitelist, blacklist):
    if whitelist and not re.search(whitelist, item):
        return False
    if blacklist and re.search(blacklist, item):
        return False
    return True


def is_test_path(s: str) -> bool:
    return any(tok in s for tok in ('/test/', '\\test\\', '/src/test/', '\\src\\test\\'))
