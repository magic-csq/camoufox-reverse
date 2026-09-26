---

name: camoufox-reverse-browser
description: 用 Camoufox Reverse 逆向浏览器做授权 Web 逆向取证与执行链分析——还原签名/加密参数生成逻辑、分析混淆 JS/JSVMP/自定义 VM/WASM/Worker 运行链、环境指纹与动态代码取证。浏览器负责产出完整可信的记录监控产物，分析者基于产物离线还原逻辑。不用于普通前端开发、漏洞利用、渗透。
metadata:
  version: "2.0.0"
  mcp-compatible: "1.1.0 + browser whitenightshadow/152.0.4-beta.30-reverse.9"

---

# Camoufox Reverse 浏览器逆向取证

本文件是**任务契约**：锁定验收目标、调用方式和纪律底线；工具参数细节、产物解读、操作流程等深度内容按需加载 `references/` 下对应文档，不要凭记忆猜参数。

先消灭两种失效模式：

- **目标漂移**：用户要 A（比如还原某加密参数的生成逻辑），执行中降成 B（浏览器跑起来了、页面打开了），还把 B 说成完成。
- **虚假完成**：没做最终验证就说"已完成"。浏览器能启动、trace 有数据、产物文件存在都不算验收——验收 = 用户要的逻辑被还原到可复现的程度，且每条结论在产物里有据可查。

## 何时使用

还原签名/加密参数/风控字段的生成逻辑；分析混淆 JS、eval/Function 动态代码、JSVMP/自定义 VM、WASM、Worker/iframe 多上下文运行链；环境指纹与反检测对抗取证；把采集到的证据整理成可离线复现的分析报告。

不适用：普通前端开发、漏洞利用/渗透、非 Web 目标的逆向。

## 三条红线

1. **产物集中**：一切证据落在 `project_dir`（绝对路径、可写、不在 Git 提交范围内）的 `runs/<session-id>/` 下。raw 证据只追加，分析结论写 `derived/`、`report/` 或 `indexes/`，绝不覆盖 raw。
2. **完成必须可验证**："已还原"只能在**离线复现验证通过**之后说（`verify_signer_offline` 或等效脚本），并明确标注每条结论是 `observed` / `call-linked` / `inferred` / `gap`。没跑通就如实写卡点。
3. **防编造铁律**：只有拿到工具的真实返回，才允许陈述任何事实。「把工具名和参数写进回复正文」不是调用。证据目录里**必须**有这次调用产生的真实文件，空目录 = 没做过。

## 环境前提与调用方式

工具包根目录（默认 `~/camoufox-reverse-browser`）下有 MCP 服务端与 CLI；MCP 注册方式见包内 `MCP.md`。关键约定：

- `project_dir` 必填绝对路径；需要代理时显式传（如 `http://127.0.0.1:7890`），不从聊天记录复制代理凭据；
- 浏览器版本固定 `browser_version="whitenightshadow/152.0.4-beta.30-reverse.9"`，不改变机器上其它 Camoufox 的 active；
- 整条任务**只用同一个浏览器实例/同一套指纹**——换实例 = 指纹变化 = 可能触发风控拿到假数据。

宿主调用方式三选一，动手前先用一次真实调用确认自己在哪种环境，然后全程只用这种方式：

1. **直接工具**（Kimi、Codex 等）：工具列表里直接有 `launch_browser` 等 36 个工具 → 直接调用。
2. **元工具**（Grok 等延迟加载宿主）：只有 `search_tool`/`use_tool` → 先搜再用全名调用：`use_tool("camoufox-reverse__launch_browser", {...})`（两个下划线）。
3. **命令行兜底**：用包内 `scripts/crb.py`，一条命令 = 一次工具调用，首次调用自动拉起常驻 server（浏览器跨命令存活）：

   ```bash
   CRB="python3 ~/camoufox-reverse-browser/scripts/crb.py --project-dir /abs/evidence"
   $CRB launch --headless
   $CRB navigate https://target.example/
   $CRB snapshot                       # aria 快照找可交互元素
   $CRB click 'button:has-text("Log In")'
   $CRB type 'input[type="email"]' 'user@example.com'   # 返回带 readback/verified
   $CRB call vm_loop_trace --arguments '{"duration_ms": 15000}'
   $CRB stop                           # 收尾：关浏览器 + 关 server
   ```

   工具级错误 → 退出码 1；`project_dir` 自动注入。底层机制与进程清理纪律见 [cli-fallback](references/cli-fallback.md)——正常收尾就是 `$CRB stop`，**严禁广谱 pkill**。

## 交付梯度（先选 1 个主模式，不提前升级）

- **A 逻辑还原报告**：加密参数生成链路（采集点 → 变换 → 落地字段）在产物中完整可追溯，附离线复现脚本。
- **B 关键算法复现**：核心变换用 Python/Node 单独跑通，输出与浏览器内观测一致。
- **C 端到端参数生成**：给定输入能离线生成合法参数（必要时服务端实测）。

用户没要求纯算法时，A 就是完整交付；不要为"更完整"自动升级到 C。

