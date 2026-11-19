# MyOpenCodeConfig

一套可迁移的 OpenCode Desktop 配置：**云端模型负责需求澄清、工程规划和独立审计，本地模型负责代码编写、测试与修复。**

你用普通语言提出需求，确认设计和计划，之后由主协调者自动委派。正常工作不需要输入阶段命令，也不用自己在模型之间传递审计意见。

新需求会先创建独立 Git worktree 并移动会话，代码、测试和修复都在其中完成，原 checkout 保留。已在 linked worktree 时复用，不为修复反复创建。没有 Git 或隔离失败时停止实施；不会自动 stash、reset、合并或删除原工程内容。

新增可选集成：Context7 查版本文档、Quota 显示额度、Plannotator 可视化批注和批准。使用示例映射会开启三项及 worktree 策略；需要按下文完成 **setup_quality.py 完整安装**，才能一起配置插件偏好和权限。记忆及 DCP 不包含在本组合内。详见[插件与隔离工作区](docs/PLUGIN_INTEGRATION.md)。

本仓库保存脱敏配置模板、生成器和模型映射示例，并提供一个无额外依赖的 V2 云端会话路由插件，不修改 Desktop 源码。GrillMe 与 Superpowers 作为技能依赖安装；质量扩展提供独立计划审查、固定版 BMAD 只读审计与证据门禁。

