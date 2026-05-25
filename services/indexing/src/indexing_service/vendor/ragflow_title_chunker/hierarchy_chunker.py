from __future__ import annotations

#
# Adapted from RAGFlow title_chunker/hierarchy_chunker.py under Apache 2.0.
#

from indexing_service.vendor.ragflow_title_chunker.common import BODY_LEVEL, resolve_target_level


class _ChunkNode:
    def __init__(self, level: int, title_indexes: list[int] | None = None, body_indexes: list[int] | None = None):
        self.level = level
        self.title_indexes = title_indexes or []
        self.body_indexes = body_indexes or []
        self.children: list[_ChunkNode] = []

    def add_child(self, child: "_ChunkNode") -> None:
        self.children.append(child)

    def add_body_index(self, index: int) -> None:
        self.body_indexes.append(index)

    def build_tree(self, indexed_lines: list[tuple[int, int]], depth: int) -> "_ChunkNode":
        stack = [self]
        for level, index in indexed_lines:
            if level > depth:
                stack[-1].add_body_index(index)
                continue
            while len(stack) > 1 and level <= stack[-1].level:
                stack.pop()
            node = _ChunkNode(level, title_indexes=[index])
            stack[-1].add_child(node)
            stack.append(node)
        return self

    def get_paths(self, depth: int, include_heading_content: bool) -> list[list[int]]:
        chunk_paths: list[list[int]] = []
        self._dfs(chunk_paths, [], depth, include_heading_content)
        return chunk_paths

    def _dfs(self, chunk_paths: list[list[int]], titles: list[int], depth: int, include_heading_content: bool) -> None:
        if self.level == 0 and self.body_indexes:
            chunk_paths.append(titles + self.body_indexes)

        if include_heading_content:
            path_titles = titles + self.title_indexes if 1 <= self.level <= depth else titles
            if self.body_indexes and 1 <= self.level <= depth:
                chunk_paths.append(path_titles + self.body_indexes)
            elif not self.children and 1 <= self.level <= depth:
                chunk_paths.append(path_titles)
        else:
            path_titles = titles + self.title_indexes + self.body_indexes if 1 <= self.level <= depth else titles
            if not self.children and 1 <= self.level <= depth:
                chunk_paths.append(path_titles)

        for child in self.children:
            child._dfs(chunk_paths, path_titles, depth, include_heading_content)


def hierarchy_record_groups(
    records: list[dict[str, object]],
    levels: list[int],
    *,
    hierarchy: int,
    include_heading_content: bool = False,
) -> list[list[dict[str, object]]]:
    target_level = resolve_target_level(levels, hierarchy)
    if target_level is None:
        return [records] if records else []

    indexed_lines = list(zip(levels, range(len(records))))
    root = _ChunkNode(0)
    root.build_tree(indexed_lines, target_level)
    paths = root.get_paths(target_level, include_heading_content)

    result: list[list[dict[str, object]]] = []
    for path in paths:
        chunk = [records[index] for index in path if levels[index] < BODY_LEVEL or levels[index] == BODY_LEVEL]
        if chunk:
            result.append(chunk)
    return result
