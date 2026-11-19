# 本地执行效率集成设计（待确认）

目标：把 RTK、ast-grep、本地执行技能、精选 Rust 技能、Serena 和 Playwright CLI 作为 MyOpenCodeConfig 可迁移、可选择的能力，缩短需求开始至独立审计通过的时间。不能用 token 降幅替代速度或正确性。

## 已知基线

远端 master 核对为 41523127e50b6f18843e821f59183a35d2a128d7。工程已有 models.example.json / configure.py / setup_quality.py、skills.lock.json、integrations/plugins.lock.json、不可变质量运行时、云会话模型继承、固定本地 worker、原工程只读和 linked worktree 防护。此次规划在独立 worktree 编写，不修改原 checkout 或生效配置。

现有 RTK 为用户目录自动发现的 plugins/rtk.ts，不在受管 plugins 列表中；不能重复注册另一个 RTK hook。RTK 1.2.0 的机器全局统计不能代表 OpenCode 独有收益。当前 ACP 已对本地会话注入 compress/acp_status，云会话未必有，原生 auto:false 需要单独核对覆盖；本项目此次不顺带切换上下文管理器。

## 范围与默认

- 基础方案：RTK 精选输出过滤、ast-grep 结构搜索、短版 local-execution 技能。
- Rust 工程：按具体编译错误加载 ownership/error-handling/concurrency 的精选适配，保留上游来源与完整必要资源。
- Serena：随工程保存配置和适配；默认关闭，仅在通过单独权限与性能验收后开启只读符号导航。禁止编辑、rename、REPL、任意 shell、记忆和自动 onboarding。
- Playwright CLI：随工程保存能力；默认关闭，Web 任务按需启用，使用隔离浏览器会话。
- cargo-nextest、sccache 仅记为后续独立性能实验；本批不安装或替换验证命令。
- 不加入 Morph、其他云端编辑服务、新模型路由、新记忆/DCP/压缩层、第二套 TDD/编排。

## 方案选择

推荐沿用现有生成器和不可变运行时，增加一个可选 execution 配置域、依赖锁和少量按需技能，独立能力按开关安装/暴露。另两种方案：整套 agent 框架替换会干扰既有分工；把每个工具独立手工配置难以迁移和回滚，均不推荐。这里是提议，不标记为用户已批准。

## 必须保持

R1 云端选中模型负责澄清、计划、审计；同一个固定 local-worker 负责实现、测试、修复；不增加本地 reasoning variant。
R2 每个新实现需求独立 worktree；原工程源码只读；共享 Git 元数据、硬链接、macOS 保护范围沿用现有文档，不能宣称完整宿主隔离。
R3 不改项目契约、验证入口、断言、停止条件或批准范围。OnlyAlpha 原生模式不生成 portable 合同/门禁工件。
R4 旧配置不含 execution 时行为保持；新配置未知字段/无效组合写前失败；不触碰无关 Provider/OAuth/上下文预算/压缩设置。
R5 锁定版本/commit、上游文件摘要、许可与必要资源，运行中不下载 latest 或自动更新。
R6 安装、接管、卸载均备份、幂等、可回滚；逐目标检测并发修改，异常恢复也不得覆盖用户的新变化；未知外部插件/技能不得覆盖。秘密、个人路径、浏览器状态、索引和日志不进公共仓库。
R7 新工具自建子进程、MCP与browser进程需分别检查实际调用角色/session/worktree，尊重worktree内原生read deny/ask；新 MCP 进程单独隔离并管理自有子进程生命周期；OpenCode 原生 edit 规则或 shell wrapper 不能自动保护 MCP 自己的进程。
R8 不静默把工作切给云端或替代模型；必要工具失败回传明确阻塞，可选搜索失败最多一次回退到现有只读搜索。
R9 每阶段继续显示协调模型、执行模型、状态和实际 worktree；只在能力变化时显示启用工具，避免每轮重复长卡片。
R10 原始验证日志落盘；RTK 摘要不充当完整证据。涉及固定精确验证命令、管道/重定向及权限语义不明确的命令不改写。

## 建议统一配置

在现有模型映射中新增可选字段（提议接口，尚未实现）：

```json
"execution": {
  "rtk": {"enabled": true, "profile": "safe-output"},
  "ast_grep": {"enabled": true},
  "worker_skill": true,
  "rust_skills": ["ownership", "error-handling", "concurrency"],
  "serena": {"mode": "off"},
  "browser": {"mode": "off"}
}
```

执行范围只允许当前 worktree。rtk profile 仅允许已验证的列表/搜索摘要等命令；没有完整验证前不改写 diff、源码读取、测试/审计证据命令。ast-grep 仅搜索，批量替换须另有计划授权。Rust 技能按实际问题加载，不能每个 Result/async 都触发。Serena mode 仅 off/symbols-readonly；browser mode 仅 off/playwright-cli。

## 期望流程

云端确认需求和计划 → 自动准备 worktree、继承原生工程规程 → 给同一 Strata worker 简短交接（目标/非目标、基线、路径、验收命令、停止条件）→ worker按问题选择 rg/ast-grep/已启用Serena → 定位并局部修改 → 实际编译错误驱动修复、原生验证与完整日志 → 云端读取当前字节和原始证据独立审计 → 有阻塞交还同一worker修复复验 → 审计通过后按原授权收尾。

## 成功条件

配置迁移/回滚、权限和模型分工必须全部通过；性能与准确性按计划中的相同任务对照评价。没有实测就保持“候选”状态。阶段交付可单独验收；Serena/browser 不通过不得阻塞已验收的基础能力，也不得暗中放宽权限。
