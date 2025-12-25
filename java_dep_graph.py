#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path
from renderer import Renderer
import rg_runner
import parser
import finder

SCRIPT_DIR = Path(__file__).resolve().parent

def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def load_config():
    # cfg holds user-configurable regexes and ripgrep-level exclude globs
    # `exclude_globs` is a comma-separated list of ripgrep `-g` patterns
    cfg = {'whitelist_regex': '', 'blacklist_regex': '', 'include_globs': [], 'exclude_globs': []}
    cwd_cfg = Path.cwd() / 'java-dep-graph.conf'
    script_cfg = SCRIPT_DIR / 'java-dep-graph.conf'
    cfg_file = cwd_cfg if cwd_cfg.exists() else (script_cfg if script_cfg.exists() else None)
    if cfg_file:
        for line in cfg_file.read_text().splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            if line.startswith('whitelist_regex='):
                cfg['whitelist_regex'] = line.split('=',1)[1]
            elif line.startswith('blacklist_regex='):
                cfg['blacklist_regex'] = line.split('=',1)[1]
            elif line.startswith('include_globs='):
                val = line.split('=',1)[1]
                cfg['include_globs'] = [v.strip() for v in val.split(',') if v.strip()]
            elif line.startswith('exclude_globs='):
                # comma-separated list of ripgrep glob patterns, e.g. !**/test/**,!**/src/test/**
                val = line.split('=',1)[1]
                cfg['exclude_globs'] = [v.strip() for v in val.split(',') if v.strip()]
        if cfg['whitelist_regex']:
            log('Loaded whitelist regex:', cfg['whitelist_regex'])
        if cfg['blacklist_regex']:
            log('Loaded blacklist regex:', cfg['blacklist_regex'])
    return cfg

def build_rg_exclude_args(cfg=None):
    """Return a list of ripgrep `-g` args.

    Uses cfg['exclude_globs'] if present, otherwise empty list.
    """
    if cfg and cfg.get('exclude_globs'):
        args = []
        for p in cfg['exclude_globs']:
            args.extend(['-g', p])
        return args
    return []



# `run_rg_files`, `get_files` and `precompute_files_cache` moved to `rg_runner`.

# `parse_package_and_imports`, `apply_filters`, `is_test_path` moved to `parser`.

# precompute_files_cache moved to `rg_runner`.


# traversal helpers moved to `finder`.

def generate_dot(root, cfg):
    files = rg_runner.run_rg_files(root)
    edges = set()
    for f in files:
        pkg, imports, _ = parser.parse_package_and_imports(f)
        if not pkg:
            continue
        for imp in imports:
            if parser.apply_filters(imp, cfg['whitelist_regex'], cfg['blacklist_regex']):
                edges.add((pkg, imp))
    print('digraph Dependencies {')
    print('  node [shape=box, style=filled, color="#E8E8E8"];')
    for a,b in sorted(edges):
        print(f'  "{a}" -> "{b}";')
    print('}')




def find_class_file(root, target, files_cache=None, cfg=None):
    # target can be simple or fully-qualified
    if '.' in target:
        # try to find file by FQN path
        parts = target.split('.')
        cls = parts[-1]
        candidates = rg_runner.get_files(root, files_cache, cfg)
        for c in candidates:
            if c.name == cls + '.java':
                # check package
                pkg, _ = parser.parse_package_and_imports(c)
                if pkg == '.'.join(parts[:-1]):
                    return c
        return None
    else:
        candidates = [p for p in rg_runner.get_files(root, files_cache, cfg) if p.name == target + '.java']
        return candidates[0] if candidates else None

def list_imports_of_class(root, target, cfg, files_cache=None):
    file = find_class_file(root, target, files_cache=files_cache, cfg=cfg)
    if not file:
        log(f"Error: class file {target}.java not found under '{root}'.")
        sys.exit(1)
    log('Inspecting imports in:', str(file))
    _, imports, _ = parser.parse_package_and_imports(file)
    filtered = [imp for imp in sorted(set(imports)) if parser.apply_filters(imp, cfg['whitelist_regex'], cfg['blacklist_regex'])]
    for imp in filtered:
        print(imp)

