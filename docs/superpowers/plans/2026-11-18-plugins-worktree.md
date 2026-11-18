# Plugins and isolated implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans for inline implementation, TDD, then independent review.

**Goal:** 接入三项插件、隔离所有新需求实施并完整验证云low/本地分工后发布。
**Architecture:** 固定第三方包；生成器保有条目所有权；独立worktree策略插件采用原生SDK创建/移动，真实Git元数据校验；注册逻辑按同一Git来源继承策略。
**Tech Stack:** Python3.9+、Node/Bun、OpenCode V2 Promise SDK、Git。
**Spec:** ../specs/2026-11-18-plugins-worktree-design.md

## Global Constraints
- 先备份；保留Provider、日常模型、压缩、已有项目与自定义权限；只测试会话使用low。
- 实施测试在linked worktree；主工程不改、不stash/reset/自动合并。
- 不加Mem/DCP；不把UI批准或idle当验收。

## Review Focus
- 未托管插件/权限保持，冲突拒绝；固定版本不静默替换。
- 主目录、子模块和伪.git文件不能通过linked-worktree校验。
- 移动前后实际会话目录与云model/variant保持；不能续跑仍位于原目录的旧worker。
- worktree注册不能从portable降级native，原生私密指导不泄漏。
- 拒绝/批注反馈不能启动实施，修订计划需再次批准。

### Task1: 可移植集成与权限
- [x] tests/test_integrations.py先写插件配置/权限/幂等冲突回归，观察RED。
- [x] configure.py与integrations/plugins.lock.json实现固定包和user-managed；templates.json增加精确权限与阶段规则。
- [x] 全套测试GREEN。

### Task2: worktree工具及策略继承
- [x] tests/test_worktree_policy.mjs真实Git仓库测试主目录拒绝/linked允许/旧child拒绝/复用无重复创建；tests/test_onboarding.py增加继承反例，RED。
- [x] plugins/worktree-policy独立工具+hooks；workflow/registration.py继承已有Git主目录策略；生成器/安装器管理immutable路径。
- [x] 全套GREEN，记录局限。

### Task3: 本机安装和端到端
- [x] 配置、状态、skills、相关插件设置先私密备份；安装固定发行包并核对真实入口。
- [x] 插件active、真实Context7查询、Quota真值与DesktopGUI、Plannotator反馈/拒绝/批准。
- [x] 临时Git工程云low规划/独立计划审查，创建worktree并移动，Strata实施/测试，云low审计；预设问题触发修复复验，复审完成。
- [x] 保存原目录不变、实际model/variant、child位置与真实执行证据；重复安装无变更。

### Task4: 复核和发布
- [x] 独立review；修复可重现缺陷并跑回归。
- [x] 中文README/验证说明/固定版本记录；隐私扫描；fetch对齐后push master并核对CI。

## Verification and review record

- 67 Python tests passed; included 12 actual Node tests. Native LOW fixture completed documented approval/repair/BMAD flow; private original records retained outside this checkout.
- Final: fixed nested-project policy loss — real nested worktree location test RED→GREEN, suite67/67.
- Final: fixed copied .git false isolation — real reciprocal backlink test RED→GREEN, suite67/67.
- Final: fixed --option=/source policy bypass — test_equal_option_source_path_is_rejected_before_policy_inheritance RED→GREEN, suite67/67.
- Integration failures corrected: exact hyphenated Context7 permission names, disabled Plannotator agent switching, approved-plan read scope, explicit BMAD completion and original receipt handoff. No review findings deferred.
