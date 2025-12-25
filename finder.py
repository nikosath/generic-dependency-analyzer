#!/usr/bin/env python3
from rg_runner import build_rg_exclude_args, run_ripgrep
import rg_runner
from parser import parse_package_and_imports, apply_filters, is_test_path
from pathlib import Path
import sys


def find_matches_for(cur, root, cfg, files_cache=None, sort_strategy=None):
    cur_pkg = cur.rsplit('.', 1)[0] if '.' in cur else ''
    cmd = ['rg'] + build_rg_exclude_args(cfg) + ['--files-with-matches', '-F']
    # If ripgrep include patterns are not provided by cfg, fallback to searching all java files.
    # Support old `include_globs` key for backward compatibility.
    if not (cfg and (cfg.get('ripgrep_include_patterns') or cfg.get('include_globs'))):
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
                if apply_filters(dep, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                    if link not in recorded_links:
                        recorded_links.add(link)
                        results.append((depth + 1, dep, cur))
                continue
            if not apply_filters(dep, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                continue
            seen.add(dep)
            if link not in recorded_links:
                recorded_links.add(link)
                results.append((depth + 1, dep, cur))
            stack.append((dep, depth + 1))
            
            # If this is an implementation class, look for its interface and add both as siblings
            if dep.endswith('Impl') or dep.endswith('OperationImpl'):
                # Get the file for this implementation to find what interface it implements
                try:
                    impl_simple_name = dep.split('.')[-1]
                    all_files = rg_runner.run_ripgrep(['rg', '--files', '-g', '*.java', str(root)])
                    for f in all_files:
                        if f.name == impl_simple_name + '.java':
                            impl_pkg, _, impl_implements = parse_package_and_imports(f)
                            # For each interface this implementation implements, add it as a sibling at same level
                            for interface in impl_implements:
                                if interface not in seen and apply_filters(interface, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                                    seen.add(interface)
                                    # Add interface as sibling of implementation (same parent, same depth)
                                    interface_link = (cur, interface)
                                    if interface_link not in recorded_links:
                                        recorded_links.add(interface_link)
                                        results.append((depth + 1, interface, cur))
                                    # Also traverse the interface for its own dependents
                                    stack.append((interface, depth + 1))
                            break
                except Exception as e:
                    print(f'Error searching for interfaces of {dep}: {e}', file=sys.stderr)
            
            # If this is an interface, look for its implementations by searching for class files
            elif not dep.endswith('Impl') and not dep.endswith('OperationImpl'):
                impl_simple_name = dep.split('.')[-1] + 'Impl'
                # Search for implementation class files
                try:
                    all_files = rg_runner.run_ripgrep(['rg', '--files', '-g', '*.java', str(root)])
                    for f in all_files:
                        if f.name == impl_simple_name + '.java':
                            impl_pkg, _, impl_implements = parse_package_and_imports(f)
                            impl_fqn = f'{impl_pkg}.{impl_simple_name}' if impl_pkg else impl_simple_name
                            
                            # Check if this implementation implements our interface
                            if dep in impl_implements:
                                if impl_fqn not in seen and apply_filters(impl_fqn, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                                    seen.add(impl_fqn)
                                    impl_link = (cur, impl_fqn)
                                    if impl_link not in recorded_links:
                                        recorded_links.add(impl_link)
                                        results.append((depth + 1, impl_fqn, cur))
                                    stack.append((impl_fqn, depth + 1))
                except Exception as e:
                    print(f'Error searching for implementations of {dep}: {e}', file=sys.stderr)
            
            for imp in implements:
                if imp not in seen and apply_filters(imp, cfg.get('import_include_patterns') or cfg.get('whitelist_regex'), cfg.get('import_exclude_patterns') or cfg.get('blacklist_regex')):
                    seen.add(imp)
                    link2 = (cur, imp)
                    if link2 not in recorded_links:
                        recorded_links.add(link2)
                        results.append((depth + 1, imp, cur))
                    stack.append((imp, depth + 1))
    return results


def traverse_reverse_bfs(root, target_fqn, cfg, levels=0, sort_strategy=None, files_cache=None):
    # Deprecated: delegate to deprecated_bfs module but keep wrapper for
    # backwards compatibility.
    import warnings
    warnings.warn('finder.traverse_reverse_bfs is deprecated; use finder.traverse_reverse_dfs', DeprecationWarning)
    from deprecated_bfs import traverse_reverse_bfs as _bfs
    return _bfs(root, target_fqn, cfg, levels=levels, sort_strategy=sort_strategy, files_cache=files_cache)
