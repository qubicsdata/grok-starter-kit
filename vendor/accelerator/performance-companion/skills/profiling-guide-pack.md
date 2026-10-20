---
# <!-- perf-provenance: performance-companion v1.0.0 2026-07-03 -->
name: profiling-guide-pack
description: Import when selecting a profiling tool or advising on sampling vs instrumentation — covers runtime-to-tool mapping, flame graph interpretation, and continuous profiling decisions.
---

# Profiling Guide Pack

## Runtime-to-Tool Mapping

Use this table as the authoritative selection guide. Never recommend a tool outside the runtime column.

| Runtime | Default sampling tool | Default instrumentation tool | Allocation profiler | Continuous profiling |
|---|---|---|---|---|
| Go | pprof (net/http/pprof or runtime/pprof) | custom trace spans | pprof heap | Pyroscope, Grafana Phlare |
| Python | py-spy (zero-install, no restart) | cProfile + pstats | memory-profiler | Pyroscope |
| Python (data/ML) | Scalene (line-level CPU + memory) | line_profiler | memray | — |
| JVM (Java/Kotlin/Scala) | async-profiler | JFR (Java Flight Recorder) | JFR allocation events | Pyroscope (JVMTI), JDK Mission Control |
| Node.js | Clinic.js Doctor + Flame | `--inspect` + Chrome DevTools | Clinic.js Bubbleprof | — |
| Rust | flamegraph / cargo-flamegraph | tracing + tracing-flame | heaptrack | — |
| .NET | dotnet-trace + dotnet-counters | EventSource / DiagnosticSource | dotnet-gcdump | dotnet-monitor |
| Ruby | stackprof | rbspy | ObjectSpace | — |
| PHP | Blackfire (sampling) | Xdebug (instrumentation) | — | Blackfire |

## Sampling vs Instrumentation Decision

**Default: sampling.** Instrumentation only when sampling cannot reproduce the issue.

| When to choose sampling | When to choose instrumentation |
|---|---|
| Production environment (minimal overhead) | Exact call-count tracking required |
| Unknown hot path — discovering where time is spent | Reproducing a specific code path (not a statistical sample) |
| Intermittent latency spikes | Tracing a single request from entry to exit |
| Cannot modify code or restart process | Need custom timing annotations at known boundaries |

**Overhead guideline:** async-profiler and py-spy typically add < 2% CPU overhead at 99 Hz sampling. Instrumentation tools (Xdebug, JFR with all events) can add 20–100% overhead — never run in production without rate-limiting.

## Flame Graph Reading

A flame graph shows stack traces width-proportional to time on CPU. Reading order:

1. **Look at the widest frames at the top** — these are the actual bottlenecks, not the tall stacks below them.
2. **Ignore the bottom frames** — they are the call chain from `main` → your code; common to all traces.
3. **Distinguish CPU-on from CPU-off:** CPU-on (orange/red in typical tools) = actually executing. CPU-off / "off-CPU" (blue in Clinic.js, async_profiler async) = waiting for I/O, locks, or scheduling.
4. **Wide plateau = hot loop.** A frame spanning 30%+ of the width is spending proportional CPU time there.
5. **Narrow but tall = deep call chain without hot work** — often framework overhead; usually not the bottleneck.

## Continuous Profiling

For services with unpredictable latency spikes: deploy a continuous profiler to collect always-on low-overhead samples, correlated with traces.

- **Default**: Pyroscope (OSS, multi-language, Grafana-native)
- **Alternative**: Elastic APM continuous profiling, Datadog Continuous Profiler (managed)
- **Gate**: Only enable in production after verifying overhead < 3% on a staging environment.

## Hard Gates

**STOP if no runtime is identified** — do not recommend a profiling tool until the language/runtime is confirmed.
**DO NOT recommend instrumentation-mode tools (Xdebug, JFR full) for production without explicit overhead rate-limiting acknowledgement.**
**DO NOT recommend a cross-runtime tool** (e.g. pprof for Python) — always apply the Runtime-to-Tool Mapping table.
