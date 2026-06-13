# Phase-1 E2E 上传 → 检索 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `tests/e2e/` 下实现一条可重复运行的端到端回归套件，覆盖“web 上传 PDF → 后台解析索引 → web 检索返回证据片段”主路径及 3 个关键负向场景，并自动清理测试数据。

**Architecture:** `pytest` + `pytest-playwright` 驱动 Chromium 完成前端交互；`tests/e2e/helpers/services.py` 通过 admin/workbench API 创建/清理集合、轮询任务状态；`tests/e2e/helpers/agent_assert.py` 调用 `agent-browser` CLI 做语义断言与页面错误检查；每个测试用例拥有独立 collection，失败时保留截图。

**Tech Stack:** Python 3.12, pytest, pytest-playwright, requests, agent-browser CLI, fpdf2.

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `pyproject.toml` | 在 `dependency-groups.dev` 中增加 `pytest-playwright` 与 `fpdf2` |
| `pytest.ini` | 增加 `e2e` marker，避免 E2E 被默认单元测试误跑 |
| `tests/e2e/conftest.py` | session 级服务健康检查、function 级独立 collection fixture、认证 page fixture |
| `tests/e2e/helpers/__init__.py` | helpers 包标记 |
| `tests/e2e/helpers/services.py` | 服务 API 调用、集合 CRUD、任务轮询、API Key 同步 |
| `tests/e2e/helpers/agent_assert.py` | 通过 `agent-browser` CLI 读取页面文本/错误 |
| `tests/e2e/fixtures/generate.py` | 生成 `sample.pdf` 测试文件 |
| `tests/e2e/fixtures/invalid.txt` | 非法文件类型负向用例 |
| `tests/e2e/test_upload_retrieve.py` | 主路径与负向用例 |

---

## 前置条件

- 已安装 `agent-browser` CLI：`npm i -g agent-browser && agent-browser install`
- 本地基础设施已启动：`docker compose -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis`
- Python 服务已启动：admin `:18084`、workbench-api `:18083`、intake-pipeline `:18085`（含 document-service `:8006`）
- Java 服务已启动：access `:18181`、retrieval `:18182`
- 已存在 published retrieval profile `ret_smoke_01`（当前 smoke 数据已包含）

---

## Task 1: 增加开发依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 在 `dependency-groups.dev` 中追加 `pytest-playwright` 与 `fpdf2`**

```toml
[dependency-groups]
dev = [
    "huggingface-hub>=1.18.0",
    "jsonschema>=4.26.0",
    "olefile>=0.47",
    "pdfplumber>=0.11.9",
    "pyjwt>=2.13.0",
    "pytest>=9.0.3",
    "pytest-asyncio>=1.4.0",
    "pytest-cov>=7.1.0",
    "pytest-playwright>=0.7.0",
    "fpdf2>=2.8.3",
    "quart>=0.20.0",
    "requests>=2.34.2",
    "respx>=0.23.1",
    "scikit-learn>=1.9.0",
    "xgboost>=3.2.0",
]
```

- [ ] **Step 2: 同步依赖**

Run: `uv sync`

Expected: 无报错，`pytest-playwright` 与 `fpdf2` 安装成功。

- [ ] **Step 3: 安装 Chromium 浏览器**

Run: `playwright install chromium`

Expected: Chromium 下载完成。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(dev): add pytest-playwright and fpdf2 for e2e tests"
```

---

## Task 2: 配置 pytest marker

**Files:**
- Modify: `pytest.ini`

- [ ] **Step 1: 在 `[pytest]` 段增加 `e2e` marker**

```ini
[pytest]
markers =
    live_model: tests that require real API keys (INDEXING_CHAT_API_KEY / INDEXING_EMBEDDING_API_KEY)
    e2e: tests that drive a real browser against running services
