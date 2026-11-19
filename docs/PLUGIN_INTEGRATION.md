# 文档、额度、计划评审与隔离实施

继续使用云端会话选择的模型/档位进行规划和独立审计，local-worker 使用固定本地模型实施、测试及修复。插件不负责自动降级或选择另一模型。本地推理/输出参数不增加工作流覆盖。

## 安装与迁移

1. 备份已有配置，按 README 准备真实 Provider/OAuth 与完整技能。
2. models.local.json 中保留原模型映射，增加：

```json
"extensions": {
  "context7": true,
  "quota": true,
  "plannotator": true,
  "worktree": true
}
```

3. 按 QUALITY_WORKFLOW.md 准备固定 BMAD checkout 和 renderer，然后运行 setup_quality.py 预览及 --apply。安装器备份主配置、生成状态、质量技能、项目登记和本次涉及的插件偏好；合并原权限，保存无关配置。严格 JSON 格式，不解析 JSONC 注释；遇到注释文件拒绝覆盖，不自行删注释。单独 configure.py 不安装这些独立偏好。
4. 等待首次包解析完成，在 Desktop 的 Extensions / Plugins 中核对激活。包和 integrity 固定在 integrations/plugins.lock.json：Context7 0.2.2、Quota 6.3.0、Plannotator 0.28.67。OpenCode 2.3.x、Git 和本机对应运行依赖需可用；包由宿主解析安装，不把 node_modules 放进配置仓库。
5. 首次 Context7 查询需要它自己的 OAuth：`opencode mcp auth context7`，在浏览器授权；此登录与 OpenAI 登录不同，不随仓库迁移。不能把 needs_auth 当作可用。
6. 新建会话，按下文小任务验收。全新机器仍需分别登录云端与 Context7；不复制 auth、token 或 service 文件。

启用/禁用由映射文件统一管理，生成器只移除自己记录的插件条目。同名非托管包、被外部修改的托管选项会拒绝覆盖；先明确迁移来源，不静默安装两个版本。已有自定义角色权限若不同于工具管理的列表，不自动放宽；需确认具体工具限制。

## 具体行为

Context7 提供 `context7_resolve-library-id` 和 `context7_query-docs`。真实 V2 权限动作保留连字符，不能写成下划线。各工作流角色可查询公开依赖文档；先识别锁定版本，不向文档服务提交私有源码或秘密，不以第三方文档覆盖工程契约。

云端审查还获得 Plannotator 已批准 plans 目录的窄外部读取权限，用于核对批准原件；不会因此开放其配置、凭据、任意用户目录或 shell。交接仍需包含完整当前计划、准确差异（含未跟踪文件）和原始执行回执，不能只给一个不可访问的路径。该目录按默认数据位置生成，自定义数据路径需显式适配。

Quota 使用 Desktop GUI/RPC 观察供应商数据。安装器设置 `providers.checking.waitForQuotaReset=false`，不接管宿主重试；关闭 exportFile/telemetry。UI面板及标题栏入口可显示额度，成本估算不是订阅实际账单。本地服务没有额度 API 时不虚构剩余额度。避免将 `/quota_status` 当成纯只读诊断：上游部分诊断路径会登记发现的 Provider；GUI RPC status 不执行此登记。插件仍会读宿主凭据并访问对应供应商，不是零网络的本地显示器。

Plannotator 使用 `user-managed`，planningAgents 为 cloud-workflow/design/plan。仅主规划角色获准 submit_plan，叶子审计和本地 worker 不负责批准。安装器在其数据目录 config.json 设置 `agentSwitch: "disabled"`，批准后保持当前云端角色，防止默认切到 build；其余用户偏好保留。之后由协调者正常委派 local-worker。计划工具和 UI 存储在 Plannotator 自己的数据目录，原生工程不因此强制创建通用规格/契约。改变 PLANNOTATOR_DATA_DIR 等上游环境路径后，必须重新核对这些偏好的实际生效位置。

批注、请求修改、独立审查 READY 与用户批准是不同状态。修订必须重新显示当前计划并批准。UI 本身不能替代业务验收；测试驱动器的模拟批准必须明确标识，不能挪作真实需求授权。保留当前工作流的云模型身份提示。

## Worktree 规则

