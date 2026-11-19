# 本地执行工具与技能

目标是缩短任务开始至独立审计通过的时间，同时保留原生工程验收。云端仍继承主会话所选模型；本地 worker 仍使用固定本地绑定，不增加推理档位。工具缩减输出不等于任务同比提速。

## 本次可用范围

| 能力 | 状态 | 使用方式 |
|---|---|---|
| RTK safe-output | 已集成 | 命令执行后才过滤符合条件的搜索/简短日志展示；不改写原命令或权限判断 |
| ast-grep | 已集成 | 通过 execution_ast_search 查询当前 linked worktree 内 1..64 个显式源码文件 |
| local-execution | 已集成 | 已批准实施任务加载；复用现有 TDD/调试，保留原日志，同一 worker 修复 |
| rust-diagnostics | 已集成 | 实际 ownership/error/concurrency 问题按需加载，通用建议不覆盖领域契约 |
| Serena | 配置候选，未放行 | 当前缺少已认证语言服务器/独立进程授权与生命周期验证，保持 off |
| Playwright CLI | 固定依赖/官方技能资源已准备，未放行 | 独立空白 Chrome 启动已通过；浏览器 daemon 的权限与清理尚未认证，保持 off |

Serena/browser 非 off 在安装前明确失败，不会给用户一个“已启用”但不受控的进程。它们不是本次已完成的安全/性能能力。cargo-nextest/sccache 不在本批安装范围，不能替换项目已批准检查。

## 从零设置

先按 README 配置 OpenCode V2、Provider/OAuth、技能和固定 BMAD renderer。工具运行依赖 Node/npm；首批认证 macOS。准备 RTK 1.2.0（上游固定来源见 integrations/execution.lock.json），不要用另一个同名程序。然后从仓库运行：

```sh
python3 setup_execution_tools.py
```

该命令根据仓库的 npm 完整 dependency lock 准备 ast-grep 0.51.3，不改业务工程依赖或全局 npm。`--browser` 可额外准备 Playwright CLI 0.1.25，但不启用 browser 能力、不安装/认证浏览器 revision。npm 生命周期脚本禁用；ast-grep 使用平台原生二进制绝对路径，避免 JS 启动器每次解析 binary 的开销。

工具安装使用同级 staging：npm 失败保留活动版本；完整后切换或逐字校验接管。已有 receipt 的版本校验后复用，不重复 npm ci 清空 node_modules；被外部修改则拒绝替换。依赖缺失在部署预检时处理，模型执行任务时不安装、不更新。

把以下块加入自己的私有模型映射（不是原生 opencode.json）：

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

然后按 QUALITY_WORKFLOW.md 使用 setup_quality.py 预览并 `--apply`。安装器检查版本、插件重复入口和已管理技能是否被修改，备份后把本机可执行文件绝对路径写入私有运行时选项。不能只运行 configure.py 就假定 CLI、技能和固定运行时已安装。部署后先用一个小任务验证实际工具可用；不需要为每个新需求手工选择工具。启用worker_skill会将旧的重型executing-plans入口替换为local-execution短入口，继续保留TDD和完成验证，不额外叠加一套实施初始化。

不存在 execution 或设置为空时，生成器保留原来的行为。每个能力独立关闭；关闭只移除自己的注册和未被修改的技能文件，保留用户追加的其他文件，不删除工具包、用户会话或工程源码。工具版本更新要更新锁和依赖完整性，重新验收；没有运行期 latest 下载。

## RTK 接管和输出证据

本机原有 `plugins/rtk.ts` 是自动发现项，不是 plugins 数组项。安装时同时检查用户、工程、linked worktree 和自定义配置目录；已核对的原 hook 摘要一致才能在同一事务中移除并接入唯一受管过滤器。未知或多个入口停止，不静默覆盖。运行期当前工程再出现另一个 RTK hook 会阻止新请求，要求先消除重复；不是双重压缩后继续运行。

过滤器当前仅处理安全形态的 rg 和 git log --oneline 展示，不触碰源码读取、审计 diff、测试、构建、固定验证入口、管道或重定向。已被宿主截断、太短、无可识别格式、过滤无收益或工具失败的结果保持原样；不会重新执行命令。原始未过滤文本以私有 0600 日志保存，展示里给路径；退出码及 native output/metadata 保留。完整验收日志仍由原生测试/证据机制保存，不以 RTK 指针或摘要替代。

