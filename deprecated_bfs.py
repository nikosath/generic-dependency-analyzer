#!/usr/bin/env python3
"""
Deprecated BFS implementations moved here.
Keep these functions available for backward compatibility; callers
should migrate to DFS-based APIs.
"""
import warnings
from rg_runner import build_rg_exclude_args, run_ripgrep
from parser import parse_package_and_imports, apply_filters, is_test_path
from pathlib import Path


def traverse_reverse_bfs(root, target_fqn, cfg, levels=0, sort_strategy=None, files_cache=None):
    """Original BFS traversal logic (deprecated).
    Returns list of (level, dep, parent)
    """
    warnings.warn('traverse_reverse_bfs is deprecated and moved to deprecated_bfs module', DeprecationWarning)
    seen = set([target_fqn])
    results = []
    frontier = [target_fqn]
    current_level = 0
    recorded_links = set()
    while frontier and (levels == 0 or current_level < levels):
        if sort_strategy == 'lex':
            frontier = sorted(frontier)
        next_frontier = []
        for cur in list(frontier):
            matches = find_matches_for(cur, root, cfg, files_cache, sort_strategy)
            for f in matches:
                s = str(f)
                if is_test_path(s):
                    continue
                pkg, _, implements = parse_package_and_imports(f)
                cls = f.stem
                dep = f'{pkg}.{cls}' if pkg else cls
                link = (cur, dep)
                if dep in seen:
                    # already discovered elsewhere: record the parent link but do not add to next frontier
                    if apply_filters(dep, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                        if link not in recorded_links:
                            recorded_links.add(link)
                            results.append((current_level + 1, dep, cur))
                    continue
                if not apply_filters(dep, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                    continue
                seen.add(dep)
                if link not in recorded_links:
                    recorded_links.add(link)
                    results.append((current_level + 1, dep, cur))
                next_frontier.append(dep)
                for imp in implements:
                    if imp not in seen and apply_filters(imp, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                        seen.add(imp)
                        link2 = (cur, imp)
                        if link2 not in recorded_links:
                            recorded_links.add(link2)
                            results.append((current_level + 1, imp, cur))
        if sort_strategy == 'lex':
            next_frontier = sorted(set(next_frontier))
        else:
            seen_nf = set()
            nf = []
            for x in next_frontier:
                if x not in seen_nf:
                    seen_nf.add(x)
                    nf.append(x)
            next_frontier = nf
        frontier = next_frontier
        current_level += 1
    return results


def find_matches_for(cur, root, cfg, files_cache=None, sort_strategy=None):
    # local copy of the original helper used by BFS implementation
    cur_pkg = cur.rsplit('.', 1)[0] if '.' in cur else ''
    cmd = ['rg'] + build_rg_exclude_args(cfg) + ['--files-with-matches', '-F']
    # Support new `ripgrep_include_patterns` key and fall back to old `include_globs`.
    if not (cfg and (cfg.get('ripgrep_include_patterns') or cfg.get('include_globs'))):
        cmd += ['-g', '*.java']
    cmd += ['-e', f'import {cur};']
    if cur_pkg:
        cmd += ['-e', f'import {cur_pkg}.*;']
    if files_cache:
        cmd += [str(p) for p in files_cache]
    else:
        cmd.append(str(root))
    matches = []
    try:
        matches = run_ripgrep(cmd)
    except RuntimeError:
        return []
    if sort_strategy == 'lex':
        matches = sorted(matches, key=lambda p: str(p))
    return matches


def render_bfs(children, target, top_extras=None):
    warnings.warn('render_bfs is deprecated and moved to deprecated_bfs module', DeprecationWarning)
    print(target)
    count = 0
    # print any top-level extras as their own BFS subtrees
    if top_extras:
        for extra in top_extras:
            print(extra)
            count += 1
            queue = [extra]
            while queue:
                next_queue = []
                for parent in queue:
                    for lvl, child in children.get(parent, []):
                        indent = '  ' * (lvl - 1)
                        print(f"{indent}- {child}")
                        count += 1
                        next_queue.append(child)
                queue = next_queue
    # then print target's BFS subtree as before
    queue = [target]
    while queue:
        next_queue = []
        for parent in queue:
            for lvl, child in children.get(parent, []):
                indent = '  ' * (lvl - 1)
                print(f"{indent}- {child}")
                count += 1
                next_queue.append(child)
        queue = next_queue
    return count
