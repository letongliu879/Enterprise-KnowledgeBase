from __future__ import annotations


def deep_merge(default: dict, custom: dict) -> dict:
    merged = dict(default or {})
    for key, value in (custom or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def get_parser_config(chunk_method: str | None, parser_config: dict | None) -> dict:
    if not chunk_method:
        chunk_method = "naive"

    base_defaults = {
        "table_context_size": 0,
        "image_context_size": 0,
    }
    key_mapping = {
        "naive": {
            "layout_recognize": "DeepDOC",
            "chunk_token_num": 512,
            "delimiter": "\n",
            "auto_keywords": 0,
            "auto_questions": 0,
            "html4excel": False,
            "topn_tags": 3,
            "raptor": {
                "use_raptor": True,
                "prompt": "Please summarize the following paragraphs. Be careful with the numbers, do not make things up. Paragraphs as following:\n      {cluster_content}\nThe above is the content you need to summarize.",
                "max_token": 256,
                "threshold": 0.1,
                "max_cluster": 64,
                "random_seed": 0,
            },
            "graphrag": {
                "use_graphrag": True,
                "entity_types": ["organization", "person", "geo", "event", "category"],
                "method": "light",
                "batch_chunk_token_size": 4096,
                "retry_attempts": 2,
                "retry_backoff_seconds": 2.0,
                "retry_backoff_max_seconds": 60.0,
                "build_subgraph_timeout_per_chunk_seconds": 300,
                "build_subgraph_min_timeout_seconds": 600,
                "merge_timeout_seconds": 180,
                "resolution_timeout_seconds": 1800,
                "community_timeout_seconds": 1800,
                "lock_acquire_timeout_seconds": 600,
            },
            "parent_child": {
                "use_parent_child": False,
                "children_delimiter": "\n",
            },
        },
        "qa": {"raptor": {"use_raptor": False}, "graphrag": {"use_graphrag": False}},
        "tag": None,
        "resume": None,
        "manual": {"raptor": {"use_raptor": False}, "graphrag": {"use_graphrag": False}},
        "table": None,
        "paper": {"raptor": {"use_raptor": False}, "graphrag": {"use_graphrag": False}},
        "book": {"raptor": {"use_raptor": False}, "graphrag": {"use_graphrag": False}},
        "laws": {"raptor": {"use_raptor": False}, "graphrag": {"use_graphrag": False}},
        "presentation": {"raptor": {"use_raptor": False}, "graphrag": {"use_graphrag": False}},
        "one": None,
        "knowledge_graph": {
            "chunk_token_num": 8192,
            "delimiter": r"\n",
            "entity_types": ["organization", "person", "location", "event", "time"],
            "raptor": {"use_raptor": False},
            "graphrag": {"use_graphrag": False},
        },
        "email": None,
        "picture": None,
    }

    default_config = key_mapping[chunk_method]
    if not parser_config:
        merged_config = deep_merge(base_defaults, {} if default_config is None else default_config)
    elif default_config is None:
        merged_config = deep_merge(base_defaults, parser_config)
    else:
        merged_config = deep_merge(base_defaults, default_config)
        merged_config = deep_merge(merged_config, parser_config)

    parent_child = merged_config.get("parent_child", {})
    if parent_child.get("use_parent_child"):
        merged_config["children_delimiter"] = parent_child.get("children_delimiter", "\n")
    elif parent_child:
        merged_config["children_delimiter"] = ""

    return merged_config