RTK 数据只说明命令输出估算缩减，不是整个请求 token、费用或任务时间。日志可能包含源码，不能随配置上传。可按自己的留存要求清理私有 execution-logs，清理前确认不再被审计证据引用。

## 搜索边界

普通名称、路径和字符串用原有 rg/read。语法结构问题才加载 ast-grep adapter，用显式文件避免无效项目全扫。原工程核对仍走原生 read，不借新工具开放其他目录。

Desktop的shell PATH可能缺少rg。部署预检会在存在时记录现有rg绝对路径，并向本地角色提供实际路径提示；不改全局PATH，RTK只额外接受这个精确路径。没有可用rg时继续用原生grep/read，不让模型反复尝试command-not-found。

适配器检查实际角色/session/worktree、敏感文件和 canonical 路径，逐文件请求宿主原生 read 权限；同时覆盖相对/绝对规则。权限等待前固定文件描述符，等待后校验身份/会话，拒绝 symlink 替换和多个硬链接的源码文件；将批准文本从 stdin 交给固定 CLI，不让 CLI 在工程内遍历或装载项目配置。最多返回100处带行号命中，标明截断；缺失或零匹配不能证明符号不存在。

源码通用只读保护仍受 PLUGIN_INTEGRATION.md 中的平台、共享 Git 元数据与硬链接支持范围限制；不把它宣称成整个宿主的访问锁。

## 技能来源

ast-grep/agent-skill 与 actionbook/rust-skills 的 inspected commit 中未发现明确根许可文件，因此本仓库不分发它们的完整正文。使用本项目原创精简适配和 Rust 官方手册参考，保留上游 commit、源文件摘要和链接。微软官方浏览器 skill/support files 作为关闭候选资料保存，附原 Apache 许可。固定技能资源不等于角色已加载或工具已认证。

## 安装、恢复与并发修改

安装前逐目标记录原/目标字节摘要及备份，配置、受管状态、偏好、技能和旧 RTK hook 归属在同一文件事务中更新。已管理文件被用户修改时停止覆盖；应用/异常恢复中发现的新修改也保留。单项 symlink/目录/损坏备份冲突不会妨碍其他无冲突目标恢复。

需人工恢复时，在配置工程目录或相应不可变运行时中运行：

```sh
python3 -m workflow.execution_setup --rollback <本次备份目录>
```

它仅恢复仍等于本次已写版本的目标；并发修改和损坏备份列为 conflicts，退出非零，不能把这称为完整恢复。进程中断后同样可使用事务日志恢复。备份含私有配置，只留本机，不能上传。应用以后新的配置版本会使旧事务产生冲突，禁止强行恢复整份旧配置覆盖新工作。

## 验证与速度结论

真实 OpenCode low 云主会话与独立 cloud-review 使用同一个选中模型/档位，Strata worker 实际执行代码与测试。原生 AST 正常命中、绝对 read deny、原目录越界、.env 拒绝均有真实工具回执。首次 native 调用暴露 source.messageID 字段要求，修复后同一会话重试通过，未掩盖初次失败。RTK首次shell探针也如实记录了Desktop找不到rg的exit127；使用预检绝对路径后在独立worktree重试成功，保留120处原始命中日志和exit0。

可重复 CLI 小实验：

```sh
python3 examples/execution-pilot/benchmark_tools.py --rtk <固定rtk路径> --ast <固定ast-grep路径>
```

本机三轮交错的合成重复搜索样本：RTK显示从38439字符降到359字符，过滤中位开销约6.57ms；简单已知函数的 AST 查询约6.28ms，rg约4.36ms。结果仅属于该合成CLI样本；不证明一般压缩率，更不证明任务总耗时提速。简单文本继续rg，AST用于结构精度。

当前仍有其他本地任务活动，不能把真实小任务的墙钟时间当排除其他客户端干扰的 A/B。没有取得可靠端到端提速比例；不发布虚构百分比。Serena/browser保持关闭，待其独立隔离和实际任务对照完成后再决定开启。ACP/原生压缩策略本次保持，不将改变压缩策略的收益归给这些工具。

真实小任务由Strata执行27项unittest，云端low独立审计提出证据manifest绑定缺口，同一worker新增补证、不改代码或伪造历史运行，再由原cloud low复审关闭。测试驱动器曾把RTK探针文件放进同一实施worktree，触发额外核对；已说明来源并改用独立探针worktree。这种驱动干扰不计为优化收益。
