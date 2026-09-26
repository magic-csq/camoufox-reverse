# Camoufox Reverse 逆向分析浏览器工具包（reverse.9）

这是一个**自包含**工具包：浏览器二进制、Agent Skill、MCP 服务端全部在内，
目标机器不需要 clone 任何仓库。把整个目录放到 `~/camoufox-reverse-browser` 即可。

## 内容清单

| 路径 | 内容 |
| --- | --- |
| `browser/camoufox-152.0.4-beta.30-mac.arm64.zip` | 逆向浏览器二进制（Apple Silicon Mac 版） |
| `browser/SHA256SUMS` | 浏览器 zip 的 SHA-256 校验值 |
| `browser/addons/UBO/` | uBlock Origin 离线副本（首次启动的默认组件，避免 addons.mozilla.org 451 封锁） |
| `skill/camoufox-reverse-browser/SKILL.md` | Agent Skill（逆向取证工作流程说明） |
| `MCP.md` | MCP 服务说明：名称、启动方式、参数、工具清单、验证方法 |
| `pythonlib/` | 浏览器 Python 核心（camoufox 定制版） |
| `integrations/camoufox-reverse-mcp/` | MCP 服务端源码 |
| `mcp/` | MCP 命令行客户端（自检/调试使用） |
| `scripts/install-camoufox-reverse.py` | 浏览器安装器（SHA-256 + 能力契约双重校验） |
| `scripts/run-reverse-mcp.sh` | MCP 服务端启动脚本 |
| `scripts/reverse-browser-instrumentation-divergence.py` | 被动/插桩双会话分叉裁决（未知目标先跑它） |

## 安装步骤

### 1. 安装浏览器二进制（一次性）

```bash
cd ~/camoufox-reverse-browser
python3 scripts/install-camoufox-reverse.py \
  browser/camoufox-152.0.4-beta.30-mac.arm64.zip \
  --sha256 "$(awk '/camoufox-152.0.4-beta.30-mac.arm64.zip$/ {print $1}' browser/SHA256SUMS)"
```

安装器会强制校验 SHA-256 与 reverse.9 能力契约，校验不过则拒绝安装、不做任何改动。
浏览器以 selector `whitenightshadow/152.0.4-beta.30-reverse.9` 旁路安装到
camoufox 缓存，**不改变**机器上已有 Camoufox 的 active 配置；同级的
`browser/addons/` 会一并离线安装（已存在的组件绝不覆盖）。

要求 Python ≥ 3.10。本包浏览器仅支持 Apple Silicon Mac；
其它平台需要从 GitHub Release 获取对应平台的 zip 替换 `browser/` 里的资产
（资产名不同，其余步骤相同）。

### 2. 安装 Skill

把 `skill/camoufox-reverse-browser/` 整个目录复制到你的 Agent 宿主 skill 目录
（例如 `$CODEX_HOME/skills/` 或你 Agent 平台对应的 skills 目录）。
skill 名称是 `camoufox-reverse-browser`。

### 3. 安装 MCP

见 [MCP.md](MCP.md)。里面只描述服务的名称、启动命令、参数和验证方法，
**不限定注册方式**——按你的 Agent 宿主支持的方式自行添加即可。

### 4. 验证

MCP 加载后列出工具列表，应看到 `launch_browser`、`navigate`、
`trace_property_access`、`vm_loop_trace` 等 36 个工具。也可以用包内客户端自检：

```bash
cd ~/camoufox-reverse-browser
bash mcp/run-client.sh --project-dir ~/camoufox-reverse-evidence list-tools
```

## 安全约束

- 证据工程目录（默认 `~/camoufox-reverse-evidence`）包含 Cookie、Storage、
  请求体等敏感数据，**不要加入 Git，不要上传**。
- 除非任务明确要求，不要启动浏览器访问第三方网站，不要登录、不要处理验证码。
- 本工具包仅用于授权的逆向分析与安全研究。