```

- [ ] **Step 2: Commit**

```bash
git add pytest.ini
git commit -m "chore(tests): add e2e pytest marker"
```

---

## Task 3: 生成测试文件

**Files:**
- Create: `tests/e2e/fixtures/generate.py`
- Create: `tests/e2e/fixtures/invalid.txt`

- [ ] **Step 1: 创建 PDF 生成脚本**

```python
from pathlib import Path
from fpdf import FPDF

OUT_DIR = Path(__file__).parent

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "E2E Retrieval Test Document", ln=True, align="C")
        self.ln(5)

    def chapter(self, title: str, body: str):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, title, ln=True)
        self.set_font("Arial", "", 11)
        self.multi_cell(0, 6, body)
        self.ln()


def main() -> None:
    pdf = PDF()
    pdf.add_page()
    pdf.chapter(
        "Retrieval Test",
        "This document validates the enterprise knowledge pipeline. "
        "Key terms: end-to-end verification, retrieval accuracy, pipeline integrity.",
    )
    pdf.chapter(
        "Details",
        "The pipeline parses the document, builds an active index, "
        "and returns this paragraph as an evidence item when queried for pipeline verification.",
    )
    out_path = OUT_DIR / "sample.pdf"
    pdf.output(str(out_path))
    print(f"Generated {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 创建非法类型 fixture**

```bash
printf 'This is not a supported file type for upload.\n' > tests/e2e/fixtures/invalid.txt
```

- [ ] **Step 3: 生成 PDF**

Run: `uv run python tests/e2e/fixtures/generate.py`

Expected: `tests/e2e/fixtures/sample.pdf` 存在且大于 1KB。

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/fixtures/
git commit -m "test(e2e): add sample pdf and invalid file fixtures"
```

---

## Task 4: 创建服务调用 helper

**Files:**
- Create: `tests/e2e/helpers/__init__.py`
- Create: `tests/e2e/helpers/services.py`

- [ ] **Step 1: 创建 `tests/e2e/helpers/__init__.py`**

```python
"""E2E test helpers."""
```

- [ ] **Step 2: 创建 `tests/e2e/helpers/services.py`**

```python
"""Service API helpers for E2E tests."""

import time
import uuid
from typing import Any

import requests

DEMO_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJkZW1vLWFkbWluIiwiZW1haWwiOiJkZW1vQGV4YW1wbGUuY29tIiwicm9sZXMiOlsia25vd2xlZGdlX2FkbWluIiwidXBsb2FkZXIiLCJyZXZpZXdlciIsImNodW5rX2VkaXRvciJdLCJ0ZW5hbnRfaWQiOiJkZWZhdWx0IiwiYWxsb3dlZF9jb2xsZWN0aW9ucyI6WyIqIl19."
    "VbBjQ1VIoY7weiicGtnrGxi139X0XF6_iVdOjkKVqHo"
)

ADMIN_BASE = "http://127.0.0.1:18084"
WORKBENCH_BASE = "http://127.0.0.1:18083"
ACCESS_BASE = "http://127.0.0.1:18181"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {DEMO_TOKEN}",
        "Content-Type": "application/json",
    }


