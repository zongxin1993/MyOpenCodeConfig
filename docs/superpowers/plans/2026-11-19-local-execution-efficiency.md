# MyOpenCodeConfig 本地执行效率集成计划

> **For agentic workers:** REQUIRED SUB-SKILL: 执行经确认的计划时使用 executing-plans；OpenCode 中云端规划/审计，同一个固定 local-worker 实施/测试。不得采用技能默认的另派实施者或模型切换。步骤按复选框追踪。

**Goal:** 将 RTK、ast-grep、短版执行技能、精选 Rust 技能及可选 Serena/Playwright 集成进可移植配置，以总耗时与验收质量决定启用。
**Architecture:** 复用现有纯配置生成、受管状态、事务备份和不可变运行时。以 execution 字段选择能力，CLI 和 MCP 使用不同权限适配，技能按需加载。
**Tech Stack:** Python 配置器、OpenCode V2 Promise plugin、Node.js、固定上游 CLI/skill、stdio MCP。
**Spec:** ../specs/2026-11-19-local-execution-efficiency-design.md
**Status:** 用户于2026-11-19明确批准“开始执行任务，云端还是用 low 模型，最后上传到 github”。基础能力已实施，真实验证与发布记录见 docs/EXECUTION_EFFICIENCY.md。Serena/browser未通过独立认证，保留off；不标记为已验收能力。

## Global Constraints

遵守设计 R1–R10；当前可核对基线为 4152312。首批认证 macOS/OpenCode 2.3；移植系统未验收时不能降级为无保护运行。现有工程门禁与规范优先，不降低测试要求。审批、配置成功和工具加载不等于业务验收。未来执行时重新 fetch 并核对 HEAD/origin/master/worktrees/dirty 状态，不把此计划基线当最新事实。

## Review Focus

1. 已存在自动发现 RTK hook，接管不得双重改写或覆盖第三方修改（任务1/2）。
2. 命令重写改变权限、管道、退出码或原始日志，尤其固定验证入口（任务2）。
3. Serena 缓存/语言服务器写原目录或切换到另一任务 worktree（任务5）。
4. 大型技能重复规划、超范围设计、猜过期符号或压缩工具不存在（任务4）。
5. 冷启动、缓存预热、并行请求及验收强度不同导致假提速（任务7）。

## 文件布局及接口（拟新增）

- `integrations/execution.py`：解析并验证 execution 配置、能力策略，不执行外部命令。
- `integrations/execution.lock.json`：CLI release/平台/摘要、适配器来源 commit/摘要、许可证与资源记录；Serena Python传递依赖锁、语言服务器版本、Node运行时要求和Playwright浏览器revision也必须覆盖。固定内容后才能启用，不使用 latest。
- `plugins/execution-tools/index.js`、`package.json`、`access.js`与各能力模块：OpenCode V2 的 RTK 受管接入、ast-grep只读结构搜索、按会话worktree绑定和可见性。
- `workflow/execution_setup.py`：本机依赖预检、既存安装辨认、安装计划和受管工件事务；复用现有安装器事务，避免第二套写配置框架。
- `skills/local-execution/`、`skills/rust-diagnostics/`、`skills/ast-grep/`：短版执行协议、精选适配、官方搜索技能及支持资源。
- `integrations/serena/`、`integrations/playwright/`：固定启动参数、最小能力白名单和可选适配资料。
- 修改 `configure.py`、`setup_quality.py`、`models.example.json`、`skills.lock.json`、`templates.json`、README和现有配置/验证文档；按以下任务增加有实际失败模式的测试。

拟定 Python 接口：`parse_execution(raw: dict | None) -> dict`（缺省为全关闭且不影响旧输出）；`plan_execution(home: Path, options: dict, lock: dict) -> dict`（只返回预检、受管/外部归属、冲突、待写工件）；`execution_runtime(home: Path, options: dict, lock: dict, release: Path) -> dict`（生成配置及私有运行时引用，仍由现有 compile_config/安装事务合并）。实施时以小模块实现，不复制原安装器。CLI工具安装是显式setup动作，不在模型任务中自动brew/npm安装。

