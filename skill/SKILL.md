---

name: camoufox-reverse-browser
description: 用 Camoufox Reverse 逆向浏览器做授权 Web 逆向取证与执行链分析——还原签名/加密参数生成逻辑、分析混淆 JS/JSVMP/自定义 VM/WASM/Worker 运行链、环境指纹与动态代码取证。浏览器负责产出完整可信的记录监控产物，分析者基于产物离线还原逻辑。不用于普通前端开发、漏洞利用、渗透。

---

# Camoufox Reverse 浏览器逆向取证

这是一个**任务契约 + 工具能力映射**：本文件锁定验收目标、给出执行方法论、把每个分析阶段映射到具体的 MCP 工具与产物文件。

先消灭两种失效模式：

- **目标漂移**：用户要 A（比如还原某加密参数的生成逻辑），执行中降成 B（浏览器跑起来了、页面打开了），还把 B 说成完成。
- **虚假完成**：没做最终验证就说"已完成"。浏览器能启动、trace 有数据、产物文件存在都不算验收——验收 = 用户要的逻辑被还原到可复现的程度，且每条结论在产物里有据可查。

## 何时使用

还原签名/加密参数/风控字段的生成逻辑；分析混淆 JS、eval/Function 动态代码、JSVMP/自定义 VM、WASM、Worker/iframe 多上下文运行链；环境指纹与反检测对抗取证；把采集到的证据整理成可离线复现的分析报告。

不适用：普通前端开发、漏洞利用/渗透、非 Web 目标的逆向。

## 两条红线

1. **产物集中**：一切证据落在 `project_dir`（绝对路径、可写、不在 Git 提交范围内）的 `runs/<session-id>/` 下。每次 `launch_browser` 默认新建隔离 session。raw 证据只追加，分析结论写 `derived/`、`report/` 或 `indexes/`，绝不覆盖 raw。
2. **完成必须可验证**："已还原"只能在**离线复现验证通过**之后说——用产物里的字节离线重建出目标参数的生成过程（`verify_signer_offline` 或等效脚本），并明确标出哪些环节是 `observed`（直接捕获）、`inferred`（推断）、`gap`（缺失）。没跑通就如实写卡点。

## 环境前提

工具包根目录（默认 `~/camoufox-reverse-browser`）下有 MCP 服务端与客户端；MCP 注册方式见包内 `MCP.md`。启动参数：

- `project_dir` 必填，绝对路径；
- 需要代理时显式传（如 `http://127.0.0.1:7890`）；不要从聊天记录或报错里复制代理凭据；
- 浏览器版本固定 `browser_version="whitenightshadow/152.0.4-beta.30-reverse.9"`，不改变机器上其它 Camoufox 的 active；
- `enable_trace=True`（默认）启用引擎层 PropertyTracer；`trace_profile` 三档：`overview`（被动首选）→ `targeted` → `deep`（开销递增）。

整条任务**只用同一个浏览器实例/同一套指纹配置**——换实例 = 指纹变化 = 可能触发风控拿到假数据，污染整条证据链。

## 交付梯度（先选 1 个主模式，不提前升级）

- **A 逻辑还原报告**：加密参数的生成链路（采集点 → 变换 → 落地字段）在产物中完整可追溯，附离线复现脚本。
- **B 关键算法复现**：核心变换用 Python/Node 单独跑通，输出与浏览器内观测一致。
- **C 端到端参数生成**：给定输入能离线生成合法参数（必要时服务端实测）。

用户没要求纯算法时，A 就是完整交付；不要为"更完整"自动升级到 C。

## 执行循环（每轮产出服务于最终交付）

`定位 → 采集 → 还原 → 复现 → 验证` 逐轮推进：

1. **定位**：`navigate` 打开目标 → `network_capture` + `list_network_requests` 找加密请求 → `get_request_initiator` 拿生成调用链 → `scripts`/`search_code` 定位 VM/混淆代码段与所在 realm。
2. **采集**：对未知目标先跑分叉裁决（被动/插桩双会话，见「插桩还是被动」），再按裁决采：被动走 `trace_property_access`（overview）+ `vm_loop_trace`；插桩透明就走 `hook_function`/`inject_hook_preset` 定向钩取。
3. **还原**：读产物（`raw/vm-loop/`、`trace/`、`raw/network/`），按「标准分析顺序」五步：定位 VM → 还原结构 → 钉语义 → 追数据流 → 验证理解。
4. **复现**：把证据转成最小离线脚本；随机源/时间戳钉死后输出应与浏览器观测逐字节一致。
5. **验证**：围绕最终交付验证，不是局部成功。

## 工具能力映射（语义层 → 工具 → 产物）

