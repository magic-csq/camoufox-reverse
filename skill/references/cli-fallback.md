# 命令行兜底：crb.py 与底层机制

宿主不支持 MCP 或工具调用持续失败时使用。日常使用只需要第一节。

## crb.py：一条命令 = 一次工具调用

```bash
CRB="python3 ~/camoufox-reverse-browser/scripts/crb.py --project-dir /abs/evidence"
$CRB launch --headless            # 启动浏览器；首次调用自动拉起常驻 server
$CRB navigate https://target.example/
$CRB snapshot                     # aria 快照（找可交互元素）
$CRB screenshot                   # 截图（base64 JSON）
$CRB click 'button:has-text("Log In")'
$CRB type 'input[type="email"]' 'user@example.com'
$CRB eval 'document.title'
$CRB requests                     # 列出已捕获网络请求
$CRB page-info                    # 当前 URL/标题
$CRB call <任意工具名> --arguments '{"key": "value"}'   # 36 个工具全能调
$CRB status                       # server 是否存活
$CRB stop                         # 收尾：close_browser + 关闭 server
```

行为约定：

- 首次调用自动拉起常驻 server 并启动浏览器会话，之后每条命令复用**同一个浏览器**（满足"整条任务同一指纹"红线）；
- `project_dir` 自动注入每条调用的 arguments，不用手写；
- 每条命令把工具的真实 JSON 返回打到 stdout；工具级错误（返回里有 `error`）退出码为 1；
- 每条命令默认超时 180 秒，`--timeout` 可调（trace 类长操作调大）；
- 状态文件在 `<project_dir>/.crb/`（mcp.fifo、results.jsonl、server.pid、lock），带文件锁防并发写。

## 底层机制（排障时才需要看）

crb.py 内部是 FIFO 长会话：`run-client.sh ... batch <fifo>` 让一个 MCP server 进程常驻，读命名管道里的 JSON-lines（每行 `{"tool":..., "arguments":{...}}`），结果追加到 results.jsonl，`{"tool":"__shutdown__"}` 终止。

**为什么不能绕过 crb.py 直接调 `run-client.sh call`**：`call` 每次新起一个 server 进程，浏览器注册表在内存里，进程退出即丢失——上一条 `launch_browser` 启动的浏览器，下一条 `get_page_info` 就报 `Browser is not running`，`trace_property_access` 报 `engine_trace_not_available` 也是同一根因。

原始 batch 仍可用（一长串固定调用一次跑完）：

```bash
bash mcp/run-client.sh --project-dir <dir> --timeout 180 batch calls.jsonl
```

## 进程清理纪律

- 正常收尾就是 `$CRB stop`，**不需要杀进程**；
- 确实要清残留（如异常退出留下的孤儿），**只能用包内 `scripts/mcp-cleanup.sh --project-dir <本任务目录>`**——带选择器的 scoped 清理；
- **严禁广谱 `pkill`**（`pkill -f camoufox`、`pkill -x moz` 之类）：会误杀其它并行任务的 server、别的会话的浏览器、甚至本机 Firefox；
- 机器上存在其它 camoufox 进程是正常的（其它会话 / Codex 常驻 MCP server），`ps | grep` 看到有进程不等于"没清干净"，**不要反复清理**——把清理命令输出非空当成失败并重试，是实测中真实发生过的死循环事故。

## server 启动的 Python 选择

`run-reverse-mcp.sh` 会自动探测带依赖（orjson 等）的解释器（`python3.13/3.12/3.11` + 常见绝对路径）；都没有时报错并提示设 `CAMOUFOX_REVERSE_PYTHON=/path/to/python`。
