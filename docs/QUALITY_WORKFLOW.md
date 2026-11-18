# 质量工作流：从计划到交付

本扩展保留云端规划/审计、本地实施/测试的职责，增加独立计划审查、结构/测试审查和可重算的证据门禁。它由原生角色配置、两个技能、Python 工具和只读 MCP 组成，不修改 OpenCode Desktop 源码。

## 日常流程

首次在主规划入口提出任务时，协调者自动调用 `quality_onboard` 接入当前目录，再继续需求流程，无需手动登记。已有登记原样复用；未登记工程识别最近Git根或工程标记，列出实际规范文件并保存本机原生模式。空Git工程没有规范时保留空清单，不能伪造规范；完全没有工程标记的任意目录不会自动登记，正常授权初始化后再接入。接入状态会明确显示登记/复用和模式，不能当业务验收PASS。

新工程默认原生模式，沿用真实工程检查入口；不自动导入仓库里的可执行策略或编造测试命令。已有通用模式及手工策略保持。需要显式使用通用机器门禁的项目，仍可按下文核对命令后配置；这不是普通新工程接入的必经步骤。

这是首次任务时由协调模型调用工具的自动接入，不是Desktop打开目录的后台监听插件。使用更新后的主规划入口，旧会话可新建以加载新提示。未连接quality MCP时明确报告工具不可用，不能声称接入成功。

提出需求 → GrillMe 澄清 → 确认需求/设计 → 云端写计划与契约 → fresh cloud-plan-review 检查并修正计划 → 确认计划 → local-worker 实施/TDD/检查 → 云端独立审计 → 原会话修复复验 → 复审 → quality_gate → 归档后再核验 → 最终交付。

低风险仅必需 plan/code 两类审查；medium/high 还需 structure/tests。cloud-review 的 BMAD quick 审计仍通过真实独立子会话进行，专项视角按风险开启。所有 cloud-* 角色继承 models.local.json 的 cloud 默认模型/档位，可分别覆盖；local-* 沿用服务参数，无新增思考强度。

审查采用平级会话：主 cloud-workflow 直接派发 code、structure、tests，再收集原文并交代码审查综合裁决。审计子代理不再派子代理，兼容 Desktop 的单层深度限制；不会为此提高宿主深度或跳过必需视角。检查数量与批准方案冲突时停止并上报，不添加无用模块凑数量，策略变更需明确裁定。

协调者可将子审查的原文与JSON直接保存到 `.quality/reviews/`，避免本地模型再次转写；新增权限只覆盖该目录的报告文件。审计子代理保持只读；实际命令、执行日志和回执仍由本地worker生成。报告原文不得改写或覆盖历史，归档权限不赋予修改源码、测试、执行证据或策略的能力。

## 从零安装扩展

先完成根 README 的基础配置、模型登录和技能依赖。Python 3.9+ 可运行本扩展；官方 BMAD 渲染需要单独 Python 3.11+、Jinja2 3.1.6 和 MarkupSafe 3.0.3。本版本依赖 POSIX fcntl/进程组，仅验证 macOS/Linux 路径，Windows 未验证。

下载固定上游，不执行自动更新：

```sh
git clone --no-checkout https://github.com/bmad-code-org/BMAD-METHOD.git /absolute/path/bmad-source
git -C /absolute/path/bmad-source checkout --detach e435a22574fe55722841086e5566420178b98df3
python3.11 -m venv /absolute/path/bmad-render-venv
/absolute/path/bmad-render-venv/bin/python -m pip install Jinja2==3.1.6 MarkupSafe==3.0.3
```

在本仓库根目录先预览，再应用。替换占位绝对路径；不要填写服务密钥：

```sh
python3 setup_quality.py --models models.local.json
python3 setup_quality.py --models models.local.json \
  --source /absolute/path/bmad-source \
  --render-python /absolute/path/bmad-render-venv/bin/python \
  --project /absolute/path/project \
  --policy /absolute/path/approved-project-quality.json \
  --apply
```

`examples/project-quality.python.json` 是 unittest 示例，要求测试在 tests/ 下；先核对项目再登记。不要让模型随意改变登记策略。普通新工程由首次任务自动接入，不必重复安装；只有显式选择通用机器门禁或更新执行策略时使用管理命令。相同安装输入不创建多余备份。运行配置与策略保存在本机，不进入Git。

