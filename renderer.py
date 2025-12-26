#!/usr/bin/env python3
import re
import sys


class Renderer:
    """Render dependency trees in BFS or DFS ASCII styles.

    The renderer no longer reads configuration files itself. The caller
    (the application's entry point) must load configuration and may pass
    optional comma-separated regex lists via the constructor.
    """

    def __init__(self, render_exclude_patterns: str | None = None, render_include_patterns: str | None = None):
        # parse comma-separated regex lists
        self._exclude_res = []
        self._include_res = []
        if render_exclude_patterns:
            for part in [p.strip() for p in render_exclude_patterns.split(',') if p.strip()]:
                try:
                    self._exclude_res.append(re.compile(part))
                except re.error:
                    # ignore invalid patterns
                    continue
        if render_include_patterns:
            for part in [p.strip() for p in render_include_patterns.split(',') if p.strip()]:
                try:
                    self._include_res.append(re.compile(part))
                except re.error:
                    continue

        # legacy default exclude pattern when no includes/excludes configured
        if not self._exclude_res and not self._include_res:
            self._exclude_res.append(re.compile(r'(?:Impl$|\.Impl\.)'))

    def render_bfs(self, children, target, top_extras=None):
        # Deprecated: delegate to deprecated_bfs.render_bfs
        import warnings
        warnings.warn('Renderer.render_bfs is deprecated; use DFS rendering', DeprecationWarning)
        from deprecated_bfs import render_bfs as _render_bfs
        return _render_bfs(children, target, top_extras=top_extras)

    def render_dfs(
        self,
        children: dict[str, list[tuple[int, str]]],
        target: str,
        top_extras: list[str] | None = None,
        allow_impl_pairs: bool = False,
    ) -> int:
        """Render DFS tree respecting include/exclude patterns and implementation rules."""
        print(target)
        count = 0
        seen: set[str] = {target}

        def print_subtree(parent: str):
            nonlocal count
            lst = children.get(parent, [])
            for idx, (lvl, child) in enumerate(lst):
                # Inclusion/exclusion logic:
                # - If include patterns are configured: render only if any include matches.
                # - Otherwise, skip a node if any exclude pattern matches.
                # - Exception: if allow_impl_pairs is True and this is an implementation that has its interface as a sibling, allow it
                should_exclude = False
                if self._include_res:
                    if not any(r.search(child) for r in self._include_res):
                        should_exclude = True
                else:
                    if any(r.search(child) for r in self._exclude_res):
                        should_exclude = True
                if should_exclude and allow_impl_pairs and child.endswith('Impl'):
                    interface_name = child[:-4]
                    interface_found = False
                    for check_parent, check_children in children.items():
                        for check_lvl, check_child in check_children:
                            if check_child == interface_name:
                                interface_found = True
                                break
                        if interface_found:
                            break
                    
                    direct_dependent = True
                    
                    if interface_found or direct_dependent or (parent == target and child.endswith('Impl')):
                        should_exclude = False
                
                if should_exclude:
                    continue

                indent = '  ' * (lvl - 1)
                marker = f'{lvl}- '
                print(f"{indent}{marker}{child}")
                count += 1
                if child not in seen:
                    seen.add(child)
                    print_subtree(child)

        # print any top_extras as separate top-level subtrees (no prefix on the extra itself)
        if top_extras:
            for extra in top_extras:
                print(extra)
                count += 1
                if extra not in seen:
                    seen.add(extra)
                    print_subtree(extra)

        print_subtree(target)
        return count
