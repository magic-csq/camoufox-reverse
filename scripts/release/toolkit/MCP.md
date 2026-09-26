# MCP 服务说明：camoufox-reverse

Camoufox Reverse 的 MCP 服务，向 Agent 宿主暴露逆向分析浏览器的全部能力
（启动浏览器、页面操作、网络证据、Hook、属性追踪、VM 执行链分析等）。

## 基本信息

| 项目 | 值 |
| --- | --- |
| 服务名称 | `camoufox-reverse` |
| 传输方式 | stdio（本地子进程，无网络端口） |
| 运行要求 | Python ≥ 3.10 |
| 源码位置 | 工具包内 `integrations/camoufox-reverse-mcp/`（服务端）、`pythonlib/`（浏览器核心） |

## 环境准备（一次性）

在工具包根目录执行，安装三个 Python 组件及其依赖：

```bash
cd ~/camoufox-reverse-browser
python3 -m pip install -e ./pythonlib -e ./integrations/camoufox-reverse-mcp -e ./mcp
```

只装这三个包；不要安装 Node、Selenium 或其它浏览器自动化框架。
网络受限时先配置 pip 镜像或 `https_proxy` 再重跑（命令幂等）。

## 启动命令

```bash
bash ~/camoufox-reverse-browser/scripts/run-reverse-mcp.sh \
  --project-dir ~/camoufox-reverse-evidence --proxy http://127.0.0.1:7890
```

参数说明：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--project-dir <绝对路径>` | 是 | 证据工程目录，所有 raw 产物落盘在这里；每次启动浏览器默认新建隔离 session |
| `--proxy <URL>` | 否 | 浏览器出口代理，不需要代理时省略该参数 |

注意：`run-reverse-mcp.sh` 内部用 `python3` 启动服务端，请确保 `python3`
指向已完成「环境准备」的那个解释器（必要时用绝对路径或在 PATH 中前置）。

## 注册方式

不限定。按你的 Agent 宿主支持的方式把上面的启动命令注册为 stdio MCP
服务（名称 `camoufox-reverse`）即可。如果宿主用 JSON 配置，等价形式是：

```json
{
  "mcpServers": {
    "camoufox-reverse": {
      "command": "bash",
      "args": ["~/camoufox-reverse-browser/scripts/run-reverse-mcp.sh",
               "--project-dir", "~/camoufox-reverse-evidence",
               "--proxy", "http://127.0.0.1:7890"]
    }
  }
}
```

（路径中的 `~` 需展开为绝对路径；已有 MCP 配置只追加这一条，不要覆盖。）

## 验证

注册完成后让宿主加载该 MCP 并列出工具列表，应看到以下 36 个工具：

```
launch_browser, close_browser, navigate, reload, take_screenshot, take_snapshot,
click, type_text, wait_for, get_page_info, reset_browser_state, scripts,
search_code, evaluate_js, hook_function, inject_hook_preset, remove_hooks,
get_console_logs, network_capture, list_network_requests, get_network_request,
get_request_initiator, intercept_request, cookies, get_storage, export_state,
import_state, hook_jsvmp_interpreter, compare_env, instrumentation,
check_environment, verify_signer_offline, trace_property_access,
list_trace_files, query_trace_file, vm_loop_trace
```

也可以在命令行自检（不依赖任何 MCP 宿主）：

```bash
cd ~/camoufox-reverse-browser
bash mcp/run-client.sh --project-dir ~/camoufox-reverse-evidence list-tools
```

看到上述工具清单即说明 MCP 链路正常。

命令行兜底执行浏览器操作时，**直接用包内 `scripts/crb.py`**（内置常驻会话管理，一条命令 = 一次工具调用，浏览器跨命令存活）：

```bash
CRB="python3 ~/camoufox-reverse-browser/scripts/crb.py --project-dir ~/camoufox-reverse-evidence"
$CRB launch --headless
$CRB navigate https://example.com/
$CRB snapshot
$CRB click 'button:has-text("Next")'
$CRB call vm_loop_trace --arguments '{"duration_ms": 15000}'   # 任意工具
$CRB stop
```

不要用 `run-client.sh call` 反复单条调用——每次新起 server 进程，浏览器状态会丢失。
浏览器本体是否就绪，用
`check_environment` 工具确认（它会检查 selector
`whitenightshadow/152.0.4-beta.30-reverse.9` 的安装状态与能力契约）。

## 使用方式

工具调用约定（证据目录结构、session 生命周期、trace 产物解读等）
由 Skill `camoufox-reverse-browser` 描述，装好 Skill 后 Agent 会自动遵循。
核心约定：

- 每次 `launch_browser` 必须传绝对的 `project_dir`；浏览器版本固定用
  `browser_version="whitenightshadow/152.0.4-beta.30-reverse.9"`。
- 逆向分析的关键产物是 `trace_property_access` / `vm_loop_trace` 的落盘记录，
  分析者基于产物离线分析，不需要反复重开浏览器。
- raw 证据只追加不覆盖；分析结论写到 `derived/` 或 `report/`。