安装会：先检查所有输入/冲突，再用官方 renderer 在独立运行目录生成 no-code/noninteractive 资源；备份现有配置/状态/技能/登记；合并 quality MCP 和新角色；保留已有Provider、上下文、压缩、无关MCP/角色和自定义权限限制。仅完全匹配旧版默认权限的列表会迁移到新默认值；若已有特别限制阻止新角色/MCP，保留限制并在实际验证时报告阻塞，不静默扩大权限。

官方源与定制说明见 `integrations/bmad/lock.json`、`overrides.toml`：当前选定的是固定 v7 preview 提交，不冒称稳定v6.12。上游原文件不改，官方render输出连同资源/许可保存在私有版本目录。宿主适配取消强制发现数量，要求复核全部测试缺口，禁止修改批准计划。原始BMAD技能不额外暴露为可自动触发的全局技能，避免另起一套编排。

## 可读契约与机器校验

### 已有原生验收体系的工程

若工程要求任务计划与验收留在任务上下文，或已有正式质量体系，使用显式 `repository-native` 注册。不要为接入本工具在该工程另写一套规格、账本或验收 Authority，也不要通过放宽快照限制忽略大型工作区内容。

在本机私密文件中写清接入说明，引用项目实际的规范和验证入口，不写凭据。示例：

```sh
python3 setup_quality.py --models models.local.json \
  --source /absolute/path/bmad-source \
  --render-python /absolute/path/bmad-render-venv/bin/python \
  --project /absolute/path/project --repository-native \
  --authority AGENTS.md --authority PROJECT_CONSTITUTION.md \
  --native-instructions /absolute/path/private-project-instructions.md --apply
```

原生注册不接受 `--policy`。`quality_info.project_profiles` 提供模式、项目内规范路径和私密接入说明；协调者必须在创建任何文件前识别模式。原生项目的 `prepare/run/gate` 只返回 `REPOSITORY_NATIVE_REQUIRED`，CLI退出码2，不读取通用契约、不扫描源树、不执行命令、不生成文件或通用PASS。它是接入路由，**不是完成产品验收**。

云端仍规划并独立审计，本地仍实施和复验；验证按项目规程及实际任务影响选择，结果由原生质量体系判定并在任务上下文记录。原生规则、执行环境或所需证据缺失时保持未完成，不退回通用模式求通过。原通用项目的契约、快照、执行和门禁不变。

正式需求仍遵守项目自己的规则与权威。每项必要REQ关联任务和AC，AC/ARCH关联已登记lane。JSON字段见 schemas/，完整示例见 examples/contract.example.json；不要保留示例批准句，实际填入真实确认原文。`simulated=true`仅用于明确的一次性测试。未确认plan写PENDING，runner不会执行；独立计划审查可以先运行。

semantic contract_id仅包含version、requirements、plan。后补批准引文不使已审的相同语义计划失效；任何需求/计划内容变动都会改变ID。批准引文是审计记录，不是不可伪造签名。

本包以一个受限JSON Schema词汇校验已发布schema（类型、必填、禁止多余字段、数组/数值边界、enum、pattern）；不冒充完整JSON Schema通用验证器，未知schema关键词会被拒绝。schema结构合法也不代表业务要求正确，须独立云审。

## 工具与证据

- `quality_info`：列明确登记的工程及固定公开资源名。
- `quality_onboard`：按当前目录识别/复用/登记工程，仅写固定本机注册表及0600备份，不接受模型提供的策略或命令，不写工程。注册和安装共用文件锁；各会话请求刷新注册表。
- `quality_resource`：按逻辑名提供固定schema与BMAD公开资源，校验部署摘要、去除安装路径；不读取任意目录，不增加外部目录访问权限。
- `quality_prepare`：只读校验契约、返回语义ID、当前源树快照和必要审查种类。
- `quality_gate`：只读重算当前证据与审查裁决，不执行命令。

只有主规划角色获准调用自动登记；审查子角色保持只读。注册MCP因此不再是全体只读：唯一写操作是受限本机登记，其余四个工具为只读。注册不会扩展工程外文件访问权限。

实际执行由本地模型通过已安装技能里的确切Python/runtime/settings路径调用 `python -m workflow run ...`；仅执行私密登记的argv策略，不接受review文本临时提交命令。unittest解析真实数量和skip；json适配器要求底层检查器输出checks/skipped/failures，不能使用手填成功数字。空扫描、缺工具、超时、失败和源文件变化均不能当通过。

每轮在 `.quality/runs/` 保存唯一运行原件，先登记最新尝试再运行；中断/后续失败使旧PASS不可复用。日志唯一命名、带摘要。MCP gate只允许工程内保留证据目录的日志引用。`.quality/logs`及其祖先符号链接在运行前拒绝。

