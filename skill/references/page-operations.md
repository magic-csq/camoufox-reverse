# 页面操作详解与事故案例

页面交互（click/type/wait/snapshot）是为采集服务的手段，不是进度本身。本页所有规则都来自真实事故。

## selector 语法

`click`/`type_text` 的 `selector` 是 Playwright 选择器：

- CSS：`#identifierId`、`input[type="email"]`、`button:has-text("Next")`；
- role：`role=textbox[name="Email or phone"]`；
- `take_snapshot` 返回的 `role`/`name` **不是选择器**——用它们构造上述合法形式。

事故案例：某 agent 把快照里的 role 名 `textbox` 直接当 selector 传入，Playwright 按 CSS 元素选择器解析，永远找不到，超时 30 秒——而 agent 没有读返回里的 error，继续往下走。

## 输入验证（回读）

`type_text` 返回带 `readback`/`verified`：

- 普通字段：`readback.value` 是输入后字段的真实值，`verified` 为是否匹配；
- 密码字段：只回 `value_length`（不回明文），`verified` 按长度判断；
- `verified != true` → **禁止点击 Next/提交**，先排查：选择器命中了吗？字段被页面脚本清了吗？页面已经跳走了吗？
- 关键字段（邮箱/密码/验证码）宁可再 `evaluate_js` 读一次 `.value` 确认。

事故案例：某 agent 把密码输进了邮箱框（选择器命中了错误的输入框），`type_text` 当时没有回读能力，错误直到截图才被发现——期间已空提交数十次触发风控。

## 防死循环（硬规则）

对同一个 selector 的 `click`/`type_text`，连续 2 次后 `url_changed=false` 且 `take_snapshot` 内容无实质变化 → **立刻停止重复调用**，转诊断：

- 快照里有没有报错提示 / 验证码 / 加载中？
- 元素是否真的可交互（被遮挡、disabled、在 iframe 里）？
- 是不是该等跳转（`wait_for`）而不是再点一次？

事故案例：Google 登录页，邮箱没输入成功的情况下连续点击 Next 50+ 次，Google 直接对该会话弹出图形验证码，整个 session 报废。**重复空提交是风控触发器，不是重试。**

## 导航与状态确认

- 点击触发跳转后，用 `wait_for(url_pattern=...)` 或 `get_page_info` 确认 URL 变了，再操作新页面；
- 不在旧页面上操作新流程；
- `take_snapshot` 是定位元素的依据，每次页面变化后重新取。

## 弹窗与多页面

`launch_browser` 返回 `pages` 列表；授权类流程（OAuth popup）可能开新页面，用 `get_page_info` 确认当前聚焦页面，必要时在快照里确认元素归属。
