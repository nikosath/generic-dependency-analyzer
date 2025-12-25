#!/usr/bin/env python3
class Renderer:
    """Render dependency trees in BFS or DFS ASCII styles."""
    def render_bfs(self, children, target):
        print(target)
        count = 0
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

    def render_dfs(self, children, target):
        print(target)
        count = 0
        seen = set([target])
        def print_subtree(parent):
            nonlocal count
            lst = children.get(parent, [])
            for idx, (lvl, child) in enumerate(lst):
                indent = '  ' * (lvl - 1)
                marker = '|- '
                print(f"{indent}{marker}{child}")
                count += 1
                if child not in seen:
                    seen.add(child)
                    print_subtree(child)

        print_subtree(target)
        return count