源树快照包含内容与文件权限、dirty/untracked；排除依赖/缓存、.quality、docs/superpowers/evidence、.env*、*.pyc、*.log，排除项随快照明列。被排除内容不能宣称已审。快照上限100MB/10000文件，符号链接与非普通文件拒绝，不会静默丢弃超量范围。

## 审计报告、问题分级和历史闭合

报告schema为 schemas/review.schema.json。每个kind每轮递增round，原文与JSON保存 `.quality/reviews/<kind>-<round>.md/.json`。保留旧报告，不能只留latest覆盖原件。gate会检查目录中所有适用轮次，选择每种kind最高轮次，旧clean报告不能隐藏新阻塞。

每项发现记录位置、证据、后果、范围、可信度、严重性、新增/历史、动作和状态；另列修复价值、工作量、回归风险、验证方法。风险分项impact/likelihood/breadth/time为0–5或null；自定义风险分仅排序，不是CVSS/ISO认证。未知不能填0淡化风险。

任何未解决fix/decision/investigate或critical/high/medium问题阻断。只有低等级、preexisting债务可有条件通过，必须明确owner/until/reason/accepted_by/trigger；实现模型不能批准自己的豁免。人工接受身份字段仍需外部流程核对。

历史阻塞必须显式关闭：新报告的closed_findings填id=`kind:旧round:旧finding-id`、reason和evidence=`当前snapshot:实际通过的lane-id`。失败/空/skip lane不能关闭问题。当前resolved finding的resolution_evidence使用相同格式。验收链接能防止漏项，不证明语义修复正确；独立审查仍需读代码。

最终状态：PASS、PASS_WITH_DEBT、NEEDS_EVIDENCE、BLOCKED。所有必要lane和审查完整且绑定当前代码才可通过；任何计划/代码/测试/策略变化须重验相关结论。最终归档再调用gate，避免收尾改了已审字节。

## 架构与测试有效性

`workflow/structure.py`提供显式scope的Python AST禁止导入检查，示例：

```sh
python3 workflow/structure.py --root /absolute/path/project --source app --forbid app.core:app.api
```

它不能分析动态导入、业务所有权或所有循环，不冒称完整架构证明。其他语言在项目策略中接既有工具，如dependency-cruiser、Import Linter，Rust使用cargo metadata与明确规则；cargo-deny管外部依赖政策。

`examples/mutation_probe.py` 可在隔离副本对指定Python函数做一次显式返回值变异，记录基线与变异真实测试日志，检查断言是否能发现错误；这不是通用变异覆盖率工具。它拒绝绝对/越界源路径，不修改原工程。

关键逻辑可接属性/变异检查。实际工具的目标、输入域、mutator、等价变异、排除及失败阈值都要登记；不将覆盖率/变异分当需求正确性保证。Loom/Kani/Pact/TEA等按项目风险另验收，不自动全量安装。

## 备份、恢复及边界

备份目录由安装输出给出，manifest.json列出每个路径、是否原先存在及对应备份。任务结束后按manifest恢复原文件；原先不存在的扩展文件可移除。不要用整份旧配置覆盖之后新增的无关配置；有并发改动时先合并。私有版本runtime保留便于旧会话继续读取；卸载应在所有相关任务结束后进行。

这是原生模型协调＋确定性一致性检查，不是不可绕过的OS沙箱。源树哈希、报告字段和本地日志不能证明最初真实性；同账户进程仍可篡改文件。若要强制阻止远端合并，需要受信CI重跑、required checks、可信状态来源、策略审批和bypass约束。本仓库CI只做自身测试，不自动替用户业务仓库建立这些权限。

云端额度、网络、MCP审批、模型流中断和工具不可用可能阻塞；应保留失败并恢复，不能跨云/本地静默兜底。最终能承诺的是特定版本和验证范围内满足已确认要求，不是零缺陷。

## 实施前的独立计划门禁

协调者可在尚未批准的计划文档范围内，原样保存审查记录到 docs/superpowers/plans/reviews/。质量 prepare 接受可选 plan_reviews 路径列表，返回独立 plan_gate。它只判定当前语义计划是否就绪，不执行产品检查；同一contract下的旧计划发现可通过 contract:<当前contract_id> 和独立文档核验说明关闭。代码审查仍要求实际通过的当前lane。

非schema原件保存 raw-*.md，不能伪装成有效gate JSON；新完整轮次可替代旧不完整backend轮次，但已报告的真实阻塞不得消失。新语义contract需新独立计划审查，旧contract报告原样保留作来源，不能作为当前通过指针。
