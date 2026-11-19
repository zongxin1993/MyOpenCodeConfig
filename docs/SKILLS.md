# 技能依赖：从零安装

配置依赖以下上游技能；不把第三方技能源文件和个人技能目录上传到本仓库。

| 来源 | 使用内容 | 许可 |
|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | 设计、计划、按计划实施、TDD、验证、恢复及引用资源 | 上游 MIT |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `grill-me`、`grilling` | 上游 MIT |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | `code-review-and-quality` | 上游 MIT |

确切提交在根目录 `skills.lock.json`；升级时显式更新锁文件并重新验证工作流，不自动跟随上游分支。

## 本方案的安装方式

使用 OpenCode 原生文件技能发现机制，链接完整上游目录，不依赖额外协调插件。技能放到官方支持的兼容目录 `~/.agents/skills`，上游保存在 `~/.local/share/myopencodeconfig/upstream`。这样也避免把技能资源放进工作流禁止读取的私密 `~/.config/opencode` 配置目录。

这与 Superpowers 官方插件安装方式是两种依赖加载方法；本仓库选择原生文件方式。已经安装官方插件或同名技能的机器，先确认裸 ID 能正常加载，通常不应再重复安装。不要同时安装多份同名技能。

## 全新机器安装命令

在 MyOpenCodeConfig 仓库根目录运行下面代码。它只下载固定版本并建立技能链接，不调用模型，不运行上游安装脚本，也不会覆盖不同目标的已有链接。

```sh
python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

root = Path(os.environ.get('MYOPENCODE_SETUP_ROOT', str(Path.home()))).expanduser()
cache = root / '.local/share/myopencodeconfig/upstream'
skills = root / '.agents/skills'
lock = json.loads(Path('skills.lock.json').read_text())
cache.mkdir(parents=True, exist_ok=True)
skills.mkdir(parents=True, exist_ok=True)
for name, item in lock.items():
    source = cache / name
    if not source.exists():
        subprocess.run(['git', 'clone', '--no-checkout', '--depth', '1', item['repository'], str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'fetch', '--depth', '1', 'origin', item['commit']], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', item['commit']], check=True)
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != item['commit']:
        raise SystemExit(f'{source} 不是锁定版本；已停止，请先核对已有目录')

links = {
    'superpowers': cache / 'superpowers/skills',
    'grill-me': cache / 'mattpocock/skills/productivity/grill-me',
    'grilling': cache / 'mattpocock/skills/productivity/grilling',
    'code-review-and-quality': cache / 'addy/skills/code-review-and-quality',
}
# Preflight every destination before changing links.
for name, source in links.items():
    if not source.is_dir():
        raise SystemExit(f'缺少上游技能目录：{source}')
    target = skills / name
    if target.exists() or target.is_symlink():
        if not target.is_symlink() or target.resolve() != source.resolve():
            raise SystemExit(f'已有其他技能：{target}；未覆盖')
for name, source in links.items():
    target = skills / name
    if not target.is_symlink():
        target.symlink_to(source, target_is_directory=True)
print('固定版本技能已就绪；请在 OpenCode 中核对加载结果')
PY
```

`MYOPENCODE_SETUP_ROOT` 只用于在独立目录演练；正常安装无需设置。上游目录应保留，技能链接依赖它们。

如果网络下载中断，源目录可能尚未完成 checkout；核对目录后修复下载，不要直接忽略版本检查。若同名技能来自已有插件或别的管理器，保留原管理方式并跳过这段全新安装流程。

## 在 OpenCode 中验收

重启 Desktop／后台服务，或让其重新加载技能。在新对话中要求它通过原生 `skill` 工具加载并报告以下裸 ID：

```text
grill-me
grilling
brainstorming
writing-plans
executing-plans
test-driven-development
verification-before-completion
code-review-and-quality
```

不要以“目录存在”作为完整兼容证明。随后按 README 的小任务验证实际访谈、计划、代码／测试、审计，以及审计意见自动返回本地修复。

原始技能可能写有 `superpowers:writing-plans` 之类的引用。角色模板已要求在 OpenCode 中转换为 `writing-plans` 等裸 ID，并使用当前宿主提供的 `shell/subagent/read/edit/patch` 工具。技能脚本和引用文件保留相对路径；不要只复制 SKILL.md。

参考：[OpenCode 技能发现规则](https://opencode.ai/docs/skills/)、[Superpowers 官方 OpenCode 安装说明](https://github.com/obra/superpowers/blob/main/.opencode/INSTALL.md)。技能原文和许可始终以上游仓库为准。

## 质量扩展技能与BMAD

quality-planning / quality-review 来自本仓库，由 setup_quality.py 安装并保留完整运行目录。BMAD审计上游来源、精确提交、渲染依赖见 integrations/bmad/lock.json；不会把原始BMAD技能全局自动激活。完整步骤见 QUALITY_WORKFLOW.md。不要混用稳定v6.12安装器与本扩展固定的v7预览资源。


本地执行能力的统一配置、受管技能、RTK 接管及可选进程限制见 [EXECUTION_EFFICIENCY.md](EXECUTION_EFFICIENCY.md)。
