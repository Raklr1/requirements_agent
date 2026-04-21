本文档只描述 `Requirements Agent` 的设计与实现方案，不包含其他 Agent 的设计。目标是让开发者可以直接依据本文档实现一个可运行的需求分析 Agent，并将其接入课程作业中的多 Agent 开发团队。

该 Agent 在整体瀑布式流程中的位置为：

`软件主题/产品方向确认 -> Requirements Agent -> 设计 Agent / 开发 Agent / 测试 Agent`

它的职责是把题目描述、原型、约束等上游输入，转化为结构化、可检查、可追踪、可交付的需求基线文档。
项目结构：
requirements_agent/
  app.py
  config/
    settings.yaml
    rule_config.yaml
  prompts/
    system_prompt.txt
    extract_requirements.txt
    refine_requirements.txt
    generate_srs.txt
    generate_questions.txt
  src/
    models.py
    orchestrator.py
    parser.py
    extractor.py
    normalizer.py
    validator.py
    writer.py
    memory.py
    traceability.py
    differ.py
  inputs/
    product_brief.md
    prototype.md
    constraints.yaml
    feedback.md
  outputs/
  memory/
  logs/
  tests/