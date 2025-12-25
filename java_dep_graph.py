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
    # cfg holds user-configurable regexes and ripgrep-level include/exclude patterns
    # New keys: `ripgrep_include_patterns`, `ripgrep_exclude_patterns`,
    # `render_exclude_patterns`, `render_include_patterns`.
    # Backwards-compatible old names are still accepted when present in the file.
    cfg = {
        'import_include_patterns': '',
        'import_exclude_patterns': '',
        'whitelist_regex': '',
        'blacklist_regex': '',
        'ripgrep_include_patterns': [],
        'ripgrep_exclude_patterns': [],
        'render_exclude_patterns': '',
        'render_include_patterns': ''
    }
    cwd_cfg = Path.cwd() / 'java-dep-graph.conf'
    script_cfg = SCRIPT_DIR / 'java-dep-graph.conf'
    cfg_file = cwd_cfg if cwd_cfg.exists() else (script_cfg if script_cfg.exists() else None)
    if cfg_file:
        for line in cfg_file.read_text().splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            if line.startswith('whitelist_regex=') or line.startswith('import_include_patterns='):
                val = line.split('=',1)[1]
                cfg['import_include_patterns'] = val
                cfg['whitelist_regex'] = val
            elif line.startswith('blacklist_regex=') or line.startswith('import_exclude_patterns='):
                val = line.split('=',1)[1]
                cfg['import_exclude_patterns'] = val
                cfg['blacklist_regex'] = val
            elif line.startswith('render_exclude_patterns=') or line.startswith('render_exclude_list='):
                cfg['render_exclude_patterns'] = line.split('=',1)[1]
            elif line.startswith('render_include_patterns=') or line.startswith('render_include_list='):
                cfg['render_include_patterns'] = line.split('=',1)[1]
            elif line.startswith('ripgrep_include_patterns=') or line.startswith('include_globs='):
                val = line.split('=',1)[1]
                cfg['ripgrep_include_patterns'] = [v.strip() for v in val.split(',') if v.strip()]
            elif line.startswith('ripgrep_exclude_patterns=') or line.startswith('exclude_globs='):
                # comma-separated list of ripgrep glob patterns, e.g. !**/test/**,!**/src/test/**
                val = line.split('=',1)[1]
                cfg['ripgrep_exclude_patterns'] = [v.strip() for v in val.split(',') if v.strip()]
        if cfg['import_include_patterns']:
            log('Loaded import include patterns:', cfg['import_include_patterns'])
        if cfg['import_exclude_patterns']:
            log('Loaded import exclude patterns:', cfg['import_exclude_patterns'])
    return cfg

