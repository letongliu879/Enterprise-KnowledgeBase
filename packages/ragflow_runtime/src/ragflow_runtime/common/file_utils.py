#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import os

# 优先使用外部配置的环境变量（如 Docker 挂载的模型目录）
PROJECT_BASE = os.getenv("RAG_PROJECT_BASE") or os.getenv("RAG_DEPLOY_BASE")


def _get_default_base():
    """默认使用 package resources 目录作为项目根目录。

    小文件（JSON 配置、同义词表等）打包在 ragflow_runtime.resources 中，
    通过 importlib.resources 定位，不再依赖 upstream/ragflow 源码目录。
    模型文件（ONNX，deepdoc/）较大，不打包；需通过 RAG_PROJECT_BASE
    环境变量指向外部目录，或让代码自行从 HuggingFace 下载。
    """
    try:
        from importlib import resources
        return str(resources.files("ragflow_runtime") / "resources")
    except Exception:
        return os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir,
                os.pardir,
                "resources",
            )
        )


def get_project_base_directory(*args):
    global PROJECT_BASE
    if PROJECT_BASE is None:
        PROJECT_BASE = _get_default_base()

    if args:
        return os.path.join(PROJECT_BASE, *args)
    return PROJECT_BASE


def traversal_files(base):
    for root, ds, fs in os.walk(base):
        for f in fs:
            fullname = os.path.join(root, f)
            yield fullname
