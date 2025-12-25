#!/usr/bin/env python3
from rg_runner import build_rg_exclude_args, run_ripgrep
from parser import parse_package_and_imports, apply_filters, is_test_path
from pathlib import Path


def find_matches_for(cur, root, cfg, files_cache=None, sort_strategy=None):
    cur_pkg = cur.rsplit('.', 1)[0] if '.' in cur else ''
    cmd = ['rg'] + build_rg_exclude_args(cfg) + ['--files-with-matches', '-F']
    # If include_globs are not provided by cfg, fallback to searching all java files.
    if not (cfg and cfg.get('include_globs')):
        cmd += ['-g', '*.java']
    cmd += ['-e', f'import {cur};']
    if cur_pkg:
        cmd += ['-e', f'import {cur_pkg}.*;']
    if files_cache:
        cmd += [str(p) for p in files_cache]
    else:
        cmd.append(str(root))
    try:
        matches = run_ripgrep(cmd)
    except RuntimeError as e:
        import sys
        print('rg error:', str(e), file=sys.stderr)
        return []
    if sort_strategy == 'lex':
        matches = sorted(matches, key=lambda p: str(p))
    return matches


def traverse_reverse_dfs(root, target_fqn, cfg, levels=0, sort_strategy=None, files_cache=None):
    seen = set([target_fqn])
    results = []  # list of (level, dep, parent)
    recorded_links = set()
    stack = [(target_fqn, 0)]
    while stack:
        cur, depth = stack.pop()
        if levels and depth >= levels:
            continue
        matches = find_matches_for(cur, root, cfg, files_cache, sort_strategy)
        if sort_strategy == 'lex':
            iter_matches = list(reversed(matches))
        else:
            iter_matches = matches
        for f in iter_matches:
            s = str(f)
            if is_test_path(s):
                continue
            pkg, _, implements = parse_package_and_imports(f)
            cls = f.stem
            dep = f'{pkg}.{cls}' if pkg else cls
            link = (cur, dep)
            if dep in seen:
                # already discovered elsewhere: record the parent link but do not traverse again
                if apply_filters(dep, cfg['whitelist_regex'], cfg['blacklist_regex']):
                    if link not in recorded_links:
                        recorded_links.add(link)
                        results.append((depth + 1, dep, cur))
                continue
            if not apply_filters(dep, cfg['whitelist_regex'], cfg['blacklist_regex']):
                continue
            seen.add(dep)
            if link not in recorded_links:
                recorded_links.add(link)
                results.append((depth + 1, dep, cur))
            stack.append((dep, depth + 1))
            for imp in implements:
                if imp not in seen and apply_filters(imp, cfg['whitelist_regex'], cfg['blacklist_regex']):
                    seen.add(imp)
                    link2 = (cur, imp)
                    if link2 not in recorded_links:
                        recorded_links.add(link2)
                        results.append((depth + 1, imp, cur))
                    stack.append((imp, depth + 1))
    return results


def traverse_reverse_bfs(root, target_fqn, cfg, levels=0, sort_strategy=None, files_cache=None):
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
                    if apply_filters(dep, cfg['whitelist_regex'], cfg['blacklist_regex']):
                        if link not in recorded_links:
                            recorded_links.add(link)
                            results.append((current_level + 1, dep, cur))
                    continue
                if not apply_filters(dep, cfg['whitelist_regex'], cfg['blacklist_regex']):
                    continue
                seen.add(dep)
                if link not in recorded_links:
                    recorded_links.add(link)
                    results.append((current_level + 1, dep, cur))
                next_frontier.append(dep)
                # Record implements/extends as dependents but do not enqueue them
                # for BFS traversal to avoid cyclic/explosive expansion.
                for imp in implements:
                    if imp not in seen and apply_filters(imp, cfg['whitelist_regex'], cfg['blacklist_regex']):
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
