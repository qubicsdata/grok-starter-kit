# Behavioral Scenarios — memory-companion v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 11 scenarios (MW-01–06, MR-01–05)

---

## memory-writer Scenarios (MW-01 – MW-06)

### MW-01 — Happy path: new entry written

**Input:** namespace="my-plugin", key="last-run", value="success".

**Expected behavior:**
- Validates namespace and key against regex
- Resolves path: .ai-memory/my-plugin/last-run.json
- Validates path is inside .ai-memory/
- Creates .ai-memory/my-plugin/ if not exists
- Writes entry atomically (temp + rename)
- Returns MEMORY_OK

**Pass condition:** .ai-memory/my-plugin/last-run.json exists with all 5 fields. MEMORY_OK returned.

---

### MW-02 — Overwrite existing entry: succeeds

**Input:** namespace="my-plugin", key="last-run", value="new-value". Entry already exists.

**Expected behavior:** Overwrites atomically. Returns MEMORY_OK.

**Pass condition:** Entry updated with new value and ts. MEMORY_OK returned.

---

### MW-03 — Invalid namespace format: rejected

**Input:** namespace="My Plugin!", key="test", value="x".

**Expected behavior:** Agent rejects — namespace fails `^[a-z0-9_-]+$`. Returns `MEMORY_REJECTED: invalid namespace format`.

**Pass condition:** MEMORY_REJECTED returned. No file written.

---

### MW-04 — Invalid key format: rejected

**Input:** namespace="valid", key="bad/key/../escape", value="x".

**Expected behavior:** Agent rejects — key fails `^[a-z0-9_.-]+$` (contains `/`). Returns `MEMORY_REJECTED: invalid key format`.

**Pass condition:** MEMORY_REJECTED returned. No file written.

---

### MW-05 — Path escape via namespace: rejected

**Input:** namespace="valid", key="key", value="x". After joining, resolved path is outside .ai-memory/.

**Expected behavior:** realpath check detects escape. Returns `MEMORY_REJECTED: path escape attempt`.

**Pass condition:** MEMORY_REJECTED returned. No file written.

---

### MW-06 — $ARGUMENTS injection in value: stored verbatim

**Input:** namespace="ns", key="k", value="'; rm -rf /". Value is a label string, not executed.

**Expected behavior:** Value stored verbatim in JSON. No shell execution of value content.

**Pass condition:** .ai-memory/ns/k.json exists with value field = "'; rm -rf /". No shell execution.

---

## memory-reader Scenarios (MR-01 – MR-05)

### MR-01 — Happy path: read existing entry by key

**Input:** namespace="my-plugin", key="last-run". Entry exists.

**Expected behavior:** Agent validates namespace/key, resolves path, reads .ai-memory/my-plugin/last-run.json, returns full entry JSON.

**Pass condition:** Full entry JSON returned with all 5 fields.

---

### MR-02 — List all keys in namespace

**Input:** namespace="my-plugin", key empty/omitted.

**Expected behavior:** Agent lists all .json files in .ai-memory/my-plugin/. Returns key names (filename without .json extension).

**Pass condition:** List of key names returned. No file contents returned.

---

### MR-03 — Fuzzy search across all namespaces

**Input:** namespace empty/omitted, key empty/omitted, search="last-run".

**Expected behavior:** Agent searches all .json files under .ai-memory/ for key or value containing "last-run". Returns matching entries.

**Pass condition:** All matching entries returned (namespace, key, value, ts shown). No non-matching entries.

---

### MR-04 — Missing entry: MEMORY_NOT_FOUND

**Input:** namespace="my-plugin", key="nonexistent".

**Expected behavior:** .ai-memory/my-plugin/nonexistent.json does not exist. Returns `MEMORY_NOT_FOUND: my-plugin/nonexistent`.

**Pass condition:** MEMORY_NOT_FOUND returned. No crash.

---

### MR-05 — $ARGUMENTS path injection: rejected

**Input:** namespace="valid", key="../../etc/passwd".

**Expected behavior:** Key fails `^[a-z0-9_.-]+$` validation. Returns `MEMORY_REJECTED: invalid key format`.

**Pass condition:** MEMORY_REJECTED returned. No file system traversal.

---