### 任务1：配置、依赖锁、备份与迁移

Files: 修改 configure.py/setup_quality.py/models.example.json/skills.lock.json；新增上述 execution.py、execution_setup.py、execution.lock.json；测试 tests/test_execution_config.py、tests/test_execution_install.py。
Consumes: 现有 compile_config(base, models, templates, previous) 和安装器事务。
Produces: parse_execution / plan_execution / execution_runtime 及生成状态中的独立 execution 工件归属。

- [ ] 先写失败测试：旧映射逐字等价、未知字段/无效mode拒绝、关闭仅删除自己记录的工件、Provider/OAuth/压缩设置不变；外部RTK/技能碰撞拒绝覆盖、符号链接拒绝、失败中途恢复、重复生成无差异。
- [ ] 运行 `python3 -m unittest discover -s tests -p 'test_execution_*.py' -v` 确认新增接口缺失导致失败。
- [ ] 从官方上游取得固定release/commit及摘要，记录本机RTK版本和现有hook来源；锁本身、许可证、依赖资源完整后才允许安装。平台或所需版本不匹配在apply前失败。依赖放在私有版本目录、用绝对可执行路径启动；部署后离线启动，禁用运行期自动下载，升级先并列准备新版本，再事务切换，保留旧版供回滚。可选关闭项不要求依赖存在。
- [ ] 先备份主配置、受管状态、现有自动发现插件/技能及偏好和本机能力映射。现有setup_quality事务不足以原样复用：对每个待写目标记录前后字节摘要、归属和恢复工件，apply及异常/中断恢复逐项检查并发修改；有冲突停止恢复该目标并明确记录，不能覆盖第三方新改动。加入故障注入和用户并发修改测试。RTK确认为相同来源时预览接管并迁移为唯一受管hook；未知内容停止接管，不同时运行两个版本。枚举固定宿主实际支持的用户/工程自动发现目录、受管列表和npm插件入口；任何未知重复项先阻止启用。旧hook移除、新hook注册必须属于同一事务，异常恢复后仍只能有一个有效入口。
- [ ] 将新工件及实际启用技能的必要references/许可加入现有不可变release摘要/复制/完整性校验，并将受管技能安装到宿主可发现位置；新增技能发现/加载与资源完整性测试，不能只复制SKILL.md。运行上述测试变绿；中断后生效配置不留半安装状态。
- [ ] 独立检查迁移差异后形成阶段提交；不改或推送业务工程。

### 任务2：RTK 精选输出过滤与原始证据

Files: plugins/execution-tools/rtk.js；tests/test_execution_rtk.mjs；扩展任务1的安装测试。
Consumes: 任务1锁与归属、现有 worktree-policy 和角色权限。
Produces: 一个 RTK hook，safe-output 策略和可追溯原始输出位置。

- [ ] 先验证固定宿主是否允许保持原command的输出后处理；若可忠实保留退出码、原始证据和权限语义则优先使用。只有不能满足且命令重写测试全部通过，才采用上游rewrite路径；不得在两层同时过滤。

- [ ] 写实际命令fixture负例：原生deny/ask不因改写放宽；非零退出不变；管道/重定向、相对路径、空格路径、未知shell保持原样或拒绝，不执行猜测的重写。
- [ ] `node --test tests/test_execution_rtk.mjs` 先红后绿。V2事件/权限按固定宿主版本核对，不能仅依据RTK注释承诺。
- [ ] safe-output仅纳入已验证的列表和搜索输出；原始测试入口、审计diff、完整源码、证据记录命令不改写。证明RTK与source只读shell wrapper顺序组合正确。
- [ ] 工具不可用时原命令只在原权限仍允许时直通，不增加模型重试；过滤结果不可用按既有RTK规则恢复原文，不伪造证据或重复历史测试。
- [ ] 新会话真实运行：工具输出缩短、错误仍可定位、原始日志可读、原目录源码不变；记录总耗时而非只记录gain。