## 执行循环

`定位 → 采集 → 还原 → 复现 → 验证` 逐轮推进，每轮产出服务于最终交付：

1. **定位**：`navigate` → `network_capture` + `list_network_requests` 找加密请求 → `get_request_initiator` 拿调用链 → `scripts`/`search_code` 定位 VM/混淆代码段与所在 realm。
2. **采集**：未知目标先跑分叉裁决（被动/插桩双会话，见 [workflow-details](references/workflow-details.md)）；被动走 `trace_property_access`（overview）+ `vm_loop_trace`，插桩透明走 `hook_function`/`inject_hook_preset`。
3. **还原**：读产物按标准分析五步（定位 VM → 还原结构 → 钉语义 → 追数据流 → 验证理解），产物字段详解见 [artifact-analysis](references/artifact-analysis.md)。
4. **复现**：证据转最小离线脚本；钉死随机源/时间戳后输出应与浏览器观测逐字节一致。
5. **验证**：围绕最终交付验证，不是局部成功。

Hook 语义优先级（高 → 低）：`request-use` → `sign/decrypt-call` → `payload 明文边界` → `dispatch` → `reader/writer` → 低层 DOM/storage。**优先钩高语义层**。

## 取证纪律

- 先列 2~5 个高信息量入口再启用定向 trace；**不无目标地全量记录**。
- **假设先行**：每次 Hook/开 trace 前写下假设（"我预期看到 X，它能区分 A/B"）。同一疑点 3 次（VM/WASM 链 6 次）无新认知就换语义层/换入口，把刷 dump 当进度 = 失败。
- 关联断言必须有证据链：请求 ID + 脚本 hash + trace 序号 + 调用帧串起来；仅凭时间相近不断言数据依赖。
- 产物截断/缺口都有自描述字段（`truncated`、`coverage_pct`、`worker-gap` 等）——**产物里没有的是能力缺口，有但没说清可信度的也是缺口**，都要如实标注。
- stdout/stderr 不出现密码、Cookie、token 或完整代理认证信息。

## 页面操作纪律（click/type/wait 类，硬规则）

页面交互是采集的手段，不是进度本身。违反任意一条算操作事故：

- **每次调用先读返回再动下一步**；返回里有 `"error"` 就是失败，不允许无视错误继续。
- **输入必须验证回读**：`type_text` 返回 `readback`/`verified`，`verified != true` 时不允许提交，先排查；关键字段可用 `evaluate_js` 再读一次 `.value`。
- **防死循环**：同一 selector 的 click/type 连续 2 次后 `url_changed=false` 且快照无实质变化 → **立刻停止重复调用**转诊断。重复空提交会触发风控（实测：Google 登录页被连点 50+ 次后直接出图形验证码）。
- **selector 是 Playwright 语法**：CSS（`#identifierId`、`button:has-text("Next")`）或 role（`role=textbox[name="..."]`）；`take_snapshot` 返回的 role/name 不是选择器。
- **每步之间等跳转**：`wait_for`/`get_page_info` 确认 URL/DOM 变了再继续。

## 停损（每轮结束自问）

- 连续 2 轮无新增 hook/入口/证据映射 → 换入口或换语义层；
- 被动 profile 拿不到所需语义 → 先跑分叉裁决确认插桩透明再上插桩；
- 产物 `gap` 连续存在 → 区分「能力缺口」还是「本轮没跑这段代码」（看活性自检字段），能力缺口如实写进报告。

## 收尾与回复纪律

任务完成或终止时写 `<project_dir>/report/<task>-report.md`（六节必填模板见 [report-contract](references/report-contract.md)），内容必须来自真实做过的事。

只有四种情况停下：① 需要用户协作（登录/验证码/样本）；② 高风险副作用需确认；③ 已完成可验证交付；④ 必须声明路线级 pivot（声明后继续执行）。不要把"我会继续"当作输出。

## 按需参考

| 当前需要 | 参考 |
| --- | --- |
| 36 个工具的参数、契约边界、缺口字段语义 | [mcp-tool-reference](references/mcp-tool-reference.md) |
| 产物目录结构、vm_loop/trace 产物解读、分析五步 | [artifact-analysis](references/artifact-analysis.md) |
| crb.py 完整用法、FIFO 底层机制、进程清理 | [cli-fallback](references/cli-fallback.md) |
| 分叉裁决、执行循环各阶段细节、停损判据 | [workflow-details](references/workflow-details.md) |
| 页面交互操作详解与事故案例 | [page-operations](references/page-operations.md) |
| 报告六节模板与分级标注规范 | [report-contract](references/report-contract.md) |
| 历史实战案例（脱敏沉淀） | [cases/](cases/) |

## 更新记录

- v2.0.0（2026-09-26）：重构为骨架 + references 按需加载结构；新增 crb.py 一键 CLI、页面操作纪律（回读验证/防死循环）、进程清理纪律——全部来自 grok 实测 dola.com Google 登录链路的真实事故。
- v1.x：单文件任务契约 + 工具能力映射（reverse8 各阶段沉淀）。
