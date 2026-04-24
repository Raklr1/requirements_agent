# Requirements Agent

## 简介

`Requirements Agent` 是当前仓库中已经实现的需求分析 Agent。它读取产品说明和原型说明，结合可选约束与反馈，生成结构化需求基线和质量检查工件。

当前实现目标是让需求分析流程可运行、可检查、可追踪。

## 当前已实现能力

- 读取 `inputs/product_brief.md`。
- 读取 `inputs/prototype.md`。
- 可选读取 `inputs/constraints.yaml`。
- 可选读取 `inputs/feedback.md`。
- 解析 Markdown 章节并建立来源映射。
- 生成 `ProjectContext`。
- 通过配置文件加载运行目录、模型参数和检查规则。
- 通过 `LLMClient` 屏蔽模型 Provider 细节。
- 支持 `compatible` 与 `openai` 两类 Provider 配置。
- 支持 LLM 抽取需求草稿。
- 支持规则化兜底抽取，保证无 API Key 或模型不可用时主流程仍可运行。
- 生成功能需求、非功能需求、业务规则、边界场景、验收标准和待确认问题。
- 归一化需求字段和编号。
- 复用上一版 baseline 的稳定 ID。
- 进行完整性、一致性、歧义、可测试性、来源完整性检查。
- 生成追踪矩阵、变更日志和项目记忆。

## 目录结构

```text
requirements_agent/
├─ app.py
├─ README.md
├─ config/
│  ├─ settings.yaml
│  ├─ model_config.yaml
│  └─ rule_config.yaml
├─ inputs/
│  ├─ product_brief.md
│  └─ prototype.md
├─ memory/
│  └─ project_memory.json
├─ outputs/
│  ├─ SRS.md
│  ├─ requirements.json
│  ├─ acceptance_criteria.yaml
│  ├─ open_questions.md
│  ├─ review_report.md
│  ├─ traceability.csv
│  └─ change_log.md
├─ prompts/
│  ├─ extract_requirements.txt
│  └─ system_prompt.txt
└─ src/
   ├─ config.py
   ├─ differ.py
   ├─ extractor.py
   ├─ llm_client.py
   ├─ memory.py
   ├─ models.py
   ├─ normalizer.py
   ├─ orchestrator.py
   ├─ parser.py
   ├─ traceability.py
   ├─ validator.py
   ├─ writer.py
   └─ providers/
```

## 环境要求

- Python 3.13+
- 可选环境变量：`DASHSCOPE_API_KEY`

说明：

- 配置了可用 API Key 时，优先走 LLM 抽取链路。
- 未配置 API Key 或模型调用失败时，会走规则化兜底抽取链路。

## 运行方式

在仓库根目录执行：

```powershell
python requirements_agent/app.py --base-dir D:/Desktop/Chatgpt/agent
```

按需覆盖输入输出目录：

```powershell
python requirements_agent/app.py --base-dir D:/Desktop/Chatgpt/agent --input-dir D:/path/to/inputs --output-dir D:/path/to/outputs
```

运行结束后，命令行会打印本次状态，例如：

```text
BASELINE_READY
```

## 输入

默认输入目录：

```text
requirements_agent/inputs/
```

必需输入：

- `product_brief.md`
- `prototype.md`

可选输入：

- `constraints.yaml`
- `feedback.md`

若缺少必需输入，运行状态为 `BLOCKED`。

## 输出

默认输出目录：

```text
requirements_agent/outputs/
```

当前生成：

- `SRS.md`
- `requirements.json`
- `acceptance_criteria.yaml`
- `open_questions.md`
- `review_report.md`
- `traceability.csv`
- `change_log.md`

项目记忆：

- `memory/project_memory.json`

## 配置

配置文件位于 `config/`。

- `settings.yaml`：运行目录、兜底开关、草稿版本。
- `model_config.yaml`：Provider、模型名、Base URL、API Key 环境变量、超参数。
- `rule_config.yaml`：歧义词、问题类别、严重级别。

当前默认模型配置：

- Provider Type: `compatible`
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Model Name: `qwen3.6-plus-2026-04-02`
- API Key Env: `DASHSCOPE_API_KEY`

## 主流程

```text
app.py
-> load_app_config()
-> run_requirements_agent()
-> load_project_context()
-> load_memory()
-> extract_requirement_candidates()
-> normalize_requirements()
-> validate_requirements()
-> diff_requirement_sets()
-> resolve_next_version()
-> write_outputs()
-> update_memory()
-> save_memory()
```

## 运行状态

当前代码会返回以下状态之一：

- `BLOCKED`：缺少关键输入。
- `DRAFT_READY`：已生成草稿，但存在阻塞型待确认问题。
- `REVISION_REQUIRED`：存在 critical 或 high 级别问题。
- `BASELINE_READY`：需求通过当前检查，可作为基线输出。

## 当前样例输出

当前样例输出为：

- Project: `校园活动策划与报名管理平台`
- Version: `v1.0`
- Status: `BASELINE_READY`
- Functional Requirements: `26`
- Non-functional Requirements: `9`
- Business Rules: `30`
- Edge Cases: `10`
- Acceptance Criteria: `26`
- Open Questions: `1`

## 相关文档

- 根说明：[`../README.md`](../README.md)
- 当前实现规格：[`../requirements.md`](../requirements.md)
- 实现进度：[`../agentwork.md`](../agentwork.md)
