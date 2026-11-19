# 模型映射、生成与迁移

## 两类文件

| 文件 | 保存内容 | 是否提交 |
|---|---|---|
| `models.example.json` | Provider ID、模型 ID、云端档位的脱敏示例 | 是 |
| `models.local.json` | 本机实际角色映射，不含凭据也默认忽略 | 否 |
| `~/.config/opencode/opencode.json` | 实际地址、凭据连接、模型能力、参数与最终角色 | 否 |
| `.workflow-generated-state.json` | 已生成自定义档位的所有权记录 | 否，随本机配置保留 |

生成器不连接模型目录，也不会自动登录。填写前应在 OpenCode 中确认准确的 Provider、模型和 variant。语法有效不代表服务实际可用。

## 继承与覆盖

推荐使用 `"routing": {"cloud_model": "session"}`。所有 `cloud-*` 代理和云端命令不固定 model，当前主会话所选模型和 variant 决定后续云端委派，包括继续同一个审查子会话。本地角色继续使用配置绑定，不跟随云端选择；不会额外设置本地思考强度。

此模式安装 `plugins/cloud-session-router`：使用 OpenCode V2 Promise SDK 的工具钩子，在受管理的 subagent 委派时读取根会话模型元数据，并为云端设置该实际模型、本地设置其固定模型；请求上下文钩子提供本次协调和执行身份。不读取 API 密钥、不联网、不操作工程文件，不处理其他角色。无法确定运行时身份时阻断请求，不猜默认模型。新会话后验证插件为 active；当前已验证 V2 2.3.x，旧版本须先确认兼容性。

切换不追溯改变正在生成的请求，也不主动修改未再次委派的旧子会话。后续新建或续跑委派使用新选择。界面提示仍是模型生成文本，实际请求记录才是路由证据。独立审查指独立上下文与任务，不要求使用不同型号。

`defaults.cloud` 在 session 模式仅是启动默认值。此时非空 `roles.cloud-*` 覆盖会被拒绝。下面的云端单角色覆盖示例仅适用于 `"cloud_model": "fixed"`；省略 routing 也保持旧 fixed 行为。

- `defaults.cloud` 为所有 `cloud-*` 角色设置默认 Provider、模型及云端 variant。
- `defaults.local` 为所有 `local-*` 角色设置默认模型，`variant: null`，不增加工作流思考强度。
- `roles` 只写要覆盖的字段；其他字段继承所属组。只接受十个工作流角色名，拼错会拒绝应用。

例如：

```json
"roles": {
  "cloud-plan": {
    "model": "another-cloud-model",
    "variant": "high"
  },
  "cloud-review": {
    "variant": "medium"
  },
  "local-worker": {
    "provider": "local",
    "model": "another-local-model",
    "variant": null
  }
}
```

示例名称必须替换为真实可用项。更换模型后，旧模型的 variant 不一定适用，需一起调整。

`cloud-*`／`local-*` 是职责命名，不会根据网络地址强制判定云端或本地。实际请求由 `provider/model#variant` 决定；两个组也可使用不同厂商的服务。

## 云端推理强度

使用模型目录实际支持的 variant，如某些模型的 `low/medium/high`。不同模型的档位不通用。生成器支持原生自定义 `variants`（`id/settings/body`），自定义 ID 必须以 `workflow-` 开头，不接受凭据或服务地址字段。

只有有明确需求时才定义自定义云端档位；使用内置 `high` 不需要再写 variants。自定义档位要求目标配置已包含相应 Provider 条目。不同角色若对同一 Provider／模型／档位定义不同内容，生成器拒绝冲突。

本地默认不使用自定义 variants；其原有思考、输出预算等参数在私密 Provider／模型或服务端配置中维护。`variant: null` 不是把所有请求参数清空，也不是关闭模型原有思考。

## 应用的边界

生成器会管理：十个角色的 system/model/description/mode、备用命令、默认入口、原生常用／维护角色的默认模型、本工具创建的自定义档位，以及 session 模式的路由插件条目。无关插件保留；被外部修改的托管插件设置拒绝覆盖。质量安装器把插件复制到带内容哈希的运行目录，移走源码目录不影响已安装质量运行包；单独使用 configure.py 时须保留源码插件目录。

已有工作流角色的权限列表会保留，仅把旧 `strata-worker` 的准确委派资源迁移为 `local-worker`；若旧新 worker 同时存在则拒绝歧义迁移。全新目标使用模板权限。既有目标上的权限差异可能使功能受限，应核对实际规则，生成器不会为了通过流程而放宽权限。

已有角色的其他非模板字段在本版生成时不承诺保留；需要持久使用的配置应明确加入模板并测试。非工作流角色和命令保留，原生维护角色仅同步本地默认模型。

Provider 的既有地址、凭据、默认请求参数、模型能力与上下文限制、自动压缩、MCP和其他根配置保留。自定义 variants 只在模型的 variants 数组中合并，不会把本地示例配置复制进云端 Provider。

生成器只支持 JSON。默认目标是 `~/.config/opencode/opencode.json`，文件必须先存在。`--target` 可测试其他文件；默认模型选择文件是脚本旁的 `models.json`，本仓库推荐显式使用 `--models models.local.json`，避免把个人选择提交到 Git。

## 备份与运行状态

应用前先完整校验输入，再私密备份并原子写入；无差异不新增备份。不属于工具管理的同名自定义档位不会被覆盖；管理过的档位若被外部修改，也会拒绝覆盖。

原子写入保护单个文件；并发运行多个生成器不属于支持用法。请在活动任务结束后应用一次，随后新建会话。

角色提示与实际绑定一起生成，但提示本身仍由模型遵守。它不提供不可绕过的硬状态机，不会改造 Desktop 的系统身份徽标。输入框选择不写回模型映射文件：session 模式影响后续云端委派，fixed 模式继续使用各角色固定绑定；两者都保持本地配置独立。运行回归套件需 Node.js 20+，插件运行不需要安装额外 npm 包。


本地执行能力的统一配置、受管技能、RTK 接管及可选进程限制见 [EXECUTION_EFFICIENCY.md](EXECUTION_EFFICIENCY.md)。