主规划入口使用 `workflow_worktree` 封装宿主原生 worktree.create 和 session.move。它保留嵌套工程的仓库相对目录，移动后在下一轮接入新目录；当前已是 linked worktree 时复用。没有 Git 时停止，不隐式初始化、stash 或清理用户工程。新 worktree 从已提交源码建立，不包含原目录未提交内容；如任务依赖这些内容，先明确基线，不能悄悄迁移。

运行时检查 Git 公共目录、子模块与 reciprocal backlink；复制一个真的 .git 文件也不能冒充独立 worktree。原目录不能派发本地实施，处于原目录/其他任务目录的旧 worker 不能被直接续跑。local-build/worker 的原目录修改和 shell 调用会被阻断；只读讨论和文档查询不要求创建 worktree。

工程登记依据同一 Git 来源继承最近适用的原生/通用策略，不能从 portable 默默降级为 native。已登记多个冲突策略时停止；可执行策略中明显指向原目录的绝对参数（含 --option=/path）拒绝继承，要求先适配。没有声称能静态识别任意脚本内部的间接访问。

原工程只读适配由 worktree-policy 自动完成，不需要每个新工程增加绝对路径白名单。根据当前 Git worktree 注册记录、公共 Git 目录和双向 backlink 找到同一仓库的主 checkout；普通非 Git 目录不获得授权，伪造或不安全 Git 关系停止。首次会话请求在配置角色加载后追加权限，保留模型、Provider 和已有显式外部目录拒绝。

原工程通过原生 `read` 读取文件或分页列目录；不自动复制未提交内容，裸 commit 也不能代表 dirty 基线。新增原工程访问仅适用于托管 cloud-* / local-* 角色，不开放其他工程、同名前缀目录或整个人目录。原工程的 edit 被拒绝，敏感文件（.env*、.git、.ssh、.aws、.config、pem/key）及符号链接越界读取被拒绝。原工程 grep/glob 和覆盖其父目录的搜索停止，改用 read：当前宿主 grep 不检查每个结果的 read 权限，不能以允许目录搜索换取凭据泄漏。其他目录的既有权限仍以原配置为准；这不是任意命名秘密的通用识别器。

macOS 的模型 shell 在创建时切换到同方言名的隔离启动器，内部使用 `/usr/bin/sandbox-exec`；原始 command 不变，继续经过宿主原来的命令和外部目录权限检查。沙箱禁止 shell 读取或修改主 checkout 文件，即便脚本使用相对路径、变量或符号链接。原工程内容通过直接 read 获取，worktree 文件仍可读写；共享 Git 公共目录保留读写，用于 worktree 提交、对象与 refs，**不承诺 Git 元数据只读或秘密识别**。这种路径隔离不支持已存在的跨目录硬链接：worktree 中若有与原工程共享 inode 的文件，必须先改成独立副本；普通 Git worktree 不自动创建这类硬链接。这并非整个宿主的访问锁：手工进程、尚未初始化插件的底层 shell API、其他应用/外部服务及既有进程不受此钩子接管；不要把系统保护关闭或外部代理当绕过通道。当前版本只认证 macOS；其他平台 shell 拒绝执行，无不受保护的降级。迁移 Linux/Windows 需先实现并验证对应进程隔离。插件不会自动合并、推送业务工程或删除 worktree。交付保留工作区路径、branch或detached HEAD、提交/差异和验证证据，合并按任务授权单独进行。

## 验收小任务

在可丢弃 Git 工程开始一个小需求，云端选择账号实际支持 low 档位的模型。本次测试选 gpt-6.1-sol#low；这不改变日常默认，更不向本地模型设置 low。

- 确认澄清、计划审查和代码审查实际 assistant.model 均为所选云模型/low。
- 确认 Context7 两项真实查询成功；Quota Desktop 面板显示供应商值和检查时间。
- 在计划 UI 添加中文批注，请求修改；本地实施不得启动。修订后批准，主会话仍为云端协调。
- 确认 worker 实际目录为 linked worktree、模型为固定本地，无新增命名推理档位；真实运行项目检查。
- 云端读取当前源码/测试与执行证据，有问题交回原 worker 修复、复验和复审。
- 原 checkout 的 HEAD、状态和源码内容保持；没有把 idle、READY 或工具加载当成最终完成。


本地执行能力的统一配置、受管技能、RTK 接管及可选进程限制见 [EXECUTION_EFFICIENCY.md](EXECUTION_EFFICIENCY.md)。
