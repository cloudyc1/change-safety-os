# Change Safety OS

Change Safety OS，简称 CSO，是一个面向 AI 辅助开发的变更安全系统。它的目标不是限制 Agent 修改代码，而是让 Agent 在修改代码前后明确回答三个问题：

- 这次到底要改哪个用户可感知的问题？
- 这个改动会影响哪些相邻链路、共享状态、持久化字段或外部集成？
- 目标问题修好了以后，是否已经检查过不会把其他功能改坏？

CSO 适合放进长期运行的 AI coding 工作流里，尤其适合多人、多 Agent、24 小时代码工厂、复杂业务系统、队列任务、支付计费、发布回调、数据监测、权限和导航状态等容易出现 side effect 的项目。

## 核心理念

CSO 不做“禁止修改某个文件”的硬限制。真实项目里，一个函数可能被多个链路调用，强行把作用域锁死在某个文件或函数上，容易导致两个问题：

- 该改的调用方没有被同步修改，功能表面修了但链路没闭环。
- 修改共享函数时没有检查其他调用方，导致实时查询、定时任务、报告生成、计费、前端展示等相邻流程出现 side effect。

CSO 的做法是把变更过程拆成一个安全闭环：

```text
明确目标 -> 建立变更记录 -> 查询影响图 -> 扫描改动 -> 检查契约 -> 追踪调用方 -> 运行验证 -> 记录缺口 -> 最终收口
```

最终交付前，CSO 会给出一个明确状态：

- `ready_to_deliver`：目标修复和 side effect 检查都可以交付。
- `needs_work`：还需要继续修复、验证或缩小改动。
- `needs_human_decision`：目标可能已完成，但存在未验证缺口，需要人类决策是否接受。

## 包含内容

本仓库包含以下模块：

- `cso`：安装后可用的 CLI 命令。
- `change_safety_os/`：CSO 的 Python 实现。
- `skills/change-safety/SKILL.md`：给 Codex 使用的通用 skill。
- `change_safety_os/assets/config/*.yaml`：初始化项目时复制到目标项目的默认配置。
- `change_safety_os/assets/templates/agents-snippet.md`：可合并进目标项目 `AGENTS.md` 的规则片段。
- `bin/*.py`：兼容直接 clone 仓库使用的入口脚本。
- `tests/`：CSO 自身的测试。

## 安装

PyPI 包名是 `secso`，安装后的命令是 `cso`。

```bash
python3 -m pip install secso
```

不要执行 `pip install cso`。`cso` 是命令名，不是本项目的 PyPI 包名。

如果 PyPI 版本暂时不可用，也可以直接从 GitHub 安装：

```bash
python3 -m pip install "git+https://github.com/cloudyc1/change-safety-os.git"
```

安装后检查命令是否可用：

```bash
cso --help
```

如果提示找不到 `cso`，通常是 Python 用户级脚本目录没有加入 `PATH`。可以查看路径：

```bash
python3 -m site --user-base
```

然后把输出目录下的 `bin` 加入 `PATH`。如果你使用 `pyenv`，安装后可以执行：

```bash
pyenv rehash
```

## 在项目中初始化

进入你的目标项目根目录后执行：

```bash
cd /path/to/your-project
cso init
```

初始化会做三件事：

- 在当前项目生成 `change-safety-os/config/`。
- 在当前项目生成 `change-safety-os/templates/`。
- 安装 Codex skill 到 `~/.codex/skills/change-safety/SKILL.md`。

初始化后，建议把下面这个文件中的内容合并到项目自己的 `AGENTS.md`：

```text
change-safety-os/templates/agents-snippet.md
```

这样 Codex 或其他 Agent 在处理高风险代码改动时，会知道应该触发 CSO。

## 最小使用流程

在目标项目根目录中运行：

```bash
cso start --goal "修复定时任务没有跑满的问题"
cso scan
cso contracts
cso trace
cso guards
cso probes --dry-run
cso ack --note "已检查调度、任务状态和前端展示契约"
cso finalize
```

这套流程适合手动分步执行。每一步的作用如下：

- `cso start`：创建本次变更记录，写明目标。
- `cso scan`：扫描当前 git 改动，判断影响域和风险。
- `cso contracts`：检查项目契约和受保护字段。
- `cso trace`：追踪被修改符号的调用方。
- `cso guards`：运行项目配置里的验证命令。
- `cso probes`：运行或列出项目配置里的探针。
- `cso ack`：记录你已经审阅过的契约或风险点。
- `cso finalize`：根据证据判断是否可以交付。

## 一条命令运行安全门

如果你希望 Agent 或脚本一次性跑完整安全门，可以使用：

```bash
cso run --goal "修复内容发布 HTML 表格上传格式问题"
```

如果你只想看会执行哪些检查，而不真正运行高成本探针：

```bash
cso run --goal "修复内容发布 HTML 表格上传格式问题" --dry-run
```

## 工作流图

CSO 支持维护一个轻量级工作流图。这个图不是权限边界，不会阻止你改代码。它的作用是帮助 Agent 更快知道：

- 某个文件属于哪个业务域。
- 这个业务域有哪些相邻链路。
- 修改某个文件后应该额外检查哪些地方。
- 哪些字段或协议是受保护的。

构建工作流图：

```bash
cso graph build
```

更新工作流图：

```bash
cso graph update
```

按文件查询影响：

```bash
cso graph query --file backend/services/orders.py
```

按业务域查询影响：

```bash
cso graph query --domain workflow_jobs
```