### 任务3：ast-grep 官方 Skill 与只读结构搜索

Files: skills/ast-grep及其references；plugins/execution-tools/ast-search.js；tests/test_execution_search.mjs；更新skills.lock.json与能力锁。
Consumes: 固定 CLI、固定官方skill、会话实际worktree，以及共用access.js授权检查。
Produces: 本地只读结构搜索；可返回文件/范围/命中数量/截断位置。

- [ ] 先实现统一调用边界：核对实际调用角色、session与当前linked worktree，规范化目标路径，并通过按固定宿主SDK核实的授权接口（如permission.assert）保留read/external_directory的原有deny/ask；若宿主不能提供所需逐资源授权，相关能力保持关闭，不自造allow（包括worktree内被禁止读取的文件）。原生规则不能只靠新工具名称替代。自建execFile/MCP/browser入口均需使用相应边界，不能以shell wrapper已存在为由跳过。
- [ ] 写 Rust/Python/TS小fixture：语法模式、零命中、错误规则、非零退出、结果截断、路径空格、symlink逃逸、原目录/其他worktree访问拒绝；只读入口不接受rewrite选项；排除受保护秘密文件及忽略目录，不能通过结构搜索返回密钥内容。
- [ ] `node --test tests/test_execution_search.mjs` 先红后绿；CLI缺失在启用预检中报告，不在每次任务里下载。
- [ ] 源码归属不能凭零命中判不存在；复杂模式先对已知小样本验证。普通字符串/文件定位继续rg，结构查询才加载官方skill，禁止强制所有搜索转AST。
- [ ] 新工具只向已授权的local-worker/local-build/local-inspect暴露，保留各自只读或实施边界；云端不因此获得shell或源代码编辑。显式绑定搜索root为当前worktree；原工程核对仍走既有直接read规则，不能借结构搜索绕过只读/秘密保护。
- [ ] 与RTK组合时只压缩展示，不破坏JSON解析或丢掉必要坐标；真实调用由本地模型完成一次后验收。

### 任务4：短版执行协议与精选 Rust 诊断技能

Files: skills/local-execution/SKILL.md、skills/rust-diagnostics/SKILL.md及必要references；templates.json；tests/test_execution_skills.py；更新skills.lock.json。
Consumes: 已批准计划、原生/portable profile、原审计反馈和实际编译结果。
Produces: 精简交接和按需技能路由；不生成第二份需求权威。

- [ ] 写语义检查：实施只到当前worktree；没有批准不动代码；原生工程不产生portable门禁；同一worker修复；禁止本地新建审计者/额外云端编辑；没有compress/acp_status时不要求调用；工具最小范围和原日志要求保留。
- [ ] `python3 -m unittest discover -s tests -p 'test_execution_skills.py' -v` 先红后绿。文本检查只验证协议结构，不冒充模型遵循证明。
- [ ] 交接限制在目标/非目标、批准基线、实际路径与相关符号、验收命令、原始日志位置、停止条件；已知事实不重复调查。worker不重新写云端计划。
- [ ] 从Rust Skills精选ownership/error-handling/concurrency参考；按具体编译错误/风险触发，删除泛化的每个Result/async自动触发、额外子代理、实时新闻和动态技能生成流程。第三方建议不能覆盖工程领域契约。
- [ ] 真实模型fixture故意产生一种编译错误和一个业务边界错误：Strata按诊断修复；云端独立指出业务缺陷；同一worker修复复验；不得为了省轮次跳过审计。

### 任务5：Serena 最小符号查询（可选，单独验收）

Files: integrations/serena/启动适配与策略；workflow/execution_setup.py；tests/test_execution_serena.py；独立安全集成fixture。
Consumes: 当前worktree身份、固定Serena/语言服务器、独立进程隔离。
Produces: mode=off 或 symbols-readonly；只开放定义/引用/符号概览等必要查询。

