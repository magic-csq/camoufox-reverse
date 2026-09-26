# dola.com Google 登录 id_token 链路采集（2026-09-26）

- 日期：2026-09-26
- 目标类型：第三方登录 OAuth（implicit flow）链路采集
- 验证边界：camoufox reverse.9 + MCP 1.1.0 + crb.py CLI，grok-4.7 宿主实测

## 场景

dola.com 的「Continue with Google」登录：还原从点击登录按钮到 id_token 落地的完整链路。

## 关键发现

- `observed`：dola.com 使用 Google OAuth implicit flow——`accounts.google.com/o/oauth2/v2/auth?response_type=token&client_id=742187162285-...&redirect_uri=https://www.dola.com/auth/callback&scope=email+profile`，state 内含 csrfToken；
- `observed`：链路 `oauth2/v2/auth` → `signin/oauth/consent` → `v3/signin/identifier`（账号输入页）全部请求带引擎层 initiator 栈；
- `observed`：站点登录框架是 TikTok 系（`sf16-website-login.neutral.ttwstatic.com`），Google 登录嵌在其中；
- `gap`：凭据之后的 consent/callback 段在本案例记录时未跑通（图形验证码）。

## 有效路径

crb.py FIFO 长会话 → launch → navigate → network_capture start → snapshot 找登录入口 → click → click Google 按钮 → 授权链路请求全部落 `raw/network/`。同一 session 全程指纹一致。

## 无效路径与坑

1. **CLI 逐条 `call` = 每次新 server 进程 → 浏览器状态丢失**（`Browser is not running`、`engine_trace_not_available` 都是这个根因的表象）；必须 crb.py 或 batch。
2. **空提交死循环触发风控**：邮箱未输入成功时连续点 Next 50+ 次，Google 直接出图形验证码，session 报废。selector 失效要诊断，不要重复点。
3. **快照 role/name 不是选择器**：`textbox` 直接当 selector 会超时；用 `input[type="email"]` 或 `role=textbox[name="..."]`。
4. **输入不验证回读会打错字段**：密码曾被输进邮箱框，无回读时不可见。

## 可复用判据

- Google 系登录：见到 `response_type=token` 即 implicit flow，id_token/access_token 走 redirect fragment 落地，采集重点在 callback 跳转的 URL fragment（`get_page_info` + `evaluate_js` 读 `location.hash`）；
- 登录入口藏在 modal 里时，snapshot 两次（开 modal 前后）；
- 验证码出现 = 停手点，人在回路，不要尝试绕过。
