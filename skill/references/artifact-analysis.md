# 产物结构与标准分析顺序

## 目录结构

```
runs/<session-id>/
├── manifest.json        # session 状态（complete/incomplete）
├── raw/network/         # 请求/响应全文 + 引擎层 body + initiator 栈 + 终态自描述
├── raw/vm-loop/         # VM 执行链主产物（loops/realms/dynamic_sources/trace_seq/value_taps/counters）
├── raw/worker-source/   # Worker 源码回补
├── raw/.snapshots/      # take_snapshot 的 aria 快照
├── trace/               # PropertyTracer 原生属性事件（traces/*.jsonl + meta + control/）
└── derived/ report/ indexes/   # 分析结论写这里，绝不覆盖 raw
```

## 标准分析五步

1. **定位 VM**：`dynamic_sources` + `realms` 定位 VM 代码与所在 realm（main/iframe/worker）。worker realm 必须确认有记录，不能遗漏。
2. **还原结构**：`loops` + `counters` + `trace_seq` 裁决派发形态（switch-dispatch / handler-table / 直接跳转）。
3. **钉语义**：`trace_seq` 参数证据 + 返回值锚点 + `trace/` 原生事件交叉钉 handler 语义。
4. **追数据流**：`value_taps` 回追加密参数从采集点到请求字段的完整变换链。
5. **验证理解**：对照 `raw/network/` 全文确认离线重放所需字节齐全。

## 缺口自描述字段

所有截断/缺口都有自描述字段：`truncated`、`coverage_pct`、`worker-gap`、`serviceworker-gap` 等。

- **产物里没有的 = 能力缺口**，如实登记；
- **有但没说清可信度的也是缺口**；
- 区分「能力缺口」和「本轮目标没跑这段代码」——看产物里的活性自检字段。

## trace/ 目录

`traces/<id>.jsonl` 是事件流本体，`<id>.jsonl.meta.json` 是元数据（profile、覆盖声明、截断标记），`control/status-*.state` 是追踪生命周期状态。离线分析用 `list_trace_files` / `query_trace_file` 检索，不要手搓解析逻辑重复造轮子。

## 关联断言的证据链格式

任何「这个数据流向那个参数」的断言，必须能串出：请求 ID（`raw/network/`）+ 脚本 hash（`dynamic_sources`）+ trace 序号（`trace/traces/`）+ 调用帧。仅凭时间相近不断言数据依赖。