- [ ] 用假MCP进程测试：根目录绑定、路径切换拒绝、原目录写入拒绝、MCP自带subprocess写入拒绝；证明不是靠OpenCode原生edit deny保护。
- [ ] 显式禁止编辑、rename、REPL、任意shell、记忆和onboarding；缓存写私有任务目录，不写原checkout，不共用可切换project实例。语言服务器子进程同样纳入sandbox；默认不执行未经批准的项目启动脚本。测试查询worktree内原生read deny/ask文件，不能绕过原权限。
- [ ] 按worktree独占实例；会话移出该目录、最后使用者退出、配置关闭、升级或崩溃时，只清理本适配器拥有的进程及子进程。测试孤儿进程/超时恢复，不使用全局kill-all；多个同worktree会话的共享或独占策略明确记录，默认独立任务实例。
- [ ] 核对V2 mcp.servers、能力动作名与Code Mode。按本地模型可用的最小接口适配；不拿V1 LSP配置直接套V2，不启动未固定依赖下载。
- [ ] 用真实Rust跨crate导航做冷启动/复用对照；同时记录索引时间、内存、引用完整性和工具参数失败率。
- [ ] 未通过隔离/性能/引用准确性则保持off，基础能力可独立交付；不能以退回无保护进程解决兼容问题。

### 任务6：Playwright CLI 浏览器验收（可选）

Files: integrations/playwright/启动和技能适配；tests/test_execution_browser.py；更新能力锁、配置示例及文档。
Consumes: 已授权Web验收需求、可丢弃fixture、独立worktree和浏览器profile。
Produces: browser=off 或 playwright-cli，按Web任务加载官方技能。

- [ ] 测试项目/session独立、浏览器状态不进仓库、不暴露已有个人profile；依赖缺失预检失败；CLI输出与完整截图/console/network工件可回读；工具调用核对角色和当前worktree，会话移动/关闭/崩溃/禁用时清理自有browser及子进程，不影响其他浏览器。
- [ ] 使用本地fixture验证点击、表单错误、等待条件、页面结果及真实截图；不要固定sleep模拟成功。
- [ ] 浏览器动作通过独立进程安全边界，不假定现有shell sandbox覆盖常驻browser daemon。沿用项目Web原生测试，不用截图代替业务验收。
- [ ] 仅在Web任务启用；不在每次Rust后台任务注入整套浏览器工具和技能。

### 任务7：组合验证与速度决策

Files: 新增可丢弃examples/execution-pilot/、tests/test_execution_regressions.py、docs/EXECUTION_EFFICIENCY.md；性能原始数据留本机不公开私有源码。
Consumes: 各任务已通过的能力与可独立关闭的开关。
Produces: 实际启用清单、性能/准确性对照表、关闭原因及未验证项。

- [ ] 首先运行 `python3 -m unittest discover -s tests -v`、`git diff --check`；现有68项基线不能回退。Node套件由Python集成或明确独立运行，不能遗漏。
- [ ] 固定服务参数、Strata绑定/无新增variant、并发1；测试主会话显式选择账号支持的云模型及low档位（不修改日常默认），所有云端子角色继承该会话选择，不写死另一个审计模型；同一对照组保持实际模型和参数一致。先记录当前工具/ACP策略，再原样用于对照，不能一边改压缩策略一边给新搜索工具记提速。
- [ ] 按相关性分配固定任务：RTK/ast-grep/Serena测跨文件定位，执行/Rust技能测实现+编译错误修复，browser只测带失败路径的Web验收；先单项筛选，再对通过者做相关任务组合复测，不做每个工具乘全部任务的无效全组合。每个有效对照组基线/候选交错各至少3轮，新会话和独立worktree。预先固定验收答案、最大任务时间、缓存策略和工具失败的计入方法；超时算未完成且保留耗时，不能剔除失败轮次。
- [ ] 分开记录冷/热构建缓存、Serena首轮/复用；指标为总墙钟时间、定位/推理/工具/编译测试/审计等待、无效调用、编辑失败、返工轮次、首轮审计通过率。RTK token统计仅诊断。
- [ ] 安全、需求正确性和必须门禁全部通过。以本地重复样本中位数改善作为保留依据；定义基线波动为同组最大值减最小值；若候选与基线中位数差不超过该波动，先判“无法确认提速”，需要更多样本才可改判。若质量变差，维持关闭并说明，不能声称确定提速。高级选项不通过不拖住基础交付。
- [ ] 校验云端实际模型与会话选择一致，worker实际模型固定、原目录源码保持；云端BLOCKED→同一worker修复→复验→独立复审流程完整跑通。
- [ ] ACP/原生压缩迁移另立任务，不在本批自动关闭正在运行的ACP或改auto开关。