| 分析意图 | 用什么 | 产物落点 |
| --- | --- | --- |
| 找加密请求与调用点 | `network_capture` → `list_network_requests` → `get_request_initiator` | `raw/network/<id>/`（含引擎层 initiator 栈） |
| 看目标加载/执行了什么代码 | `scripts`、`search_code`、`evaluate_js` | `raw/vm-loop/<id>.json` 的 `dynamic_sources` |
| 钩函数抓入参/返回（sign-call 层） | `hook_function` / `inject_hook_preset`（用完 `remove_hooks`） | hook 事件流 |
| VM 执行链（dispatcher/opcode/handler） | `hook_jsvmp_interpreter`、`vm_loop_trace` | `raw/vm-loop/<id>.json`（loops/trace_seq/counters/value_taps） |
| 原生属性级追踪（零页面污染） | `trace_property_access` → `list_trace_files` → `query_trace_file` | `trace/` 目录 jsonl + meta |
| 环境指纹比对/自检 | `compare_env`、`check_environment` | 比对报告 |
| Cookie/Storage 证据 | `cookies`、`get_storage`、`export_state`/`import_state` | `raw/` 下对应文件 |
| 页面交互（登录后页面等） | `click`、`type_text`、`wait_for`、`take_snapshot` | 快照在 `raw/.snapshots/` |
| 请求改写/拦截 | `intercept_request` | `raw/network/` |
| 离线验证签名实现 | `verify_signer_offline` | 验证结果 |

Hook 语义优先级（高 → 低）：`request-use`（参数落请求处）→ `sign/decrypt-call` → `payload 明文边界` → `dispatch` → `reader/writer` → 低层 DOM/storage。**优先钩高语义层**；在 cookie setter、appendChild 这类低层 surface 之间切换不算真正换路线。

命令行兜底（不依赖 MCP 宿主）：`bash ~/camoufox-reverse-browser/mcp/run-client.sh --project-dir <绝对路径> list-tools` / `call <tool> --arguments '<json>'`。

## 取证纪律

- 先列 2~5 个高信息量入口（候选加密参数、可疑 VM 文件、关键请求），再启用定向 trace；**不无目标地全量记录**。
- **假设先行**：每次 Hook/开 trace 前先写下假设（"我预期看到 X，它能区分 A/B 两种可能"）。同一疑点 3 次（VM/WASM 链 6 次）仍无新认知就换语义层/换入口，把刷 dump 当进度 = 失败。
- 关联断言必须有证据链：请求 ID + 脚本 hash + trace 序号 + 调用帧串起来；仅凭时间相近不断言数据依赖。
- 分级标注：`observed`（直接捕获）/ `call-linked`（调用关系）/ `inferred`（注明推断依据）/ `gap`（缺失，如实登记）。
- 所有 stdout/stderr 不出现密码、Cookie、token 或完整代理认证信息。

## 停损（每轮结束自问）

- 连续 2 轮无新增 hook/入口/证据映射 → 换入口或换语义层；
- 被动 profile 拿不到所需语义 → 先跑分叉裁决确认插桩透明再上插桩；
- 某条路线产物显示 `gap` 连续存在 → 区分是「能力缺口」还是「本轮目标没跑这段代码」（看活性自检字段），是能力缺口就如实写进报告，不要假装覆盖。

## 插桩还是被动：先跑分叉裁决

对未知目标，用分叉检测自动跑被动/插桩双会话再决定深入方式：

```bash
python3 ~/camoufox-reverse-browser/scripts/reverse-browser-instrumentation-divergence.py \
  --target-url <目标URL> --project-dir <绝对路径>
```

裁决口径：**aligned** 插桩透明可深采；**diverged** 目标侦测到插桩，改走被动链路；**gap** 产物不全先补采集。

## 产物结构与标准分析顺序

```
runs/<session-id>/
├── manifest.json        # session 状态（complete/incomplete）
├── raw/network/         # 请求/响应全文 + 引擎层 body + initiator 栈 + 终态自描述
├── raw/vm-loop/         # VM 执行链主产物（loops/realms/dynamic_sources/trace_seq/value_taps/counters）
├── raw/worker-source/   # Worker 源码回补
├── trace/               # PropertyTracer 原生属性事件
└── derived/ report/ indexes/   # 你的分析结论写这里
```

分析五步：① `dynamic_sources`+`realms` 定位 VM 与所在 realm → ② `loops`+`counters`+`trace_seq` 裁决派发形态 → ③ `trace_seq` 参数证据 + 返回值锚点 + `trace/` 原生事件钉 handler 语义 → ④ `value_taps` 回追加密参数从采集点到请求字段的完整变换链 → ⑤ 对照 `raw/network/` 全文确认离线重放所需字节齐全。

所有截断/缺口都有自描述字段（`truncated`、`coverage_pct`、`worker-gap`、`serviceworker-gap` 等）——**产物里没有的是能力缺口，有但没说清可信度的也是缺口**，两类都要在报告里如实标注。

## 收尾契约（唯一的文档义务）

任务完成或明确终止时，把分析过程写进 `<project_dir>/report/<task>-report.md`，内容必须来自真实做过的事，六节必填：

1. **目标与结果**：一句话目标 + 验收状态（跑通的验证命令 + 输出摘要）；
2. **证据链路径**：从定位到验证的关键步骤，写清 session-id、关键文件、断点/Hook 点、函数名；
3. **逆向思路**：候选路线与选择依据、关键转折点；
4. **难点与坑点**：卡壳处、反调试/混淆对抗细节、产物缺口（gap 如实写）；
5. **经验沉淀**：可复用的判据/参数含义/工具用法；
6. **交付物与复现**：文件清单（相对路径）+ 复现命令 + 依赖。

## 回复纪律

只有四种情况停下：① 需要用户协作（登录/验证码/样本）；② 高风险副作用需确认；③ 已完成可验证交付（report 已写）；④ 必须声明目标偏差或路线级 pivot（声明后继续执行）。不要把"我会继续"当作输出。
