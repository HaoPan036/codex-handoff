# Codex Handoff

[![CI](https://github.com/HaoPan036/codex-handoff/actions/workflows/ci.yml/badge.svg)](https://github.com/HaoPan036/codex-handoff/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Platform: macOS | Linux](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-555.svg)](#兼容性与限制)

**让长时间运行的 Codex Session 在 context compaction 后继续相信可验证的仓库事实。**

多次 context compaction 之后，Codex 会越来越难判断仓库当前究竟是什么状态。Codex Handoff 会等当前 Turn 到达安全边界，再从仓库证据重建继续工作所需的信息，把结果写入 `docs/CODEX_HANDOFF.md`，供干净的新 Session 核对和接手。

[English README](README.md)

![概念流程图，展示多次 context compaction 如何经过安全 Stop 边界和仓库证据，生成 CODEX_HANDOFF.md 并进入干净的新 Session](docs/assets/codex-handoff-flow.svg)

<p align="center"><sub>概念流程图。CLI 安装和两轮完整的 host-driven 交接已在 macOS 验证；经过审查的 terminal 录制仍待完成。</sub></p>

| 安全时机 | 可验证状态 | 干净延续 |
| --- | --- | --- |
| 等当前 Turn 自然到达 `Stop`，不会中途打断任务。 | 根据 Git、仓库文件、测试、产物和 `AGENTS.md` 重建状态。 | 生成结构固定且经过校验的 `docs/CODEX_HANDOFF.md`，交给新 Session。 |

## 快速开始

用户级安装脚本仍是最短的安装路径。Plugin 包已经通过隔离的 CLI 安装检查，以及真实 Codex host 测试。后者覆盖 Hook trust、两个阈值周期、Skill 执行、经过校验的 handoff 更新、防循环和干净 Session 续接。

```bash
git clone https://github.com/HaoPan036/codex-handoff.git
cd codex-handoff
bash install.sh 3
```

安装后重启 Codex，检查并信任新安装的 Hook。最后一个数字表示累计完成多少次 compaction 后安排交接。

任何里程碑都可以手动交接，无需等待阈值。

```text
$codex-handoff
```

结果写入 `docs/CODEX_HANDOFF.md`。如果只想生成并校验文件，不打开新 Session，可以使用 `$codex-handoff handoff only`。

## 为什么需要 Codex Handoff

一次 context compaction 通常不会阻止任务继续。次数增加以后，继续工作的 Session 很难有把握地回答这些问题。

- 哪些工作已经完成？
- 当前有哪些 staged、unstaged 和 untracked 变更？
- 哪些设计决策和项目规则仍然有效？
- 哪些测试确实运行并通过？
- 接下来唯一要做的任务是什么？

普通聊天摘要只能复述对话里出现过的内容。Codex Handoff 会根据新 Session 能够再次检查的证据，生成一个长期保存在仓库里的交接文件。重要事实缺少证据时，文件会把它标记为 `UNKNOWN`。

## 工作原理

自动流程把计数和行动分开。`PostCompact` 只记录一次已经完成的 compaction，不改变模型行为。达到阈值以后，Hook 只把状态记为待交接。当前任务、tool call、测试和 subagent 都会继续，直到 Turn 自然到达 `Stop`。

到了这个边界，Hook 才安排一次 continuation，显式调用 `$codex-handoff`。Skill 随后检查仓库、写入并校验交接文件，再尽力打开一个干净的新 Codex Session。

### 技术流程

```mermaid
flowchart LR
    A[PostCompact 完成] --> B[增加当前 Session 计数]
    B --> C{达到阈值?}
    C -- 否 --> D[继续当前任务]
    C -- 是 --> E[记录待交接状态]
    E --> D
    D --> F[当前 Turn 自然到达 Stop]
    F --> G[显式调用 $codex-handoff]
    G --> H[收集 Git 和仓库证据]
    H --> I[创建或更新 docs/CODEX_HANDOFF.md]
    I --> J[校验结构和有限历史]
    J --> K[准备新 Session 启动提示词]
```

[docs/design.md](docs/design.md) 详细记录了状态机、信任边界和证据优先级。

## 自动交接

默认阈值为 3，流程如下。

1. 当前 Session 完成 3 次 `PostCompact`。
2. 当前任务继续执行，不会被中途打断。
3. Turn 自然到达下一次 `Stop` 时，Hook 安排一次显式调用 `$codex-handoff` 的 continuation。
4. Skill 创建或更新 `docs/CODEX_HANDOFF.md`，完成校验，并准备干净的新 Session。

每次发出交接请求以后，当前交接周期的计数会归零。后续再累计到阈值时仍能触发。`stop_hook_active` 会阻止 continuation 再次安排自身。

## 手动交接

任何里程碑都可以直接调用 Skill。

```text
$codex-handoff
```

只生成并校验交接文件，不打开新 Session。

```text
$codex-handoff handoff only
```

手动调用与自动流程遵守同一套证据和安全规则。

## `CODEX_HANDOFF.md` 包含什么

交接文件使用固定的 11 节结构。

1. 当前目标和范围
2. 已验证的当前状态
3. 架构和数据流
4. 决策、约束和被放弃的方案
5. 相关文件和符号
6. 验证命令与结果
7. 当前工作区状态
8. 已知问题、风险和未知项
9. 一个具体的下一步任务
10. 新 Session 启动检查清单
11. 最近 5 次交接历史

第 1 至 10 节每次都根据当前证据重写。第 11 节只保留最近 5 次交接记录。Validator 会拒绝缺少章节、遗留模板占位符、模糊的下一步任务、过大的文档，以及超过 5 条的历史记录。

[examples/CODEX_HANDOFF.example.md](examples/CODEX_HANDOFF.example.md) 提供了一份完整示例。

## 安全模型

准备交接时，Skill 会遵守以下规则。

- 只更新 `docs/CODEX_HANDOFF.md`
- 保留 staged、unstaged 和 untracked 工作
- 未收到明确要求时，不执行 commit、push、reset、clean、discard、stash、archive 和 delete
- 无法验证的重要结论标记为 `UNKNOWN`
- 不写入凭证、密钥、大段完整日志和完整 diff

Hook 不会读取仓库文件或 transcript。它只接收生命周期事件元数据，更新本地计数和有大小限制的审计日志，并在配置好的边界输出 continuation decision。Hook 不访问网络，也不修改仓库。Codex Handoff 不收集 telemetry。

[SECURITY.md](SECURITY.md) 记录了安全边界和漏洞报告方式。

## 安装细节

### 用户级安装脚本

安装脚本要求 Python 3.11 或更高版本，会把 Skill 和 Hook 直接安装到用户目录。

```bash
git clone https://github.com/HaoPan036/codex-handoff.git
cd codex-handoff
bash install.sh 3
```

脚本会完成这些操作。

- 把 Skill 安装到 `~/.agents/skills/codex-handoff/`
- 把 Hook 安装到 `~/.codex/hooks/codex_handoff_hook.py`
- 备份并更新 `~/.codex/config.toml`
- 删除旧版 `codex-handoff-session` 写入的 Hook 配置
- 尽可能迁移兼容的 v3 compact 计数

安装后需要重启 Codex，并检查 Hook 的完整定义。

### Codex Plugin Marketplace

仓库已经包含 Plugin 包和 Marketplace metadata。2026 年 8 月 11 日，Codex CLI `0.147.0-alpha.6.5` 分别从本地 checkout 和公开的 `HaoPan036/codex-handoff` shorthand 成功发现并安装了 `0.1.0`，两次测试均使用隔离的 `CODEX_HOME`。公开缓存中的 manifest、Hook、Skill 和 helper hash 与当前仓库一致。随后，一个由模型驱动的 Codex CLI Session 在一次性仓库中信任 bundled Hook 并完成了两个由 host 发出的阈值周期：6 次真实 `PostCompact` 产生 2 次安全 handoff continuation，每次请求后计数都归零，两次 handoff 文件都通过校验，而且 continuation 均正常结束、没有形成循环。第二轮的 `codex://new` 还打开了一个干净 Session，由它独立核对 handoff 和仓库状态。

[smoke-test 记录](docs/smoke-test-2026-08-11.md) 给出了环境、精确状态变化、第一轮观察到的启动回退，以及仍未完成的发布边界。

```bash
codex plugin marketplace add HaoPan036/codex-handoff
```

从用户级安装的 `codex-handoff-session` v4 迁移时，不要同时启用两套 Hook。先在当前 checkout 中运行 `bash uninstall.sh`，删除旧版 profile Skill 和 Hook。本地状态默认保留。随后再安装并信任 Plugin Hook。

随后在 Codex CLI 中打开 `/plugins`，或者在 ChatGPT 桌面端打开 Plugins Directory，安装 `Codex Handoff` 并新建 Session。通过 `/hooks` 查看 bundled Hook，确认完整定义后再授予信任。仓库中的 Marketplace 文件位于 `.agents/plugins/marketplace.json`，Plugin 包位于 `plugins/codex-handoff/`。

命令格式和 Hook trust 流程参考 OpenAI 官方的 [Codex Plugin 打包文档](https://developers.openai.com/plugins/build/plugins) 与 [Codex Hooks 文档](https://developers.openai.com/codex/hooks)。

### 卸载

删除用户级安装，保留本地计数和日志。

```bash
bash uninstall.sh
```

同时删除本地状态。

```bash
bash uninstall.sh --purge-state
```

Plugin 安装可以通过 `/plugins` 或 Plugins Directory 禁用或移除。

## 配置

### 用户级安装

重新执行安装脚本即可修改阈值。

```bash
bash install.sh 5
```

### Plugin 安装

创建 `~/.codex/codex-handoff.json`。

```json
{
  "compact_threshold": 3
}
```

环境变量 `CODEX_HANDOFF_COMPACT_THRESHOLD` 的优先级更高。Plugin 模式把状态保存在 Codex 提供的 `PLUGIN_DATA` 目录。

用户级安装把状态保存在以下路径。

```text
~/.codex/codex-handoff/state.json
~/.codex/codex-handoff/events.jsonl
```

审计日志达到约 1 MB 后轮转。超过 30 天的 Session 记录会在 Hook 运行时清理。

## 兼容性与限制

- 当前版本为 `v0.1.0`。
- 仓库 CI 在 macOS 和 Linux 上使用 Python 3.11、3.12 和 3.13 运行自动化测试。
- 用户级安装脚本要求 Python 3.11 或更高版本。运行时辅助脚本只使用 Python 标准库。
- 当前打包的 Hook 命令面向 macOS 和 Linux shell。
- Codex Plugin 可用于 Codex CLI 和 ChatGPT 桌面端，IDE Extension 暂不支持。IDE Extension 可以使用用户级安装脚本。
- 本地和公开 GitHub Marketplace 的发现与安装已通过隔离冒烟测试。交互式 Hook trust、host 发出的事件、两个重复阈值周期、由 Skill 编写 handoff、校验、防循环和干净 Session 续接也已通过由模型驱动的 macOS host 测试。相关材料见 [测试记录](docs/smoke-test-2026-08-11.md)、[Demo 指南](docs/demo.md) 和 [release checklist](docs/release-checklist.md)。
- `codex://new` 打开新 Session 的能力采用尽力而为策略。操作系统无法打开时，辅助脚本会输出完整的手动启动提示词。
- 自动打开失败不会影响已经校验完成的 handoff 文件。

## 开发与验证

运行完整的本地验证。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_package.py
```

测试覆盖阈值计数、合法的 `Stop` JSON、安全边界、周期触发、状态保留、snapshot、handoff validator、新 Session 回退、旧版安装升级和 Plugin metadata。

修改生命周期协议前，请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [docs/design.md](docs/design.md)。常见安装与运行问题见 [docs/troubleshooting.md](docs/troubleshooting.md)。

## 项目结构

```text
.agents/plugins/marketplace.json
.github/workflows/ci.yml
plugins/codex-handoff/
  .codex-plugin/plugin.json
  hooks/
    hooks.json
    codex_handoff_hook.py
  skills/codex-handoff/
    SKILL.md
    agents/openai.yaml
    assets/CODEX_HANDOFF.template.md
    scripts/
docs/
  assets/codex-handoff-flow.svg
  demo.md
  smoke-test-2026-08-11.md
scripts/
  install_profile.py
  uninstall_profile.py
  validate_package.py
tests/
```

## Roadmap

- 用经过审查、可重复录制的 15 至 25 秒 terminal demo 替换概念流程图。
- 发布 `v0.1.0` 前，完成剩余的交互式安装和卸载隔离 checklist。
- 加入 Windows Hook command packaging。
- 收集外部使用反馈，再考虑扩展 handoff schema。

## License

项目采用 MIT License，详见 [LICENSE](LICENSE)。