### 任务8：部署、中文文档与脱敏发布

Files: README.md、docs/CONFIGURATION.md、docs/SKILLS.md、docs/PLUGIN_INTEGRATION.md、docs/VALIDATION.md和EXECUTION_EFFICIENCY.md。
Consumes: 通过独立审计的代码、真实能力/性能结果与安装事务。
Produces: 可从零配置、可自由选择、可卸载回滚的公开配置工程。

- [ ] 文档说明从零依赖准备、映射开关、默认/可选状态、当前平台限制、模型分工、权限、失败处置、依赖升级/摘要更新、逐项回滚；迁移机独立OAuth，不复制凭据或数据库。
- [ ] 部署前再备份生效配置/RTK外部hook/技能/registry等受影响文件；展示实际预览。活动任务不被强制重启；新会话验证后再逐步用于日常。
- [ ] 对受管文件做精确回滚测试：恢复备份仅覆盖本次仍相同版本的文件；若用户并发修改则停止并报告，不能用整份旧备份覆盖其新改动。
- [ ] 新鲜独立审计检查原工程只读、工具越权、重复hook、证据完整性、模型路由和测试有效性。阻塞问题修复并复审后才能发布。
- [ ] 扫描凭据、个人地址/路径/session、浏览器状态、索引与本机日志；公开仓库只放模板、固定来源锁、适配器、技能、测试和脱敏报告。
- [ ] 若获得本轮实施/发布授权：fetch对齐主线、提交、push master、fetch验证完全一致并等CI通过；任何未完成性能/高级选项标明未验收。当前计划请求本身不执行安装和推送。

## 交付顺序与最终体验

A：任务1–4，基础输出过滤+结构搜索+执行/诊断协议；B：任务5–6，按需高级能力；C：任务7–8，速度实证、部署与发布。不是一次把所有工具塞进每个请求。

使用者仍只提出需求并确认设计/计划。主对话展示实际协调/执行模型及worktree；worker自动选择已启用能力，完成实现和原生测试；云端审计失败自动回同一worker修复复验。安装只管理工具和配置，不把测试、审计或用户批准变成形式上的PASS。


## 一手资料与计划审阅

- RTK：https://github.com/rtk-ai/rtk
- ast-grep官方技能：https://github.com/ast-grep/agent-skill
- 精选Rust技能来源（非Rust官方）：https://github.com/actionbook/rust-skills
- Serena能力与安全：https://oraios.github.io/serena/01-about/035_tools.html 、 https://oraios.github.io/serena/02-usage/070_security.html
- Playwright CLI：https://github.com/microsoft/playwright-cli
- OpenCode V2权限与MCP：https://opencode.ai/docs/permissions/ 、 https://opencode.ai/docs/mcp-servers/

本计划经过一个独立Codex审阅者检查并复核，当前未发现新的文档阻塞项；已纳入工具入口权限、完整RTK发现范围、每目标并发安全恢复、传递依赖锁、进程生命周期及收窄对照实验等反馈。这是文档审阅，不是OpenCode OAuth真实运行验收，也不是用户实施批准。


## 实施记录

已按独立审阅修复安装并发恢复、活动工具staging安装、完整RTK发现、受管技能修改保护及AST权限等待文件身份问题。上游技能许可不明确，改为原创短适配并保留固定来源；这项调整已记录，不伪称分发官方完整技能。CLI样本对照已完成；有其他本地客户端活动，端到端A/B不具备排除干扰条件，未声称稳定提速。高级能力预检失败关闭是本计划的发布边界，不是该能力安全验收通过。