已有正式质量体系、要求任务材料留在上下文的工程，采用[仓库原生验证模式](docs/QUALITY_WORKFLOW.md#已有原生验收体系的工程)。云端/本地分工保持，验收沿用项目门禁；不在仓库另建协议或伪造通用PASS。下面的流程图描述显式配置通用机器门禁的项目；新工程自动接入默认采用原生模式。

首次在主规划入口提出任务会**自动接入工程**：识别根目录与规程、复用已有登记，或创建本机原生模式登记，再继续任务。不需要每开一个工程手动执行注册命令；不会因此修改工程、启动环境或运行测试。通用机器门禁的可执行策略仍须明确核对，不由模型自动编造。

## 功能与流程

```text
提出需求
  → 创建／复用隔离 worktree，移动会话并继承工程规程
  → cloud-workflow 使用 GrillMe 澄清需求
  → 用户确认需求／设计
  → 使用 Superpowers 写计划
  → 独立 cloud-plan-review 审查计划并修正
  → 用户确认计划
  → local-worker 编写代码、测试并运行验证
  → 运行登记的检查、保存版本化证据
  → cloud-review 独立审计（中高风险另有结构／测试审查）
      ├─ quality_gate 通过 → 原 local-worker 归档 → 再核验 → 交付
      └─ 不通过 → 原 local-worker 修复、复验 → cloud-review 复审
```

- 同一阻塞连续三轮修复仍未解决时停止循环，报告问题，不无限重试。
- 需求或计划发生实质变化时重新确认；普通代码修复自动继续。
- 云端与本地不静默互相兜底。模型不可用时如实报告当前阶段。
- 计划确认通过 Plannotator 批注与批准；请求修改不触发实施，修订计划须重新审查和批准。批准后保持云端协调，再委派本地；不会自动切换为默认 build。
- 主对话在阶段开始、派发前后、结果返回及最终交付时显示**协调模型、执行模型和状态**。子任务卡片也显示目标角色及模型。
- 规格、计划、进度与测试证据保存到工程内，便于恢复；测试通过与独立审计通过分开记录。
- 自动压缩默认开启；示例按日常128K上下文配置，实际限制须与模型和服务能力一致。
- 本地模型**不另设工作流思考强度**，沿用私密 Provider／模型和服务的实际参数。云端可选择模型支持的推理档位。

### 角色分工

| 角色 | 用途 | 默认模型组 |
|---|---|---|
| `cloud-workflow` | 默认主入口，澄清、写计划、委派、汇总 | cloud |
| `cloud-design` | 独立需求与设计入口 | cloud |
| `cloud-plan` | 独立计划入口 | cloud |
| `cloud-review` | 独立审计与复审，只读、不运行 shell | cloud |
| `cloud-plan-review` | 开发前独立审查计划与验收 | cloud |
| `cloud-structure-review` | 中高风险结构／架构专项审查 | cloud |
| `cloud-test-review` | 中高风险测试有效性与证据审查 | cloud |
| `local-worker` | 唯一实施子代理，代码、测试、修复、归档 | local |
| `local-build` | 独立实施备用入口 | local |
| `local-inspect` | 只读事实调查 | local |

OpenCode 原生的 `build/general/explore` 及维护角色跟随 local 默认模型。推荐的 session 路由中，所有云端角色跟随主会话选择，本地角色仍可分别覆盖模型。

## 从零开始配置

以下命令以 macOS／Linux、Python 3.9+、Node.js 20+（运行测试）和 Git 为例。已实际验证 OpenCode Desktop **2.3.0 / V2配置格式**，不兼容 V1 的旧字段。Windows 的原生安装和目录权限行为尚未验证。

### 1. 安装 OpenCode

从 [OpenCode 官方下载页](https://opencode.ai/docs/#desktop)安装 Desktop，启动一次。也可以按[官方安装说明](https://opencode.ai/docs/)安装 CLI：

```sh
npm install -g @opencode/cli
opencode --version
```

Desktop 与 CLI 请使用兼容的 V2 版本；若不使用 CLI，后文的连接与模型选择可在 Desktop 完成。

### 2. 克隆本仓库

```sh
git clone https://github.com/zongxin1993/MyOpenCodeConfig.git
cd MyOpenCodeConfig
cp models.example.json models.local.json
```

`models.local.json` 是你的模型选择文件，已被 Git 忽略。不要提交真实 `opencode.json`、OAuth数据、API Key或服务密码。

### 3. 安装完整技能依赖

按 [技能安装说明](docs/SKILLS.md)安装固定版本的 Superpowers、GrillMe／grilling 和代码审计技能。该步骤保留完整目录和引用资源，不只复制 `SKILL.md`。

如果机器已经装有这些技能，先检查是否能用裸 ID 加载：`grill-me`、`grilling`、`writing-plans`、`executing-plans`、`test-driven-development`、`verification-before-completion`、`code-review-and-quality`。不要重复覆盖已有版本。

### 4. 创建本机私密基础配置

生成器合并到已有 JSON 配置，不负责写入凭据。全新机器可以从示例创建；已有配置的机器请手动合并 `providers.local` 与需要的压缩设置，保留其他内容。

```sh
python3 - <<'PY'
from pathlib import Path
import shutil
p = Path.home() / '.config/opencode/opencode.json'
p.parent.mkdir(parents=True, exist_ok=True)
if p.exists():
    raise SystemExit('已有配置，未覆盖；请手动合并 examples/opencode.base.example.json')
shutil.copyfile('examples/opencode.base.example.json', p)
p.chmod(0o600)
print('已创建本机基础配置，请编辑占位地址和模型ID')
PY
```

在 **`~/.config/opencode/opencode.json`** 中修改：

- `providers.local.settings.baseURL`：本地服务真实地址，示例 `127.0.0.1:8000/v1` 只是占位。
- `providers.local.models` 的键：服务实际返回的模型 ID，不能保留 `your-local-model`。
- `capabilities`、`limit`：按实际能力填写；示例为文本＋工具调用、128K上下文、106496输入上限和24576输出上限，不代表任何模型都支持。
- 本地服务需要的原有参数：放在这个私密 Provider 配置中；仓库不额外生成本地思考档位。

服务必须支持 OpenAI 兼容接口和可靠的工具调用；纯聊天可用不等于能够执行 Agent 任务。测试与 shell 在 OpenCode 打开的工程所在机器执行，不会因为推理服务在 NAS 就自动去 NAS 执行。

示例用 `LOCAL_LLM_API_KEY` 环境变量读取本地服务凭据。若服务不鉴权，可移除 `env`。若需要鉴权，请按[官方 Provider 配置说明](https://opencode.ai/docs/providers/)在本机设置凭据；也可在私密配置的 `settings.apiKey` 中填写自己的 Key，**不要写入仓库文件**。Desktop／后台服务不一定继承终端临时 `export`；使用环境变量时，要为实际运行的服务设置环境并重启确认。

### 5. 登录云端并确认可用模型

在 OpenCode 中执行 `/connect`，选择 OpenAI，再选择 **Sign in with ChatGPT**，按官方 OAuth 页面完成登录。使用其他云服务时连接对应 Provider。

随后用 `/models` 或 Desktop 模型选择器查看准确模型 ID 和可用推理档位。登录信息由 OpenCode 保存在本机，不能从本仓库恢复。详见[官方 Provider 文档](https://opencode.ai/docs/providers/#chatgpt)。

### 6. 编辑唯一的模型选择文件

编辑 `models.local.json`：

```json
{
  "version": 1,
  "routing": { "cloud_model": "session" },
  "defaults": {
    "cloud": {
      "provider": "openai",
      "model": "gpt-6.1-sol",
      "variant": "high"
    },
    "local": {
      "provider": "local",
      "model": "your-actual-local-model-id",
      "variant": null
    }
  },
  "roles": {}
}
```

`provider`、`model` 必须与 OpenCode／私密 Provider 配置匹配。示例云模型需在你的账号目录中实际可用，不可用就换成目录中的模型。云端档位按模型支持情况选择；本地 `variant` 保持 `null`，表示沿用已有配置，**不等于关闭原有思考**。

`routing.cloud_model: "session"` 下，Desktop 当前会话所选的模型及推理档位用于云端规划、审计、复审，包括再次委派同一审查子会话；`defaults.cloud` 仅提供启动默认值。切换云端模型不会改变本地模型及其思考、输出参数。进行中的请求继续完成，后续委派才采用新选择。启用此模式时不能同时设置固定的云端角色覆盖。

`roles` 可留 `{}`，也可覆盖本地角色。需要各云端角色固定不同模型时，改用 `routing.cloud_model: "fixed"`；旧映射未写 routing 时保持 fixed 行为。完整规则见 [模型映射与生成](docs/CONFIGURATION.md)。

### 7. 预览并应用

```sh
python3 configure.py --models models.local.json
python3 configure.py --models models.local.json --apply
```

第一次只预览，不写入；第二次先备份，再原子合并。输出只显示模型映射与备份位置，不打印 Provider 凭据。

生成器同步更新模型绑定、委派目标、权限资源引用、备用命令与显示标签。重复应用相同配置应显示 `changed: false`。原权限限制、Provider默认参数、上下文限制、压缩、MCP及无关角色／命令保留。

上述命令只管理主配置。启用 extensions 后，在开始任务前继续完成[完整安装](docs/QUALITY_WORKFLOW.md#从零安装扩展)：安装器还备份/合并 Plannotator 与 Quota 的关键偏好，并部署独立运行包。仅加插件列表不能替代这一步。现有 JSONC 插件偏好若含注释，本安装器会拒绝覆盖；先保留备份并将该文件转换为等价严格 JSON，再应用。

如果使用自定义位置，添加 `--target /path/to/opencode.json`。目前只读严格 JSON，不解析 JSONC 注释。

## 日常使用

1. 在 Desktop 打开你真正要开发的工程文件夹，新建对话，使用 `cloud-workflow`。
2. 确认主输入框选择的是你配置的云端模型与推理档位；已有会话的选择可能优先于配置。
3. 直接描述需求，例如：“帮我给现有配置加载器增加环境变量覆盖；先和我确认需求，再写计划。”
4. 用普通文字回答 GrillMe，确认需求／设计，再确认计划。
5. 之后等待实施、审计、必要修复复验及归档。不要手动转发审计意见或反复输入“下一步”。

你会在主对话看到类似提示：

```text
【实施与测试(TDD)｜已派发】
协调模型：openai/<cloud-model>#high
执行模型：local/<local-model>
```

主输入框仍显示云端，因为它负责协调；后台实际实施在 `local-worker` 子会话。阶段提示是模型按配置生成的工作流文字，不是系统级身份认证徽标。

原 `/clarify`、`/plan-task`、`/implement`、`/audit` 仍作为备用入口，正常自动流程不需要它们。涉及范围变化、危险操作或工程本身的授权要求，仍应遵循工程规则。

### 首次小任务验收

先在临时小工程提出一个标准库小任务，例如“实现 `clamp(value, lower, upper)` 并用 unittest 覆盖边界”，按两处确认走完。检查：

- 规划和审计显示 cloud 模型，写代码与测试显示 local 模型。
- 云端审计读取真实源文件与测试证据；审计发现阻塞时自动交回同一 worker 修复、复验、复审。
- 测试日志有真实命令、退出码、前后版本或哈希；整体通过后才最终交付。

不要在第一次迁移时直接用大型真实工程检验全部权限与工具兼容性。

## 更新、备份与回滚

```sh
git pull --ff-only
python3 configure.py --models models.local.json
python3 configure.py --models models.local.json --apply
```

`models.local.json` 不随 Git 更新覆盖。托管角色的 system/description/model 由模板重建；如需持久改工作流，修改 `templates.json`。实际 Provider 和凭据始终在本机私密配置里。

备份保存在目标配置目录的 `backups/role-model-config-<时间>/`。`.workflow-generated-state.json` 记录生成器管理的自定义档位所有权，不含凭据，回滚时应与 `opencode.json` 一起恢复；若原先没有状态文件，恢复配置后移除新生成的状态文件。备份可能包含凭据，不要上传。

旧对话不会被强制改写，旧子会话也可能保留旧角色和模型。更新工作流后优先新建对话，避免在活动任务中途迁移角色名。

## 目录与验证

```text
configure.py                       配置生成与备份
models.example.json                脱敏模型映射示例
models.local.json                   本机模型映射（自行创建，不入Git）
templates.json                     工作流角色和权限模板
examples/opencode.base.example.json 基础Provider与压缩示例
skills.lock.json                   技能上游及固定版本
docs/SKILLS.md                     技能安装
docs/CONFIGURATION.md              模型、权限、迁移规则
docs/VALIDATION.md                 已验证范围与限制
tests/                            生成器测试
```

运行测试：

```sh
python3 -m unittest discover -s tests -v
```

生成器仅依赖 Python 标准库。当前测试与实际工作流验证范围见 [验证说明](docs/VALIDATION.md)。

本仓库不包含第三方技能源文件；上游项目及许可见 [依赖说明](docs/SKILLS.md)。本仓库模板只定义协作方式，不保证任意模型、任意工具调用或任意 OpenCode 版本都兼容。

## 质量扩展：计划与审计门禁

详见[完整质量工作流安装与使用](docs/QUALITY_WORKFLOW.md)。先完成基础配置，再用 `setup_quality.py` 预览/备份安装、明确登记工程与验证策略。只读质量MCP不能执行shell，实际检查由本地worker运行；BMAD固定版资源由官方renderer预生成，运行时不启用项目hooks或另一套总协调。

必要需求映射、dirty/untracked快照、真实非空测试、最新运行与各轮原始审计共同决定PASS。旧成功不能覆盖后续失败；历史阻塞必须显式复验关闭。风险/修复价值/延期条件独立记录，严重问题不能被平均分抵消。

该扩展的源码与验证说明在[VALIDATION](docs/VALIDATION.md)，不包含个人Provider配置、API密钥、NAS地址或真实会话。远端业务仓库的强制合并门禁需单独配置，本地PASS不等于不可绕过安全隔离。


Worktree 原工程访问已自动适配：同一仓库主 checkout 可通过原生 `read` 只读核对，开发与测试留在 linked worktree。原工程写回被阻断，敏感读取和搜索另有限制；macOS shell 使用系统沙箱，保留原命令权限检查。共享 Git 元数据例外、跨目录硬链接和其他平台支持范围见 [插件集成说明](docs/PLUGIN_INTEGRATION.md#worktree-规则)。


## 本地执行效率

已加入统一的 execution 能力配置：RTK 输出后处理、ast-grep 只读结构搜索、local-execution 与精选 Rust 诊断技能。云端继承会话选择并规划/审计，固定本地模型实施/测试/修复。Serena/浏览器保存为关闭候选，未完成独立进程认证前不能启用。安装、配置、接管已有 RTK、证据与回滚见 [执行效率说明](docs/EXECUTION_EFFICIENCY.md)。
