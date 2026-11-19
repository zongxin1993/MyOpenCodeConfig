# 结构化搜索、技能与云端工具验证（2026-11-19）

## 状态与运行边界

本分支实现显式 `execution.search.enabled` 开关。默认关闭，用户可在统一模型配置中启用。本次先保留现有全局配置，在独立 Git worktree 和项目配置中验证；持续只读观察业务会话、Strata 槽位与队列，直到连续两次全部空闲才提交真实本地探针。未重启 OpenCode 或 Strata，未向业务会话发送消息，未调用全局 location reload。

**真实 Strata 探针及全局应用后复验均已通过。** 应用前重新备份受管配置、技能及私有生成器；安装器另有事务备份。新的纯净 linked worktree 无项目覆盖，确认全局执行插件 active、全局技能实际加载及本地工具真实调用成功。云端 low 也在该项目完成只读工具复验。备份、原始回执、日志和机器路径只留本机。
## 自动验证

- 93 项 Python 回归通过，包含配置生成、部署事务、权限与子进程测试。
- 48 项 Node 测试通过；真实 rg、RTK、ast-grep 通过固定可执行文件参与验证。
- 主要覆盖：读取权限拒绝、跨 worktree、符号链接换址、文件增长读取预算、取消、查询参数注入、文件 glob、结果范围标记、技能真实 ID、RTK 原文保全、云端工具隔离。
- 云端独立审计使用 `openai/gpt-6.1-sol#low`，前轮发现的技能安装遗漏、RTK 统计与读取预算问题已修复并增加回归。最终复审 PASS；文件名 glob 越过 ignore 的 P2 问题改为与原始候选集合取交集，新增忽略文件回归并观察 FAIL→PASS。审计为静态只读，不以测试替代审计。

## 原生宿主兼容性

在独立测试项目中加载本分支插件，使用 low 云端模型兼容性探针：

| 项目 | 实际证据 |
|---|---|
| 技能 | 成功加载 `local-execution` |
| 文件与文本工具 | 成功调用 `execution_search` 两次，文本命中 100 行 |
| 使用记录 | `execution_status` 记录该插件加载后的技能 1 次、搜索 2 次；该段 Shell 搜索回退 0 次 |
| RTK 显示 | 匹配文本 9,791 → 1,074 UTF-8 字节，缩减约 89.0%；统计包含过滤后的原文路径提示，不包含范围摘要 |
| 原文 | 私有 0600 日志与完整 100 行匹配逐字节一致 |
| 源目录 | 测试源 checkout 保持干净，内容未修改 |

探针初次使用单个 `.mjs` 包装文件未被原生插件系统加载，改用带 `package.json` 与 `exports` 的本地包后成功。生产插件原本就是此结构。后续补充修复 files 模式的文件名 glob，并以 `*.rs`、`--files` 和被忽略的匹配文件回归验证；原生宿主再次确认只列出两个 Rust 文件、排除 ignored.rs。两轮累计技能 2 次、搜索 4 次、Shell 搜索回退 0 次，RTK 两次合计 19,582 → 2,148 字节。上述统计只覆盖新插件加载后的段落，不能解释为整段历史无回退。

## 云端模型配置工具检查

另一个原生 `cloud-workflow` 会话使用 `openai/gpt-6.1-sol#low`，仅进行只读检查：

| 能力 | 加载／可见与权限 | 真实调用结果 |
|---|---|---|
| 代码读取与搜索 | 云端角色允许 read/glob/grep | read、glob、grep 均成功，找到函数及两个 Rust 文件 |
| 审计技能 | 云端角色允许 skill | `using-superpowers`、`quality-review`、`opencode` 成功加载 |
| Context7 0.2.2 | 插件 active，允许 resolve-library-id/query-docs | OpenCode 库解析及插件权限文档查询均成功；查询混合 V1 示例，不能替代本机 V2 配置证据 |
| 自有质量 MCP | 允许 quality_info 等受管动作 | quality_info 成功；本次未注册测试项目、未运行质量门禁 |
| Plannotator 0.28.67 | 插件 active；云端规划可见 submit_plan，配置允许；审计角色禁止提交 | 本次未调用 submit_plan，不声称人工审批交互完成 |
| Quota 6.3.0 | 插件 active，声明 server/TUI/GUI 能力 | 未验证 Desktop 窗口和额度数据；Quota 的设置写入工具不因本次检查而获得权限 |
| 本地执行专用工具 | 云端上下文无 execution_search/status/ast_search | 符合角色分工；云端继续用原生 read/glob/grep |