def health_check_all() -> dict[str, Any]:
    """Fail fast if any required service is down."""
    r = requests.get(f"{WORKBENCH_BASE}/workbench/health/all", timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data.get("all_healthy"):
        raise RuntimeError(f"Services not healthy: {data['services']}")
    return data


def create_isolated_collection() -> str:
    """Create a unique collection for one test."""
    collection_id = f"coll-e2e-{uuid.uuid4().hex[:8]}"
    payload = {
        "collection_id": collection_id,
        "tenant_id": "default",
        "name": f"E2E {collection_id}",
        "description": "Auto-created by E2E test",
        "authority_level": 0,
        "access_policy": {},
        "default_parser_profile_id": "",
        "default_retrieval_profile_id": "",
        "default_approval_policy_id": "",
    }
    r = requests.post(
        f"{ADMIN_BASE}/admin/collections",
        json=payload,
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    return collection_id


def delete_collection(collection_id: str) -> None:
    """Best-effort cleanup of the test collection."""
    r = requests.delete(
        f"{ADMIN_BASE}/admin/collections/{collection_id}",
        headers=_headers(),
        timeout=10,
    )
    if r.status_code == 404:
        return
    r.raise_for_status()


def find_upload_id_by_filename(collection_id: str, filename: str, timeout: float = 30.0) -> str:
    """Find the upload_id for a recently uploaded file."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{WORKBENCH_BASE}/workbench/tasks",
            params={
                "collection_id": collection_id,
                "sort_by": "created_at",
                "sort_order": "desc",
                "limit": "10",
            },
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        for item in r.json().get("items", []):
            if item.get("filename") == filename:
                return str(item["upload_id"])
        time.sleep(2)
    raise RuntimeError(f"Upload for {filename} not found in collection {collection_id}")


def wait_for_task_indexed(upload_id: str, timeout: float = 180.0) -> dict[str, Any]:
    """Poll task until it reaches published / indexed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{WORKBENCH_BASE}/workbench/tasks/{upload_id}",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        task = r.json()
        status = task.get("status", "")
        if status == "published":
            return task
        if status in ("failed", "rejected"):
            raise RuntimeError(f"Task {upload_id} failed: {task}")
        time.sleep(3)
    raise TimeoutError(f"Task {upload_id} did not reach published within {timeout}s")


def ensure_api_key(api_key_id: str, collection_id: str) -> str:
    """Create and sync an API key scoped to the test collection."""
    create_payload = {
        "api_key_id": api_key_id,
        "tenant_id": "default",
        "display_name": f"E2E {api_key_id}",
        "knowledge_scopes": [collection_id],
        "roles": ["knowledge_agent"],
        "debug_permission": True,
        "token_budget_limit": 10000,
    }
    r = requests.post(
        f"{ADMIN_BASE}/admin/api-keys",
        json=create_payload,
        headers=_headers(),
        timeout=10,
    )
    if r.status_code not in (200, 201):
        # If the key already exists from a previous run, ignore.
        if r.status_code != 409:
            r.raise_for_status()

    sync_payload = {
        "command_id": f"cmd-{api_key_id}",
        "trace_id": f"tr-{api_key_id}",
        "idempotency_key": f"id-{api_key_id}",
        "actor": "e2e",
        "tenant_id": "default",
        "target_type": "api_key",
        "target_id": api_key_id,
        "payload": {
            "api_key_id": api_key_id,
            "tenant_id": "default",
            "agent_type_id": "generic",
            "knowledge_scopes": [collection_id],
            "roles": ["knowledge_agent"],
            "debug_permission": True,
            "token_budget_limit": 10000,
            "state": "active",
            "projection_version": 1,
            "last_updated_at": "2026-06-07T00:00:00Z",
        },
    }
    r = requests.post(
        f"{ACCESS_BASE}/internal/api-key-projections/sync",
        json=sync_payload,
        timeout=10,
    )
    r.raise_for_status()
    return api_key_id
```

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/helpers/
git commit -m "test(e2e): add service helpers for collection lifecycle and task polling"
```

---

## Task 5: 创建 agent-browser 断言 helper

**Files:**
- Create: `tests/e2e/helpers/agent_assert.py`

- [ ] **Step 1: 创建 helper**

```python
"""Agent-browser based semantic assertions for E2E tests."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class AgentBrowserError(AssertionError):
    """Raised when agent-browser detects an unexpected page state."""


def _agent_browser_exe() -> str:
    """Resolve agent-browser executable (handles Windows .cmd wrapper)."""
    candidates = ["agent-browser"]
    if sys.platform == "win32":
        candidates.insert(0, "agent-browser.cmd")
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    raise AgentBrowserError("agent-browser CLI not found in PATH")


def _run_agent_browser(args: list[str], timeout: int = 60) -> str:
    """Run an agent-browser CLI command and return stdout."""
    cmd = [_agent_browser_exe(), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise AgentBrowserError(
            f"agent-browser {' '.join(args)} failed:\n{result.stderr or result.stdout}"
        )
    return result.stdout


def _open_with_state(url: str, state_path: Path) -> None:
    _run_agent_browser(["--state", str(state_path), "open", url])


def assert_page_contains(url: str, expected: str, state_path: Path) -> str:
    """Use agent-browser to verify a substring exists in the interactive snapshot."""
    _open_with_state(url, state_path)
    snapshot = _run_agent_browser(["snapshot", "-i"])
    if expected not in snapshot:
        raise AgentBrowserError(
            f"Expected text {expected!r} not found on {url}.\nSnapshot:\n{snapshot[:2000]}"
        )
    return snapshot


def assert_no_browser_errors(url: str, state_path: Path) -> None:
    """Use agent-browser to verify the page has no JS errors."""
    _open_with_state(url, state_path)
    raw = _run_agent_browser(["errors", "--json"])
    errors: list[dict[str, Any]] = json.loads(raw or "[]")
    if errors:
        raise AgentBrowserError(f"Browser errors on {url}: {errors}")


def assert_vitals_healthy(url: str, state_path: Path) -> dict[str, Any]:
    """Use agent-browser to fetch Core Web Vitals."""
    _open_with_state(url, state_path)
    raw = _run_agent_browser(["vitals", "--json"])
    return json.loads(raw or "{}")
```

- [ ] **Step 2: Commit**

```bash
git add tests/e2e/helpers/agent_assert.py
git commit -m "test(e2e): add agent-browser semantic assertion helper"
```

---

## Task 6: 创建 conftest.py

**Files:**
- Create: `tests/e2e/conftest.py`

- [ ] **Step 1: 创建 fixture 文件**

```python
"""Pytest fixtures for E2E browser tests."""

import pytest
from playwright.sync_api import Page

from tests.e2e.helpers.services import (
    DEMO_TOKEN,
    create_isolated_collection,
    delete_collection,
    health_check_all,
)

DEFAULT_NOTIFICATION_PREFS = {
    "site": {"upload": True, "review": True, "decision": True, "system": True},
    "email": {
        "enabled": False,
        "events": {"upload": False, "review": True, "decision": True, "system": False},
    },
    "dnd": {"enabled": False, "start": "22:00", "end": "08:00"},
}


@pytest.fixture(scope="session", autouse=True)
def _require_services() -> None:
    """Fail fast if services are not healthy."""
    health_check_all()


@pytest.fixture(scope="session")
def base_url() -> str:
    return "http://localhost:3000"


@pytest.fixture(scope="function")
def collection_id() -> str:
    """Provide an isolated collection and delete it after the test."""
    cid = create_isolated_collection()
    yield cid
    delete_collection(cid)


@pytest.fixture(scope="function")
def authenticated_page(page: Page, collection_id: str, base_url: str) -> Page:
    """Return a Playwright page authenticated and scoped to the test collection."""
    page.goto(base_url)

    store = {
        "state": {
            "currentCollectionId": collection_id,
            "accessScope": {"scope_type": "internal"},
            "demoToken": DEMO_TOKEN,
            "demoApiKey": None,
            "sidebarOpen": True,
            "uiDensity": "comfortable",
            "theme": "dark",
            "language": "zh",
            "notificationPrefs": DEFAULT_NOTIFICATION_PREFS,
        },
        "version": 0,
    }
    page.evaluate(
        "store => localStorage.setItem('ekb-workbench-store', JSON.stringify(store));",
        store,
    )
    page.context().add_cookies(
        [
            {
                "name": "ekb_workbench_token",
                "value": DEMO_TOKEN,
                "domain": "localhost",
                "path": "/",
            }
        ]
    )
    page.reload()
    return page
```

- [ ] **Step 2: Commit**

```bash
git add tests/e2e/conftest.py
git commit -m "test(e2e): add authenticated page and isolated collection fixtures"
```

---

## Task 7: 实现主路径用例

**Files:**
- Create: `tests/e2e/test_upload_retrieve.py`

- [ ] **Step 1: 编写 happy path 测试**

```python
"""Phase-1 E2E: upload PDF via web, wait for indexing, retrieve via web."""

import tempfile
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers.agent_assert import (
    assert_no_browser_errors,
    assert_page_contains,
)
from tests.e2e.helpers.services import ensure_api_key, find_upload_id_by_filename, wait_for_task_indexed

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.e2e
def test_upload_pdf_then_retrieve(authenticated_page: Page, collection_id: str) -> None:
    page = authenticated_page
    sample_pdf = FIXTURES / "sample.pdf"
    api_key_id = f"e2e-key-{collection_id.split('-')[-1]}"
    ensure_api_key(api_key_id, collection_id)

    # ---- 1. Upload via web ----
    page.goto("/upload")
    page.set_input_files('input[type="file"]', str(sample_pdf))
    expect(page.get_by_text("sample.pdf")).to_be_visible(timeout=10000)

    # ---- 2. Wait for backend indexing ----
    upload_id = find_upload_id_by_filename(collection_id, "sample.pdf")
    task = wait_for_task_indexed(upload_id, timeout=180)
    assert task.get("status") == "published"

    # UI should eventually show published status
    expect(page.get_by_text("已发布").first).to_be_visible(timeout=30000)

    # ---- 3. Retrieve via web ----
    page.goto("/retrieval")

    # Select retrieval profile
    page.locator("button").filter(has_text="选择配置").click()
    page.locator('[data-value="ret_smoke_01"]').click()

    # Fill query
    query_input = page.get_by_placeholder("输入检索查询...")
    query_input.fill("end-to-end verification pipeline integrity")

    # Submit
    page.get_by_role("button", name="检索上下文").click()

    # Wait for evidence list
    expect(page.get_by_text("检索到的证据片段")).to_be_visible(timeout=30000)

    # ---- 4. Agent-browser semantic assertions ----
    state_path = Path(tempfile.gettempdir()) / f"e2e-state-{collection_id}.json"
    page.context().storage_state(path=str(state_path))

    retrieval_url = page.url
    assert_page_contains(retrieval_url, "检索到的证据片段", state_path)
    assert_no_browser_errors(retrieval_url, state_path)

    # Sanity: at least one evidence card is rendered
    evidence_cards = page.locator("text=/Score/").count()
    assert evidence_cards > 0, "Expected at least one evidence card"
```

- [ ] **Step 2: 运行主路径测试**

Run:

```bash
uv run pytest tests/e2e/test_upload_retrieve.py::test_upload_pdf_then_retrieve -v --base-url http://localhost:3000
```

Expected: `PASSED`（前提是 intake/indexing 链路 120s 内完成）。

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_upload_retrieve.py
git commit -m "test(e2e): add happy path upload-to-retrieve test"
```

---

## Task 8: 实现负向与边界用例

**Files:**
- Modify: `tests/e2e/test_upload_retrieve.py`

- [ ] **Step 1: 追加非法文件上传测试**

在 `test_upload_retrieve.py` 末尾追加：

```python
@pytest.mark.e2e
def test_invalid_file_type_not_accepted(authenticated_page: Page) -> None:
    page = authenticated_page
    page.goto("/upload")
    page.set_input_files('input[type="file"]', str(FIXTURES / "invalid.txt"))

    # The UI filters out unsupported files, so no card should appear.
    expect(page.get_by_text("invalid.txt")).to_have_count(0, timeout=5000)
    expect(page.get_by_text("总数")).to_have_count(0, timeout=5000)
```

- [ ] **Step 2: 追加空查询测试**

```python
@pytest.mark.e2e
def test_retrieval_disabled_for_empty_query(authenticated_page: Page) -> None:
    page = authenticated_page
    page.goto("/retrieval")

    # Select retrieval profile; collection is already set via fixture.
    page.locator("button").filter(has_text="选择配置").click()
    page.locator('[data-value="ret_smoke_01"]').click()

    search_button = page.get_by_role("button", name="检索上下文")
    expect(search_button).to_be_disabled()
```

- [ ] **Step 3: 追加未索引文档检索测试**

```python
@pytest.mark.e2e
def test_retrieve_before_indexing_shows_empty_state(
    authenticated_page: Page, collection_id: str
) -> None:
    page = authenticated_page

    # The empty collection has no documents, so searching it should return no evidence.
    page.goto("/retrieval")
    page.locator("button").filter(has_text="选择配置").click()
    page.locator('[data-value="ret_smoke_01"]').click()

    page.get_by_placeholder("输入检索查询...").fill("not indexed content")
    page.get_by_role("button", name="检索上下文").click()

    # The page should not crash and should not show the evidence list header.
    expect(page.get_by_text("检索到的证据片段")).to_have_count(0, timeout=10000)
    expect(page.locator("[role='alert']")).to_have_count(0, timeout=10000)
```

- [ ] **Step 4: 运行全部测试**

Run:

```bash
uv run pytest tests/e2e/test_upload_retrieve.py -v --base-url http://localhost:3000
```

Expected: 4 tests pass（主路径 + 3 负向）。

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_upload_retrieve.py
git commit -m "test(e2e): add negative scenarios for upload and retrieval"
```

---

## Task 9: 失败截图与 trace 配置（可选但推荐）

**Files:**
- Create: `pytest.ini`（已修改，追加配置）或 `pyproject.toml`

- [ ] **Step 1: 在 `pytest.ini` 增加 Playwright 报告配置**

```ini
[pytest]
markers =
    live_model: tests that require real API keys (INDEXING_CHAT_API_KEY / INDEXING_EMBEDDING_API_KEY)
    e2e: tests that drive a real browser against running services

addopts = --tracing=retain-on-failure --screenshot=only-on-failure --video=retain-on-failure
```

- [ ] **Step 2: Commit**

```bash
git add pytest.ini
git commit -m "test(e2e): retain screenshots/videos/traces on failure"
```

---

## Task 10: 文档更新

**Files:**
- Modify: `docs/前端端侧经验.md`（追加 E2E 运行方式）
- 或新文件 `tests/e2e/README.md`

- [ ] **Step 1: 创建 `tests/e2e/README.md`**

```markdown
# E2E 测试

Phase-1 覆盖：文档上传 → 解析/索引 → 检索。

## 运行前置

1. 安装 agent-browser CLI：
   ```bash
   npm i -g agent-browser && agent-browser install
   ```
2. 启动基础设施与应用服务（详见根目录 `AGENTS.md`）。
3. 确认已存在 published retrieval profile `ret_smoke_01`。

## 运行测试

```bash
uv run pytest tests/e2e -m e2e -v --base-url http://localhost:3000
```

## 失败调试

- 失败截图/视频/trace 保留在 `test-results/`。
- 检查服务健康：`curl http://127.0.0.1:18083/workbench/health/all`
```

- [ ] **Step 2: Commit**

```bash
git add tests/e2e/README.md
git commit -m "docs(e2e): add e2e test readme"
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - 主路径上传-检索：Task 7 实现。
   - 负向/边界：Task 8 实现非法文件、空查询、未索引检索。
   - 测试隔离与清理：Task 6 `collection_id` fixture + Task 4 `delete_collection`。
   - agent-browser 断言：Task 5 + Task 7 调用。
2. **Placeholder scan:** 所有步骤均含具体代码、命令、期望结果，无 TBD/TODO。
3. **Type consistency:**
   - `collection_id` 在 fixture、helper、test 中一致为 `str`。
   - `DEMO_TOKEN` 在 helper 与 conftest 中一致。
   - `ret_smoke_01` profile ID 在测试与 helper 中一致。
4. **依赖闭环:** Task 1 安装 pytest-playwright 与 fpdf2；Task 2 安装 Chromium；Task 3 生成 fixture。
