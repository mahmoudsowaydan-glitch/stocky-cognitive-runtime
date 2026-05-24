# Stocky Engineering OS — Memory Recording Engine v0.1

---

> هذا الملف يحدد **محرك تسجيل الذاكرة** — المسؤول عن تخزين كل حدث تنفيذ بشكل دائم وغير قابل للتعديل.
>
> This file defines the **Memory Recording Engine** — responsible for permanently storing every execution event in an immutable, append-only format.

---

## Core Principle — المبدأ الأساسي

```
All execution records are:
  - APPEND-ONLY: لا يمكن حذف أو تعديل أي record بعد كتابته
  - IMMUTABLE: بمجرد كتابته، لا يتغير أبدًا
  - TRACEABLE: كل record له سلسلة كاملة من المصدر
  - COMPRESSIBLE: بعد فترة احتفاظ، يُضغط (لكن لا يُحذف)
```

---

## MemoryEntry Structure — هيكل مدخل الذاكرة

```yaml
MemoryEntry:
  id: string                        # Unique entry ID (UUID)
  execution_id: string              # Reference to execution
  type: Enum                        # EXECUTION_RECORD | TRACE_EVENT | CHECKPOINT | 
                                    # ANOMALY | RECOVERY | DECISION | FAILURE
  
  timestamp: datetime               # وقت التسجيل
  source: string                    # Component that created the entry
  
  data: object                      # محتوى الـ record (يعتمد على النوع)
  
  metadata: {
    version: number,                # Entry schema version
    compressed: boolean,            # هل تم ضغطه؟
    compressed_original_size: number|null,  # الحجم قبل الضغط
    parent_id: string|null,         # Reference to parent entry (for chaining)
    tags: [string]                  # Tags للبحث والتصنيف
  }
  
  signature: string                 # Hash للتحقق من التكامل (SHA-256)
                                    # signature = hash(id + timestamp + data)
```

### Entry Types — أنواع المدخلات

| Type | المحتوى | متى يُسجل |
|---|---|---|
| **EXECUTION_RECORD** | نتيجة تنفيذ كاملة | بعد COMPLETED أو FAILED |
| **TRACE_EVENT** | حدث تنفيذ فردي | أثناء EXECUTING |
| **CHECKPOINT** | Snapshot للحالة عند نقطة تفتيش | عند checkpoint |
| **ANOMALY** | إشارة شذوذ تم اكتشافها | عند اكتشاف anomaly |
| **RECOVERY** | محاولة استرداد | أثناء RECOVERING |
| **DECISION** | قرار اتخذ أثناء التنفيذ | عند أي فرع decision |
| **FAILURE** | فشل + root cause | عند أي فشل |

---

## Recording Rules — قواعد التسجيل

### Rule 1: No Overwrite — لا كتابة فوق القديم
```
Once a MemoryEntry is committed, it cannot be modified, deleted, or overwritten.
Violation → governance_verdict = BLOCK (system-level violation)
```

### Rule 2: Complete Trace — تتبع كامل
```
Every execution must produce a complete trace chain:
  Plan → Graph → Steps → Results → Outcome
Missing any link → recorded as WARNING in metadata
```

### Rule 3: Ordered Writing — كتابة مرتبة
```
Entries must be written in chronological order.
If an entry arrives out of order, it is buffered and inserted at the correct position.
Violation → WARNING in audit trail
```

### Rule 4: Integrity Check — التحقق من التكامل
```
Every entry includes a SHA-256 hash of its content.
Regular integrity checks verify that no entry has been tampered with.
Integrity failure → CRITICAL anomaly → system alert
```

---

## Storage Organization — تنظيم التخزين

```
Memory Store
├── execution_records/           # Execution-level records
│   ├── exec_{id}.mem           # Full execution record
│   └── exec_{id}.summary       # Compressed summary
├── trace_streams/               # Trace events (grouped by execution)
│   └── trace_{exec_id}.log     # Ordered trace events
├── checkpoints/                 # Checkpoint snapshots
│   └── checkpoint_{exec_id}_{step_id}.snap
├── anomalies/                   # Anomaly records
│   └── anomaly_{id}.mem
├── recovery_logs/               # Recovery attempts
│   └── recovery_{id}.mem
└── index/                       # Search indexes
    ├── by_time.idx
    ├── by_execution.idx
    ├── by_type.idx
    └── by_tag.idx
```

### Retention Policy
| Data Type | Online (Queryable) | Archive (Compressed) | Deletion |
|---|---|---|---|
| Execution Records | 90 days | 2 years | Never (permanent archive) |
| Trace Events | 30 days | 1 year | Never |
| Checkpoints | 7 days | 90 days | After 90 days |
| Anomalies | 1 year | 5 years | Never |
| Recovery Logs | 1 year | 5 years | Never |

---

## Query Capabilities — إمكانيات الاستعلام

### Supported Queries
| Query | مثال | Returns |
|---|---|---|
| By execution ID | `get_execution("exec-123")` | Full execution record + trace |
| By time range | `get_by_time(start, end)` | All entries in range |
| By type | `get_by_type("ANOMALY")` | All anomalies |
| By tag | `get_by_tag("critical")` | All entries with tag |
| Failed executions | `get_failed_executions()` | All FAILED executions |
| Integrity check | `verify_integrity("exec-123")` | Pass/fail + details |
| Execution chain | `get_chain("exec-123")` | Full trace chain |

### Query Rules
```
1. All queries are read-only — لا يمكن تعديل البيانات
2. Queries on archived data are slower (decompression required)
3. Query results are limited to 1000 entries by default
4. Complex queries must pass through Governance if over system resources
```

---

## Compression Pipeline — خط أنابيب الضغط

### Algorithm
```
1. Select entries eligible for compression (based on retention policy)
2. Remove redundant metadata
3. Compress data payload (gzip/zstd)
4. Update entry metadata: compressed = true, compressed_original_size
5. Keep index entry uncompressed for searchability
6. Verify integrity after compression
```

### Compression Ratio Targets
| Data Type | Expected Ratio |
|---|---|
| Execution Records | 5:1 |
| Trace Events | 10:1 (highly redundant) |
| Checkpoints | 3:1 |
| Anomalies | 2:1 |
| Recovery Logs | 4:1 |

---

## Integrity Verification Protocol — بروتوكول التحقق من التكامل

```
Daily scheduled integrity check:
  for each entry in active store:
    1. Recalculate hash: recalculated = SHA256(id + timestamp + data)
    2. Compare with entry.signature
    3. If mismatch → CRITICAL anomaly:
       - alert Governance Layer
       - quarantine affected entries
       - initiate recovery investigation
    4. Log check result

Monthly full store verification:
  Same process for all entries including archived
```

---

*The Memory Recording Engine is the permanent memory of Stocky Engineering OS. Its immutability guarantees auditability and trust in every execution.*

*محرك تسجيل الذاكرة هو الذاكرة الدائمة للنظام. عدم قابليته للتعديل يضمن قابلية المراجعة والثقة في كل تنفيذ.*
