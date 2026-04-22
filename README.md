# Requirements Agent

## 简介

`Requirements Agent` 用于把产品说明、原型、约束和反馈等上游输入，转化为结构化、可检查、可追踪、可交付的需求基线文档。

它在整体流程中的位置为：

`软件主题/产品方向确认 -> Requirements Agent -> 设计 Agent / 开发 Agent / 测试 Agent`

## 目标

- 将模糊的软件想法整理为标准化需求规格说明
- 输出后续 Agent 可直接消费的结构化工件
- 自动检查需求完整性、一致性、可测试性和来源完整性
- 对缺失信息和歧义生成待确认问题
- 维护需求追踪关系、变更记录和项目记忆

## 当前已实现能力

- 读取 `inputs/product_brief.md`、`inputs/prototype.md`
- 可选读取 `constraints.yaml`、`feedback.md`
- 统一模型配置与 Provider 抽象
- LLM 抽取与规则兜底双路径运行
- 功能需求、非功能需求、业务规则、边界场景、验收标准归一化编号
- 生成 `SRS.md`、`requirements.json`、`acceptance_criteria.yaml`
- 生成 `open_questions.md`、`review_report.md`
- 生成 `traceability.csv`、`change_log.md`
- 持久化 `memory/project_memory.json`

## 目录结构

```text
requirements_agent/
├─ app.py
├─ README.md
├─ config/
│  ├─ model_config.yaml
│  ├─ rule_config.yaml
│  └─ settings.yaml
├─ inputs/
├─ logs/
├─ memory/
├─ outputs/
├─ prompts/
│  ├─ extract_requirements.txt
│  ├─ generate_questions.txt
│  ├─ generate_srs.txt
│  ├─ refine_requirements.txt
│  └─ system_prompt.txt
├─ src/
│  ├─ config.py
│  ├─ differ.py
│  ├─ extractor.py
│  ├─ llm_client.py
│  ├─ memory.py
│  ├─ models.py
│  ├─ normalizer.py
│  ├─ orchestrator.py
│  ├─ parser.py
│  ├─ traceability.py
│  ├─ validator.py
│  ├─ writer.py
│  └─ providers/
└─ tests/
```

## 环境要求

- Python 3.13+
- 可选环境变量：`DASHSCOPE_API_KEY`

说明：

- 若已配置可用 API Key，则优先走 LLM 抽取链路。
- 若未配置或调用失败，则回退到规则化抽取逻辑，保证流程可运行。

## 配置

配置文件位于 `config/`：

- `settings.yaml`：目录、运行开关、输出行为
- `model_config.yaml`：模型提供方、Base URL、模型名、超参数、API Key 环境变量名
- `rule_config.yaml`：歧义词、严重级别、检查规则相关配置

当前默认模型配置：

- Provider Type: `compatible`
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Model Name: `qwen3.6-plus-2026-04-02`
- API Key Env: `DASHSCOPE_API_KEY`

## 运行方式

在仓库根目录执行：

```powershell
python requirements_agent/app.py --base-dir D:/Desktop/Chatgpt/agent
```

也可以按需覆盖输入输出目录：

```powershell
python requirements_agent/app.py --base-dir D:/Desktop/Chatgpt/agent --input-dir D:/path/to/inputs --output-dir D:/path/to/outputs
```

## 输入说明

输入目录默认是 `requirements_agent/inputs/`。

必需输入：

- `product_brief.md`
- `prototype.md`

可选输入：

- `constraints.yaml`
- `feedback.md`
- `history/`

若缺少必需输入，运行状态会直接返回 `BLOCKED`。

## 输出说明

输出目录默认是 `requirements_agent/outputs/`。

当前会生成：

- `SRS.md`
- `requirements.json`
- `acceptance_criteria.yaml`
- `open_questions.md`
- `review_report.md`
- `traceability.csv`
- `change_log.md`

Memory 文件：

- `memory/project_memory.json`

## 运行状态

每次运行会返回以下状态之一：

- `DRAFT_READY`
- `BASELINE_READY`
- `BLOCKED`
- `REVISION_REQUIRED`

## 当前限制

- `inputs/history/` 的历史版本增量比较尚未补齐
- 自动 refine 回路尚未实现
- 更细的可实现性检查、编号引用检查、追踪关系检查仍待补充
- 单元测试与回归测试尚未建立

## 相关文档

- 上层实现需求说明：[`../requirements.md`](../requirements.md)
- 当前实现进度：[`../agentwork.md`](../agentwork.md)
