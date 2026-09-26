# MCP 工具参考（36 个工具，reverse.9 契约）

工具清单：`launch_browser, close_browser, navigate, reload, take_screenshot, take_snapshot, click, type_text, wait_for, get_page_info, reset_browser_state, scripts, search_code, evaluate_js, hook_function, inject_hook_preset, remove_hooks, get_console_logs, network_capture, list_network_requests, get_network_request, get_request_initiator, intercept_request, cookies, get_storage, export_state, import_state, hook_jsvmp_interpreter, compare_env, instrumentation, check_environment, verify_signer_offline, trace_property_access, list_trace_files, query_trace_file, vm_loop_trace`

调用前先跑 `check_environment`：它会校验 MCP 版本、依赖（esprima 等）和浏览器 selector `whitenightshadow/152.0.4-beta.30-reverse.9` 的安装状态与能力契约。

## 浏览器生命周期

- `launch_browser(project_dir, headless, browser_version, enable_trace, trace_profile, proxy)`：每次默认新建隔离 session（`runs/<session-id>/`）。`enable_trace=True`（默认）启用引擎层 PropertyTracer；`trace_profile` 三档 `overview`（被动首选）→ `targeted` → `deep`，开销递增。
- `close_browser`：收尾时调用，返回 session 的 `artifacts` 索引与 `capture` 自描述（含 `capabilities` 边界声明与 `errors` 列表）。`status=incomplete` 不是失败——读 `capture.errors` 判断真实缺口（例如重定向响应无 body 是浏览器固有限制）；`mcp_capture_gaps` 为 0 表示采集链路无损。
- `reset_browser_state`：清状态但**换指纹上下文**——整条任务尽量不用。

## 网络捕获

- `network_capture(action=start/stop, capture_body=True)` → `list_network_requests(limit, after_id)` 增量读 → `get_network_request(request_id, include_body=True)` 取全文。
- `get_request_initiator`：引擎层 initiator 栈（经 `_playwright_initiator_patch.py`），比 Playwright 默认栈更深；仍是归因线索，并发请求需交叉验证。
- 已知边界（来自 `close_browser` 的 `capabilities` 自描述）：worker 请求只有浏览器 context 发出的可观测，service-worker 归属不可得；响应 body 是浏览器解码后的字节，非线上压缩字节；**重定向响应没有 body**。

## 页面交互

- `click(selector)` 返回 `url_before/url_after/url_changed`；`url_changed=false` + 快照无变化 = 点击无效，禁止重复。
- `type_text(selector, text)` 返回 `readback`/`verified`；密码字段只回 `value_length`（不回明文）。`verified != true` 必须先排查再提交。
- selector 用 Playwright 语法：CSS 或 `role=...`；`take_snapshot` 的 role/name 不是选择器。
- `wait_for(selector / url_pattern, timeout)`；`take_screenshot` 返回 base64。

## Hook 与插桩

- `hook_function` / `inject_hook_preset` / `remove_hooks`：页面 JS 层钩取，事件流入产物目录；用完 `remove_hooks`。
- `hook_jsvmp_interpreter`：JSVMP 解释器级钩取（dispatcher 层）。
- `instrumentation`：源码改写插桩（`files_rewritten>0` 只说明改写完成，不证明脚本已执行——继续查 runtime 标记和实际日志）。
- 插桩可能被目标侦测：先跑分叉裁决（见 workflow-details）。

## 引擎层追踪（reverse.9 核心）

- `trace_property_access`：Gecko 原生属性级追踪，零页面污染；产物落 `trace/traces/*.jsonl` + meta。profile 三档见上。**命中是正证据，未命中不是否定证据**（受 profile 覆盖范围限制）。
- `vm_loop_trace`：VM loop 执行链主产物，落 `raw/vm-loop/<id>.json`（loops/realms/dynamic_sources/trace_seq/counters/value_taps）。worker realm 也会记录，查 `realms` 字段确认覆盖。
- `list_trace_files` / `query_trace_file`：trace 文件的离线检索。

## 验证与杂项

- `verify_signer_offline`：离线复现验证——输入样本 + 期望输出，浏览器/Node 双 runtime；这是「已还原」的唯一验收口径。
- `compare_env` / `check_environment`：环境指纹比对与自检。
- `cookies` / `get_storage` / `export_state` / `import_state`：状态证据与登录态迁移。
- `intercept_request`：请求改写/拦截（用于受控对比实验）。
- `scripts` / `search_code` / `evaluate_js` / `get_console_logs`：代码枚举、全文搜索、表达式执行、控制台日志。