def reverse_dependants(root, target_fqn, cfg, levels=0, sort_strategy=None, search='BFS', files_cache=None):
    # delegate traversal to specific BFS/DFS helper preserving existing behavior
    if search.upper() == 'DFS':
        results = finder.traverse_reverse_dfs(root, target_fqn, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)
    else:
        results = finder.traverse_reverse_bfs(root, target_fqn, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)

    # build adjacency map parent -> [children] from recorded triples
    children = {}
    seen_links = set()
    for lvl, dep, parent in results:
        link = (parent, dep)
        if link in seen_links:
            continue
        seen_links.add(link)
        children.setdefault(parent, []).append((lvl, dep))

    # If the initial target is a concrete class that implements/extends interfaces,
    # include those interfaces at the same top level as the impl and also gather
    # their reverse dependents so the interface is treated as a target too.
    # This makes the interface appear as a child of the target (level 1) and
    # shows dependents of the interface beneath it.
    target_simple = target_fqn.split('.')[-1]
    target_file = find_class_file(root, target_simple, files_cache=files_cache, cfg=cfg)
    # fallback: search all java files (ignore include_globs) to locate the class file
    if not target_file:
        try:
            all_files = rg_runner.run_ripgrep(['rg', '--files', '-g', '*.java', str(root)])
            for f in all_files:
                if f.name == target_simple + '.java':
                    pkg_try, _, _ = parser.parse_package_and_imports(f)
                    if pkg_try == '.'.join(target_fqn.split('.')[:-1]):
                        target_file = f
                        break
        except Exception:
            target_file = None
    if target_file:
        pkg, imports, related = parser.parse_package_and_imports(target_file)
        for rel in related:
            if parser.apply_filters(rel, cfg['whitelist_regex'], cfg['blacklist_regex']):
                # add the interface/superclass as a child of the target
                link0 = (target_fqn, rel)
                if link0 not in seen_links:
                    seen_links.add(link0)
                    children.setdefault(target_fqn, []).append((1, rel))
                # run reverse traversal for the interface and merge results
                if search.upper() == 'DFS':
                    extra = finder.traverse_reverse_dfs(root, rel, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)
                else:
                    extra = finder.traverse_reverse_bfs(root, rel, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)
                for lvl, dep, parent in extra:
                    link = (parent, dep)
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    children.setdefault(parent, []).append((lvl, dep))

    # apply sorting to children lists only when lexicographic sorting requested
    if sort_strategy == 'lex':
        for p in children:
            children[p].sort(key=lambda t: t[1])

    # output: first line should be the target class (no leading spaces)
    renderer = Renderer()
    if search.upper() == 'DFS':
        printed = renderer.render_dfs(children, target_fqn)
    else:
        printed = renderer.render_bfs(children, target_fqn)

    # final count: number of printed dependency lines
    print(f'Dependents found: {printed}')

def main():
    argp = argparse.ArgumentParser()
    argp.add_argument('root', nargs='?', default='.')
    argp.add_argument('target', nargs='?')
    argp.add_argument('--reverse', action='store_true')
    argp.add_argument('--levels', type=int, default=0)
    argp.add_argument('--nosort', action='store_true', help='Disable all deterministic sorting for faster traversal')
    argp.add_argument('--search', choices=['BFS','DFS'], default='BFS', help='Search strategy for reverse traversal')
    argp.add_argument('--verbose-rg', action='store_true', help='Print ripgrep commands to stderr')
    args = argp.parse_args()

    cfg = load_config()

    # enable verbose ripgrep output if requested
    if args.verbose_rg:
        rg_runner.VERBOSE_RG = True

    root = Path(args.root)
    if not root.is_dir():
        log(f"Error: directory '{root}' does not exist.")
        sys.exit(1)

    if args.target and args.reverse:
        # resolve target fqn if simple name
        target = args.target
        if '.' not in target:
            file = find_class_file(root, target)
            if not file:
                log(f"Error: class file {target}.java not found under '{root}'.")
                sys.exit(1)
            pkg, _, _ = parser.parse_package_and_imports(file)
            target_fqn = f"{pkg}.{target}" if pkg else target
        else:
            target_fqn = target
        # Determine sort strategy: default to 'lex' unless --nosort is specified
        sort_strategy = None if args.nosort else 'lex'
        # Precompute files_cache from whitelist_regex to prune file set (improves performance)
        files_cache = rg_runner.precompute_files_cache(cfg, root)

        reverse_dependants(root, target_fqn, cfg, levels=args.levels, sort_strategy=sort_strategy, search=args.search, files_cache=files_cache)
        return

    if args.target and not args.reverse:
        # when listing imports, respect whitelist prefilter if present
        files_cache = rg_runner.precompute_files_cache(cfg, root)
        list_imports_of_class(root, args.target, cfg, files_cache=files_cache)
        return

    # default: generate dot
    generate_dot(root, cfg)

if __name__ == '__main__':
    main()