def build_rg_exclude_args(cfg=None):
    """Return a list of ripgrep `-g` args.
    Uses cfg['ripgrep_exclude_patterns'] (new name) or falls back to
    the older cfg['exclude_globs'] if present, otherwise empty list.
    """
    if not cfg:
        return []
    excs = cfg.get('ripgrep_exclude_patterns') or cfg.get('exclude_globs') or []
    args = []
    for p in excs:
        args.extend(['-g', p])
    return args



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
            if parser.apply_filters(imp, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
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
    filtered = [imp for imp in sorted(set(imports)) if parser.apply_filters(imp, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex'))]
    for imp in filtered:
        print(imp)

def reverse_dependants(root, target_fqn, cfg, levels=0, sort_strategy=None, search='BFS', files_cache=None):
    # delegate traversal to specific BFS/DFS helper preserving existing behavior
    # Use DFS traversal only (BFS support removed).
    results = finder.traverse_reverse_dfs(root, target_fqn, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)

    # build adjacency map parent -> [children] from recorded triples
    children = {}
    seen_links = set()
    for lvl, dep, parent in results:
        # skip self-links where parent == dep
        if parent == dep:
            continue
        link = (parent, dep)
        if link in seen_links:
            continue
        seen_links.add(link)
        children.setdefault(parent, []).append((lvl, dep))

    # If the initial target is a concrete class that implements/extends interfaces,
    # collect those interfaces as `top_extras` so they are printed as separate
    # top-level entries (not as children of the target). Also gather their
    # reverse dependents so the interface is treated as a target too.
    # If the target itself is an interface, find its implementations and add them as siblings.
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
    top_extras = []
    if target_file:
        pkg, imports, implements = parser.parse_package_and_imports(target_file)
        
        # Check if target is an interface (no 'implements' clause, but is an interface)
        is_interface = 'interface' in open(target_file, 'r', encoding='utf-8', errors='ignore').read()
        
        if is_interface:
            # Target is an interface - promote any dependents that implement it to top_extras (siblings)
            promoted_impls = []
            for lvl, dep in list(children.get(target_fqn, [])):
                dep_file = find_class_file(root, dep.split('.')[-1], files_cache=files_cache, cfg=cfg)
                if not dep_file:
                    continue
                _, _, dep_implements = parser.parse_package_and_imports(dep_file)
                if target_fqn not in dep_implements:
                    continue
                if not parser.apply_filters(dep, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                    continue
                promoted_impls.append(dep)
                if dep not in top_extras:
                    top_extras.append(dep)
                children.setdefault(dep, [])
                extra = finder.traverse_reverse_dfs(root, dep, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)
                for extra_lvl, extra_dep, extra_parent in extra:
                    if extra_parent == extra_dep:
                        continue
                    link = (extra_parent, extra_dep)
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    children.setdefault(extra_parent, []).append((extra_lvl, extra_dep))
            if promoted_impls and target_fqn in children:
                children[target_fqn] = [(lvl, dep) for lvl, dep in children[target_fqn] if dep not in promoted_impls]
        else:
            # Target is a concrete class - promote only implemented interfaces to top_extras
            for rel in implements:
                if parser.apply_filters(rel, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                    # promote the interface to top_extras instead of making it a child
                    if rel not in top_extras:
                        top_extras.append(rel)
                    children.setdefault(rel, [])
                    # run reverse traversal for the interface and merge results
                    # Always use DFS for extra traversal
                    extra = finder.traverse_reverse_dfs(root, rel, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)
                    for lvl, dep, parent in extra:
                        # skip self-links
                        if parent == dep:
                            continue
                        link = (parent, dep)
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    children.setdefault(parent, []).append((lvl, dep))

    # For every parent -> child occurrence in `children`, add the child's
    # implements/extends types as siblings under the same parent. Iterate over
    # a snapshot of `children.items()` to avoid mutation issues while adding
    # new sibling entries.
    for parent, child_list in list(children.items()):
        for lvl, dep in list(child_list):
            # find class file for dep (use fallback to full scan if needed)
            dep_simple = dep.split('.')[-1]
            dep_file = find_class_file(root, dep_simple, files_cache=files_cache, cfg=cfg)
            if not dep_file:
                try:
                    all_files = rg_runner.run_ripgrep(['rg', '--files', '-g', '*.java', str(root)])
                    for f in all_files:
                        if f.name == dep_simple + '.java':
                            pkg_try, _, _ = parser.parse_package_and_imports(f)
                            if pkg_try == '.'.join(dep.split('.')[:-1]):
                                dep_file = f
                                break
                except Exception:
                    dep_file = None
            if not dep_file:
                continue
            _, _, implements = parser.parse_package_and_imports(dep_file)
            for rel in implements:
                if not parser.apply_filters(rel, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                    continue
                # avoid self-links and duplicates; add as sibling under same parent
                if parent == rel or dep == rel:
                    continue
                link = (parent, rel)
                if link in seen_links:
                    continue
                seen_links.add(link)
                children.setdefault(parent, []).append((lvl, rel))

    # apply sorting to children lists only when lexicographic sorting requested
    # also deduplicate children lists by dep to remove any accidental repeats
    for p in list(children.keys()):
        seen_deps = set()
        new_lst = []
        for lvl, dep in children.get(p, []):
            if dep in seen_deps:
                continue
            seen_deps.add(dep)
            new_lst.append((lvl, dep))
        children[p] = new_lst

    if sort_strategy == 'lex':
        for p in children:
            children[p].sort(key=lambda t: t[1])

    # output: first line should be the target class (no leading spaces)
    renderer = Renderer(cfg.get('render_exclude_patterns'), cfg.get('render_include_patterns'))
    # Render using DFS only (BFS rendering removed).
    printed = renderer.render_dfs(children, target_fqn, top_extras=top_extras, allow_impl_pairs=True)

    # final count: number of printed dependency lines, excluding top-level extras
    top_count = len(top_extras) if 'top_extras' in locals() and top_extras else 0
    final_count = printed - top_count
    print(f'Dependents found: {final_count}')

def main():
    argp = argparse.ArgumentParser()
    argp.add_argument('root', nargs='?', default='.')
    argp.add_argument('target', nargs='?')
    argp.add_argument('--reverse', action='store_true')
    argp.add_argument('--levels', type=int, default=0)
    argp.add_argument('--nosort', action='store_true', help='Disable all deterministic sorting for faster traversal')
    # BFS support removed; DFS is the only supported search strategy now.
    # The traversal helpers remain in `finder.py` for possible future re-enable.
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

        reverse_dependants(root, target_fqn, cfg, levels=args.levels, sort_strategy=sort_strategy, files_cache=files_cache)
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