如果图不完整，不能把它当成唯一依据。正确做法是继续用 `rg`、测试和人工审查补全判断，然后更新 `change-safety-os/config/*.yaml`。

## 配置说明

初始化后，你需要根据项目实际情况修改这些配置：

```text
change-safety-os/config/domains.yaml
change-safety-os/config/contracts.yaml
change-safety-os/config/guard-matrix.yaml
change-safety-os/config/probe-registry.yaml
change-safety-os/config/risk-rules.yaml
```

### domains.yaml

定义项目里的业务域、文件匹配规则和相邻业务域。

适合放这些内容：

- 云手机调度链路。
- 实时查询链路。
- 定时监测链路。
- 洞察报告链路。
- 内容发布链路。
- 计费/token 链路。
- 前端结果展示链路。

### contracts.yaml

定义不能被随意破坏的业务契约。

例如：

- 已完成任务不能被重新改成进行中。
- 失败任务释放设备后必须允许补位。
- 计费冻结和结算必须成对出现。
- 发布订单回调不能丢文章正文。
- 前端历史记录必须展示真实状态。

### guard-matrix.yaml

定义不同风险域要跑哪些验证命令。

例如：

```yaml
guards:
  backend_guard:
    command: "cd backend && ./run_verification.sh"
  frontend_guard:
    command: "cd frontend && npm run build"
```

### probe-registry.yaml

定义更偏端到端的探针，例如：

- 创建一次实时查询任务。
- 跑一次定时监测 dry-run。
- 生成一次内容发布订单。
- 检查一个报告分享链接。

探针可以先用 `--dry-run` 只列出，不真实执行。

### risk-rules.yaml

定义高风险字段、状态和协议名。

例如：

```yaml
protected_fields:
  - batch_id
  - job_id
  - worker_id
  - run_key
  - status
  - answer_text
  - share_url
  - screenshot_path
  - billing_freeze_id
```

这些字段一旦被修改或广泛引用，CSO 会要求更严格的审查。

## 接入 Codex

CSO 安装后会提供一个 Codex skill：

```text
~/.codex/skills/change-safety/SKILL.md
```

但仅安装 skill 还不够。你还需要在目标项目的 `AGENTS.md` 里写清楚项目级规则，例如：

- 哪些链路是高风险链路。
- 哪些字段不能随意改语义。
- 哪些改动必须触发 CSO。
- 哪些验证命令必须执行。
- 哪些相邻流程必须被手动或自动检查。

可以从模板开始：

```bash
cat change-safety-os/templates/agents-snippet.md
```

然后把它合并进项目根目录的 `AGENTS.md`，再根据项目实际情况改写。

## 推荐给 Agent 的使用方式

你可以直接对 Codex 说：

```text
这次修改涉及队列、任务状态或共享字段，请使用 CSO：
1. 先 cso start 写明目标。
2. 修改前查询 graph 和相关调用方。
3. 修改后运行 scan/contracts/trace/guards/probes。
4. 如果 finalize 不是 ready_to_deliver，就继续修。
```

也可以让 Codex 帮你在一个新项目里安装：

```text
请在当前项目安装 CSO：
1. 安装 secso。
2. 运行 cso init。
3. 把 agents-snippet 合并进 AGENTS.md。
4. 按当前项目结构配置 domains/contracts/guards。
```

## 什么时候必须使用 CSO

建议在以下场景默认触发：

- 修改任务调度、队列、worker claim、重试、释放、终态判断。
- 修改共享字段，例如 `status`、`batch_id`、`job_id`、`worker_id`、`run_key`。
- 修改计费、token 冻结、结算、退款、套餐权限。
- 修改前端导航、继续流程、历史记录、结果展示。
- 修改发布接口、回调、文章正文、截图、分享链接。
- 修改数据库迁移或持久化字段。
- 修复一个疑似由前面改动造成的 side effect。
- 一个文件被多个用户可见流程共同使用。

以下场景通常可以跳过：

- 纯文档修改。
- 纯注释修改。
- 不影响运行行为的静态文案。
- 完全隔离的样式微调。

如果不确定，默认使用 CSO。

## CSO 不解决什么

CSO 不是自动测试的替代品，也不是代码审查的替代品。

它不会保证所有 side effect 都自动消失。它做的是把“应该检查什么、检查到哪里、还有什么缺口”显式化，避免 Agent 在修完目标问题后直接交付。

CSO 也不是静态权限系统。不要把 graph 当成“只能改这些文件”的限制。真实项目里，为了完整修复问题，经常需要跨文件、跨链路修改。CSO 要求的是：你可以改，但改完必须证明相邻链路没有被破坏。

## 维护者开发

如果你要开发 CSO 本身，可以 clone 本仓库后安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

运行测试：

```bash
python3 -m pytest tests -q
```

检查 Python 文件是否可编译：

```bash
python3 -m compileall change_safety_os bin
```

本地可编辑安装：

```bash
python3 -m pip install -e .
cso --help
```

构建发布产物：

```bash
python3 -m build
python3 -m twine check dist/*
```

## 发布到 PyPI

本项目的 PyPI 包名是 `secso`。GitHub release 发布后，会通过 Trusted Publisher 自动发布。

PyPI Trusted Publisher 配置应保持：

```text
Project name: secso
Repository: cloudyc1/change-safety-os
Workflow: publish.yml
Environment: pypi
```

发布新版本前，需要先修改 `pyproject.toml` 里的版本号，然后创建 GitHub Release。

例如：

```bash
git tag v0.1.1
git push origin v0.1.1
```

然后在 GitHub 页面创建 release，选择对应 tag 并发布。

## 许可证

MIT License