另发现既有 `opencode-mobile@latest` 加载失败：导出结构缺少原生宿主所需的默认插件定义。本次未变更该插件、未重启业务会话；该异常独立于搜索优化，不应计为本次全部插件健康。

## 真实 Strata 与全局配置复验

两次会话实际模型均为 `strata-local/qwen3.8-flash-next-unsloth-ud-q4_k_xl`，variant 为默认值；没有设置本地推理强度。第一次使用独立项目包装验证新插件；第二次在无 `.opencode` 覆盖的纯净 linked worktree 中使用正式全局插件。

| 观测项 | 应用前的隔离探针 | 应用后的全局探针 |
|---|---|---|
| 实际技能加载 | `local-execution` 1 次，项目技能 | `local-execution` 1 次，全局技能 |
| `execution_search` | 3 次：文件 2、文本 1 | 2 次：文件 1、文本 1 |
| 文本范围 | 100 行匹配，incomplete=false | 100 行匹配，incomplete=false |
| `execution_ast_search` | 2 次，两次命中 | 3 次：两次零匹配后修正模式命中 |
| 原生 read | 2 次 | 1 次，核实零匹配原因 |
| Shell 搜索回退 | 0 次；无 Shell 调用 | 0 次；无 Shell 调用 |
| `execution_status` | 成功返回实际工具/技能/RTK 计数 | 成功返回实际工具/技能/RTK 计数 |
| RTK | 1 次 eligible/filtered，9,791→1,074 字节 | 1 次 eligible/filtered，9,791→1,074 字节 |
| 原文 | 私有 0600 日志，逐字节校验全部 100 行一致 | 私有 0600 日志，逐字节校验全部 100 行一致 |
| 结果 | `total(2,3)=5`，awaiting_review | `total(2,3)=5`，awaiting_review |
| 源码 | 主 checkout 干净；任务源文件与基线一致 | 主 checkout 干净；纯净任务 worktree 干净 |

全局探针第一次 AST 模式遗漏返回类型/可见性，返回零匹配；模型明确说明不能据此证明不存在，通过 read 核实，再以完整模式命中。该恢复行为通过，但仍有额外调用开销。隔离探针还完整读取了重复文本，故 RTK 的显示字节缩减不能解释为整段会话 token 或任务耗时同比下降。函数返回值是源码推导，本只读探针未执行该函数或构建业务工程。

应用后的云端 `cloud-workflow` 复验使用 `openai/gpt-6.1-sol#low`，7 次调用全部成功：`quality-review` 技能、read/glob/grep、Context7 resolve/query、quality_info。云端看不到本地 execution 专用工具。Context7 返回的插件示例仍须核对实际宿主版本；本次证明工具链可调用，不背书所有文档内容。Plannotator 人工审批界面和 Quota Desktop 展示仍未重新实测；既有 mobile 插件加载异常保持独立记录。

全局配置启用结构化搜索；云端角色继续继承会话选择，本地角色继续绑定 Strata。私有生成器同步该开关及受管源文件，Serena/browser 仍为 off。应用后本地模型、云端 low、全局插件和源码完整性均复验。可用证据证明路由及工具实际使用，不能承诺一般任务耗时或推理 TPS 提升。

## 发布检查

93 项 Python 和 48 项 Node 回归在发布前重跑通过，Node 无跳过项；初次受限运行因宿主不允许嵌套 sandbox-exec 及缺少测试 PATH 失败，在完整权限与固定工具环境重跑通过。开发分支 GitHub CI 通过。发布内容仅为配置生成器、插件、技能、回归和脱敏说明；私有模型映射、地址、令牌、会话标识、业务源码和原始日志不上传。
