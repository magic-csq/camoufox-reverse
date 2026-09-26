# 工作流程细节

## 分叉裁决：插桩还是被动

对未知目标，用分叉检测自动跑被动/插桩双会话再决定深入方式：

```bash
python3 ~/camoufox-reverse-browser/scripts/reverse-browser-instrumentation-divergence.py \
  --target-url <目标URL> --project-dir <绝对路径>
```

裁决口径：**aligned** 插桩透明可深采；**diverged** 目标侦测到插桩，改走被动链路；**gap** 产物不全先补采集。

## 执行循环各阶段

### 1. 定位

`navigate` 打开目标 → `network_capture(action=start, capture_body=True)` → 触发代表性操作 → `list_network_requests` 找加密请求 → `get_request_initiator` 拿生成调用链 → `scripts`/`search_code` 定位 VM/混淆代码段与所在 realm。

先列 2~5 个高信息量入口（候选加密参数、可疑 VM 文件、关键请求），再决定 trace 目标。

### 2. 采集

- 被动链路：`trace_property_access`（overview 起步）+ `vm_loop_trace`；
- 插桩透明：`hook_function`/`inject_hook_preset` 定向钩取，用完 `remove_hooks`；
- 每次 Hook/开 trace 前先写假设（"我预期看到 X，它能区分 A/B 两种可能"）。

### 3. 还原

读产物（`raw/vm-loop/`、`trace/`、`raw/network/`），按 artifact-analysis 的标准分析五步推进。同一疑点 3 次（VM/WASM 链 6 次）仍无新认知就换语义层/换入口。

### 4. 复现

把证据转成最小离线脚本；随机源/时间戳钉死后输出应与浏览器观测逐字节一致。不要自动改写浏览器全局时间和随机源——让签名函数显式接收这些值。

### 5. 验证

围绕最终交付验证，不是局部成功：A 交付 = 链路可追溯 + 离线复现脚本跑通；B/C 交付 = `verify_signer_offline` 通过。无法完成时记录事实、已尝试路径与剩余依赖，不伪造签名或成功响应。

## 停损判据（每轮结束自问）

- 连续 2 轮无新增 hook/入口/证据映射 → 换入口或换语义层；
- 被动 profile 拿不到所需语义 → 先跑分叉裁决确认插桩透明再上插桩；
- 某条路线产物显示 `gap` 连续存在 → 区分「能力缺口」还是「本轮目标没跑这段代码」（看活性自检字段），是能力缺口就如实写进报告，不要假装覆盖；
- 在 cookie setter、appendChild 这类低层 surface 之间切换**不算**真正换路线。

## 多步任务的操作节奏

- 每轮只推进一个可验证的小目标；
- 遇到凭据/验证码/高风险副作用 → 停下如实报告（这是正确行为，不是失败）；
- 用户说"继续"时从断点续跑，不从头再来——证据在 `runs/` 里都在。
