# 结构化搜索与执行证据实现计划

> 按用户已批准的方案实施；云端验证使用 low，本地继续使用配置的执行模型。

## 设计与边界

新增可单独启用的 `execution.search.enabled`，提供 `execution_search`（文件发现/文本检索）与 `execution_status`。固定 rg 可执行文件、参数数组、只读当前 linked worktree，继续经过宿主原生 read 权限。文件发现尊重 ignore，排除凭据及生成目录；文本最多读取 64 个文件，每个 1MiB，所有范围限制均显式返回。Rust 结构检索保留 `execution_ast_search`。RTK 只处理已完成搜索的显示结果，保留原始证据，不修改测试/构建日志。按会话记录真实工具与技能成功调用、搜索边界和 RTK 字节变化；技能存在不等于调用，不能伪造加载记录。

不修改业务工程或中断现有任务。先备份配置，在独立分支实现、测试并准备不可变 runtime；独立验证会话使用项目配置，只有当前任务安全空闲后才更新全局配置。本地探针避开正在使用单并发服务的请求。Serena、浏览器、记忆与 DCP 不启用。

## 文件职责

- `plugins/execution-tools/search.js`：固定 rg、范围和结果边界、原生读取授权。
- `plugins/execution-tools/usage.js`：按会话串行记录工具、技能和过滤计数，不持久化源码/查询内容。
- `plugins/execution-tools/index.js`：注册工具、上下文选择规则、成功调用观测。
- `integrations/execution.py`、`workflow/execution_setup.py`：可迁移配置与工具发现。
- `skills/local-execution/SKILL.md`：实际调用的简短步骤。
- `tests/test_execution_tools.mjs`、`tests/test_execution_config.py`：权限/边界/真实 CLI/配置回归。
- `docs/EXECUTION_EFFICIENCY.md`：配置和效果说明。

## 执行步骤

- [x] T1 先写搜索与会话观测行为测试，观察失败；实现结构化搜索、明确截断和读取拒绝。
- [x] T2 配置开关、模型工具引导、技能规则与统计接入，验证既有配置和云/本地分工保持。
- [x] T3 固定 rg/RTK/ast-grep 实测与完整回归，独立云端 low 审计并修复发现。
- [ ] T4 独立真实本地会话验证技能、文本/文件/结构搜索、RTK 和状态；保留真实证据，记录无法证明的效果。
- [ ] T5 安全空闲时应用备份后的配置；脱敏检查、提交并上传 GitHub，核对远端版本。

## 意外情况

- 权限拒绝、跨 worktree、符号链接换址：失败关闭，不能回退 shell 绕过。
- 无命中且范围被限制：返回 incomplete，不声称全仓库不存在。
- RTK 不可用或输出未变小：保留原输出并如实报告未过滤。
- 当前任务仍在运行：只用隔离 runtime 验证，暂缓全局配置加载。

## 2026-11-19 验证补充

云端增加三层核验：插件实际加载、角色工具可见与权限规则、真实成功回执。已用云端 low 会话验证技能、原生读取/搜索、Context7 和 quality_info；本地专用工具不泄漏给云端。Plannotator 只核对可见与配置权限，未触发人工交互；Quota 核对插件三端声明与服务端加载，未证明 Desktop 窗口的展示结果。

T4 尚需 Strata 原生探针。当前单并发服务持续有业务生成与排队，未插入测试请求；云端兼容性探针成功不能替代本地模型证明。T5 的全局应用必须等安全空闲，当前配置与备份字节一致。详见 docs/validation/2026-11-19-structured-search.md。
