# approval-service 模块设计

> 规范性状态：子服务历史设计文档，非最终架构入口。
>
> 本文只能用于理解 `approval-service` 的历史职责和旧实现意图。最终 intake-pipeline 边界、发布事实源、生命周期、manual review 退场规则以 [docs/上游机制移植总览.md](/E:/AI/My-Project/Reality-RAG/docs/上游机制移植总览.md) 和 [../intake-pipeline.md](/E:/AI/My-Project/Reality-RAG/services/intake-pipeline/intake-pipeline.md) 为准。
>
> `approval-service` 只拥有 approval ticket、approval decision 和审批审计，不拥有 `published_documents`、`documents`、`document_policies`、indexing job 或检索可见性。人工 approve/reject/return 只能形成 decision；发布、撤回、归档、reindex 必须进入 publishing domain 或 indexing owner 的正式 command/event。

## 定位

独立的内容治理与人工拍板服务。接收 ingestion-worker 产出的候选文档，由人工确认标签和发布决定，再通知下游执行入库。

## 为什么独立

| 职责 | ingestion-worker | approval-service |
|------|------------------|------------------|
| 核心能力 | 文件转换、质量评分、AI 审核 | 工单流转、人工决策、标签治理 |
| 决策主体 | AI + 规则 | 人（默认）/ 人配置的规则 |
| 响应时间 | 秒级（流水线） | 小时级甚至天级（等人点按钮）|
| 失败模式 | 技术失败 | 人还没看 |

两者生命周期完全不同，不能放在同一个服务里。

## 输入 → 内部 → 输出

### 输入

| 来源 | 内容 |
|------|------|
| **ingestion-worker** | `IngestionJob` 完成后，把「待确认文档」推送过来：候选标签（规则+AI）、质量报告、AI 审核意见、建议发布状态 |
| **admin 界面/CLI** | 人工拍板指令：确认标签、批准/拒绝/打回、备注 |
| **配置** | Collection 级自动放行规则（人工可选配置） |

**接口定义：**

```python
class ApprovalTicket(BaseModel):
    ticket_id: str
    doc_id: str
    collection_id: str
    job_id: str
    status: "pending" | "approved" | "rejected" | "returned"
    
    # 来自 ingestion-worker 的候选数据
    candidate_tags: list[DocumentTag]      # 规则标签 + AI 标签
    suggested_publish_status: PublishStatus  # DecisionStage 的建议
    quality_report: QualityReport
    agent_review: AgentReview
    
    # 人工拍板结果
    confirmed_tags: list[DocumentTag] | None
    approver_id: str | None
    notes: str | None
    decided_at: datetime | None
```

```python
# ingestion-worker 调用
POST /internal/approval/submit
{
  "doc_id": "doc-contract-abc-v1",
  "collection_id": "finance",
  "job_id": "ingest-xxxx",
  "candidate_tags": [
    {"tag": "contract", "source": "rule", "confidence": 1.0},
    {"tag": "supplier_agreement", "source": "ai", "confidence": 0.87},
    {"tag": "gdpr", "source": "ai", "confidence": 0.62}
  ],
  "suggested_publish_status": "PUBLISHED",
  "quality_report": {...},
  "agent_review": {...}
}

# 返回 ticket_id，文档状态变为 AWAITING_APPROVAL
```

### 内部

**两层决策机制：**

```
ingestion-worker 提交候选
        │
        ▼
[自动规则检查] ──命中且人工没开强制确认──► 直接批准 ──► 通知入库
        │
        │ 未命中，或人工强制确认
        ▼
[生成工单，状态=PENDING]
        │
        ▼
[Admin 队列等待人工]
        │
        ├──► 人工确认标签（可删可补）
        ├──► 人工选发布状态（可覆盖 AI 建议）
        └──► 提交拍板
                    │
                    ├──► 批准 ──► 通知 ingestion-worker / indexing-service 执行入库
                    ├──► 拒绝 ──► 通知清理临时资产
                    └──► 打回 ──► 通知 ingestion-worker 重跑（如需要转换修复）
```

**默认行为：人工拍板。**

每个 Collection 可配置：
```python
class ApprovalPolicy(BaseModel):
    default_mode: "manual" | "auto" = "manual"
    auto_approve_rules: list[AutoApproveRule]  # 只有 mode=auto 时生效
    require_tag_confirmation: bool = True      # 即使 auto，是否仍要人工确认标签
```

### 输出

| 结果 | 行为 | 通知对象 |
|------|------|---------|
| **approved** | 携带确认后的标签和发布状态，执行入库 | ingestion-worker（继续 Asset+Persist）或 indexing-service |
| **rejected** | 清理该文档的临时 sidecar 资产 | ingestion-worker / 调度器 |
| **returned** | 标记为需修复，可附带回传指令 | ingestion-worker（重跑某 Stage）|

```python
# approval-service 回调 ingestion-worker
POST /internal/ingestion/continue
{
  "doc_id": "doc-contract-abc-v1",
  "ticket_id": "apv-xxxx",
  "action": "approve",  # approve | reject | return
  "confirmed_tags": ["contract", "supplier_agreement"],
  "publish_status": "PUBLISHED",
  "approver_id": "user-123",
  "notes": "确认不含 GDPR 条款"
}
```

## 数据流全景

```
[运维人员上传文件]
        │
        ▼
ingestion-worker（技术流水线）
  Conversion → Dedup → Version → Quality → Review → Decision
        │
        │ 产出候选文档 + 建议
        ▼
approval-service（人工拍板）
  提交 ──► 规则检查 ──► 工单生成 ──► 人工确认
        │                          │
        │ 命中自动规则               ▼
        │                    [Admin 界面]
        │                          │
        └──► 直接批准 ◄────────────┘
                 │
                 ▼
ingestion-worker / indexing-service（执行入库）
```

## 模块边界

| 责任 | approval-service 不管 | approval-service 专管 |
|------|----------------------|----------------------|
| 文件转换 | ✅ ingestion-worker | ❌ |
| 质量评分 | ✅ ingestion-worker | ❌ |
| AI 审核 | ✅ ingestion-worker | ❌ |
| 生成候选标签 | ✅ ingestion-worker（规则+AI） | ❌ |
| **标签确认/修正** | ❌ | ✅ approval-service |
| **发布拍板** | ❌ | ✅ approval-service |
| **工单生命周期** | ❌ | ✅ approval-service |
| 实际写库/写索引 | ❌（发指令） | ✅（决策） |

## 关键状态

```
AWAITING_APPROVAL（ingestion-worker 设置）
        │
        ├──► PENDING（approval-service 生成工单）
        │       │
        │       ├──► APPROVED ──► ingestion-worker 继续 Asset+Persist
        │       ├──► REJECTED ──► 清理临时资产
        │       └──► RETURNED ──► 打回 ingestion-worker 重处理
        │
        └──►（若配置 auto 且命中规则）跳过 PENDING，直接 APPROVED
```

## 一句话

> **approval-service 是 ingestion-worker 的「刹车片」。默认所有文档到这里停下等人拍板，除非人明确说「这类不用问我」。人工拍板的是标签对不对、能不能发，拍完后通知技术侧继续执行。**
