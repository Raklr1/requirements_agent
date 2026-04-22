from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .llm_client import LLMClient, PromptBundle
from .models import (
    AcceptanceCriterion,
    BusinessRule,
    ClarificationQuestion,
    EdgeCase,
    FunctionalRequirement,
    NonFunctionalRequirement,
    ProjectContext,
    RequirementDraft,
)


def extract_requirement_candidates(
    context: ProjectContext,
    llm_client: LLMClient | None = None,
    prompt_dir: str | Path | None = None,
    *,
    allow_fallback: bool = True,
) -> RequirementDraft:
    if llm_client and llm_client.is_available:
        try:
            return _extract_with_llm(context, llm_client, prompt_dir)
        except Exception:
            if not allow_fallback:
                raise

    return _extract_with_heuristics(context)


def _extract_with_llm(
    context: ProjectContext,
    llm_client: LLMClient,
    prompt_dir: str | Path | None,
) -> RequirementDraft:
    system_prompt = _load_prompt(
        prompt_dir,
        "system_prompt.txt",
        "You are a requirements analysis agent. Output JSON only.",
    )
    extract_prompt = _load_prompt(
        prompt_dir,
        "extract_requirements.txt",
        "Return JSON with functional_requirements, non_functional_requirements, business_rules, edge_cases, acceptance_criteria, open_questions, assumptions. Context: {{CONTEXT_JSON}}",
    )
    rendered_prompt = extract_prompt.replace(
        "{{CONTEXT_JSON}}",
        json.dumps(context.to_dict(), ensure_ascii=False, indent=2),
    )

    payload = llm_client.complete_json(
        PromptBundle(system_prompt=system_prompt, user_prompt=rendered_prompt)
    )
    draft = RequirementDraft(
        functional_requirements=[
            _coerce_functional_requirement(item) for item in payload.get("functional_requirements", [])
        ],
        non_functional_requirements=[
            _coerce_non_functional_requirement(item) for item in payload.get("non_functional_requirements", [])
        ],
        business_rules=[_coerce_business_rule(item) for item in payload.get("business_rules", [])],
        edge_cases=[_coerce_edge_case(item) for item in payload.get("edge_cases", [])],
        acceptance_criteria=[
            _coerce_acceptance_criterion(item) for item in payload.get("acceptance_criteria", [])
        ],
        open_questions=[_coerce_question(item) for item in payload.get("open_questions", [])],
        assumptions=[str(item) for item in payload.get("assumptions", [])],
    )

    if not draft.open_questions:
        draft.open_questions = _heuristic_questions(context)
    return draft


def _extract_with_heuristics(context: ProjectContext) -> RequirementDraft:
    functional_requirements = _heuristic_functional_requirements(context)
    non_functional_requirements = _heuristic_non_functional_requirements(context)
    business_rules = _heuristic_business_rules(context)
    edge_cases = _heuristic_edge_cases(context)
    acceptance_criteria = _heuristic_acceptance_criteria(functional_requirements)
    open_questions = _heuristic_questions(context)

    return RequirementDraft(
        functional_requirements=functional_requirements,
        non_functional_requirements=non_functional_requirements,
        business_rules=business_rules,
        edge_cases=edge_cases,
        acceptance_criteria=acceptance_criteria,
        open_questions=open_questions,
    )


def _heuristic_functional_requirements(context: ProjectContext) -> list[FunctionalRequirement]:
    candidates: list[FunctionalRequirement] = []
    seen_titles: set[str] = set()

    brief = context.documents.get("product_brief.md")
    if brief:
        for ref, section_text in brief.sections.items():
            if not _is_functional_section(ref):
                continue
            for item in _extract_list_items(section_text):
                title = _clean_requirement_title(item)
                if not title or title.lower() in seen_titles:
                    continue
                seen_titles.add(title.lower())
                actors = _infer_actors(title, ref)
                candidates.append(
                    FunctionalRequirement(
                        title=title,
                        description=f"系统应支持{title}，并确保相关角色可按规范完成对应操作。",
                        actors=actors,
                        preconditions=_build_preconditions(title, actors),
                        main_flow=_build_main_flow(title, actors),
                        alternate_flow=_build_alternate_flow(title),
                        postconditions=_build_postconditions(title),
                        priority="high",
                        source=[ref],
                        status="proposed",
                    )
                )

    return candidates


def _heuristic_non_functional_requirements(context: ProjectContext) -> list[NonFunctionalRequirement]:
    requirements: list[NonFunctionalRequirement] = []
    brief = context.documents.get("product_brief.md")
    if not brief:
        return requirements

    for ref, section_text in brief.sections.items():
        category = _nfr_category_from_ref(ref)
        if not category:
            continue
        for item in _extract_list_items(section_text):
            requirements.append(
                NonFunctionalRequirement(
                    category=category,
                    title=item,
                    description=f"系统应满足“{item}”对应的非功能目标。",
                    metric=_infer_metric(item, category),
                    scope=["全系统"] if category != "performance" else ["首页", "列表页", "详情页"],
                    priority="medium" if category == "maintainability" else "high",
                    source=[ref],
                )
            )
    return requirements


def _heuristic_business_rules(context: ProjectContext) -> list[BusinessRule]:
    rules: list[BusinessRule] = []
    brief = context.documents.get("product_brief.md")
    if not brief:
        return rules

    for ref, section_text in brief.sections.items():
        if "规则" not in ref and "状态" not in ref:
            continue
        if not any(keyword in ref for keyword in ("角色", "报名", "审核", "活动状态")):
            continue
        for item in _extract_list_items(section_text):
            rules.append(
                BusinessRule(
                    title=_truncate_title(item),
                    description=item,
                    priority="high",
                    source=[ref],
                    status="proposed",
                )
            )
    return rules


def _heuristic_edge_cases(context: ProjectContext) -> list[EdgeCase]:
    edge_cases: list[EdgeCase] = []
    for file_name, document in context.documents.items():
        if not file_name.endswith(".md"):
            continue
        for ref, section_text in document.sections.items():
            if "异常" not in ref and "边界" not in ref:
                continue
            for item in _extract_list_items(section_text):
                edge_cases.append(
                    EdgeCase(
                        title=_truncate_title(item),
                        description=item,
                        source=[ref],
                        status="proposed",
                    )
                )
    return edge_cases


def _heuristic_acceptance_criteria(requirements: list[FunctionalRequirement]) -> list[AcceptanceCriterion]:
    criteria: list[AcceptanceCriterion] = []
    for requirement in requirements:
        actor = requirement.actors[0] if requirement.actors else "用户"
        criteria.append(
            AcceptanceCriterion(
                scenario=requirement.title,
                given=f"{actor}满足前置条件并进入相关功能页面",
                when=f"{actor}执行“{requirement.title}”对应的主要操作",
                then=requirement.postconditions[0] if requirement.postconditions else f"系统完成“{requirement.title}”并给出可观察结果",
                source=list(requirement.source),
                linked_requirement_title=requirement.title,
            )
        )
    return criteria


def _heuristic_questions(context: ProjectContext) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []

    for index, file_name in enumerate(context.missing_inputs, start=1):
        questions.append(
            ClarificationQuestion(
                question_id=f"Q-MISSING-{index:03d}",
                question=f"是否补充关键输入文件 {file_name}？",
                reason="缺少关键输入会降低需求抽取的可信度和完整性。",
                default_option="若暂时缺失，则仅基于现有输入生成草稿并标记为待确认。",
                blocking=True,
            )
        )

    if not context.target_users:
        questions.append(
            ClarificationQuestion(
                question_id="Q-ROLE-001",
                question="系统是否需要明确区分不同用户角色？",
                reason="角色边界会直接影响页面入口、权限和后续开发范围。",
                default_option="若未补充，则默认保留游客、学生用户、活动负责人、管理员四类角色。",
                blocking=True,
            )
        )

    if not context.scenarios:
        questions.append(
            ClarificationQuestion(
                question_id="Q-SCENE-001",
                question="是否需要补充更完整的核心使用场景？",
                reason="缺少场景会影响功能需求、异常流程和验收标准的覆盖。",
                default_option="若未补充，则仅基于页面和流程文字生成最小闭环场景。",
                blocking=False,
            )
        )

    if not context.constraints:
        questions.append(
            ClarificationQuestion(
                question_id="Q-CONSTRAINT-001",
                question="是否有需要明确写入需求基线的课程、时间或技术约束？",
                reason="约束条件会影响可实现性判断和非功能需求边界。",
                default_option="若未提供，则默认按照课程项目范围与现有 Web 平台定位处理。",
                blocking=False,
            )
        )

    return questions


def _load_prompt(prompt_dir: str | Path | None, file_name: str, fallback: str) -> str:
    if not prompt_dir:
        return fallback
    path = Path(prompt_dir) / file_name
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    return text or fallback


def _extract_list_items(section_text: str) -> list[str]:
    items: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d+\.\s+", stripped):
            items.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
        elif re.match(r"^[-*]\s+", stripped):
            items.append(re.sub(r"^[-*]\s+", "", stripped).strip())
    return items


def _is_functional_section(ref: str) -> bool:
    return any(
        keyword in ref
        for keyword in (
            "账户",
            "活动浏览",
            "学生报名",
            "工作台",
            "审核与发布",
            "统计与记录",
        )
    )


def _infer_actors(title: str, ref: str) -> list[str]:
    if any(keyword in title for keyword in ("注册", "登录", "退出登录")):
        return ["游客", "学生用户", "活动负责人", "管理员"]
    if any(keyword in title for keyword in ("浏览", "搜索", "筛选", "查看详情", "活动广场")):
        return ["游客", "学生用户"]
    if any(keyword in title for keyword in ("报名", "取消报名", "我的报名")):
        return ["学生用户"]
    if any(keyword in title for keyword in ("创建", "编辑", "提交审核", "查看审核状态", "查看报名名单")):
        return ["活动负责人"]
    if any(keyword in title for keyword in ("审核", "发布", "驳回", "统计")) or "审核" in ref:
        return ["管理员"]
    return ["用户"]


def _build_preconditions(title: str, actors: list[str]) -> list[str]:
    if "退出登录" in title:
        return ["用户当前处于已登录状态"]
    if any(keyword in title for keyword in ("注册", "浏览", "搜索", "筛选", "查看详情")):
        return ["用户具备访问平台的基础条件"]
    if any(keyword in title for keyword in ("登录", "退出登录")):
        return ["用户已拥有有效账号"] if "登录" in title else ["用户当前处于已登录状态"]
    if any(keyword in title for keyword in ("报名", "取消报名")):
        return ["学生用户已登录", "活动满足报名或取消报名条件"]
    if any(keyword in title for keyword in ("创建", "编辑", "提交审核")):
        return ["活动负责人已登录"]
    if any(keyword in title for keyword in ("审核", "发布", "驳回", "统计")):
        return ["管理员已登录"]
    return [f"{actors[0] if actors else '用户'}已进入对应功能入口"]


def _build_main_flow(title: str, actors: list[str]) -> list[str]:
    actor = actors[0] if actors else "用户"
    if "退出登录" in title:
        return ["用户点击退出登录", "系统清理当前会话", "系统返回公共入口或登录页"]
    if "注册" in title:
        return ["进入注册页面", "填写必要信息", "提交注册表单", "系统校验后创建账号"]
    if "登录" in title:
        return ["进入登录页面", "输入账号与密码", "提交登录请求", "系统验证身份并跳转"]
    if any(keyword in title for keyword in ("浏览", "搜索", "筛选", "查看详情")):
        return [f"{actor}进入活动广场或详情页", "设置查询条件或查看内容", "系统返回匹配结果"]
    if "报名" in title and "取消" not in title:
        return ["进入活动详情页", "点击报名", "系统校验资格与名额", "系统创建报名记录并反馈成功"]
    if "取消报名" in title:
        return ["进入个人中心或活动详情页", "点击取消报名", "系统校验是否允许取消", "系统释放名额并更新状态"]
    if any(keyword in title for keyword in ("创建", "编辑")):
        return ["进入活动编辑页", "填写或修改活动信息", "保存草稿或提交变更"]
    if "提交审核" in title:
        return ["进入活动负责人工作台", "选择待提交活动", "提交审核请求", "系统更新活动状态为待审核"]
    if any(keyword in title for keyword in ("审核", "发布", "驳回")):
        return ["进入管理员审核中心", "查看活动详情", "执行审核决策", "系统更新活动状态并记录结果"]
    if "统计" in title:
        return ["进入后台统计页", "系统汇总活动与报名数据", "展示统计结果与最近记录"]
    return [f"{actor}进入对应功能入口", f"{actor}执行“{title}”相关操作", "系统完成处理并返回结果"]


def _build_alternate_flow(title: str) -> list[str]:
    if "退出登录" in title:
        return ["若会话已失效，则系统提示当前无需重复退出"]
    if "注册" in title:
        return ["若账号标识已存在，则系统提示不可重复注册"]
    if "登录" in title:
        return ["若账号或密码错误，则系统给出明确错误提示"]
    if "报名" in title and "取消" not in title:
        return ["若活动已满员、已截止、未发布或重复报名，则系统阻止报名并给出原因"]
    if "取消报名" in title:
        return ["若已超过可取消时间或状态不允许，则系统阻止取消并提示原因"]
    if any(keyword in title for keyword in ("审核", "发布", "驳回")):
        return ["若活动信息不完整，则系统阻止通过并要求补充原因或修改"]
    return ["若输入不合法或状态不允许，则系统给出提示并保留当前数据"]


def _build_postconditions(title: str) -> list[str]:
    if "退出登录" in title:
        return ["当前登录会话被安全结束"]
    if "注册" in title:
        return ["用户账号被创建"]
    if "登录" in title:
        return ["用户进入与角色匹配的首页或工作台"]
    if any(keyword in title for keyword in ("浏览", "搜索", "筛选", "查看详情")):
        return ["用户获得可查看的活动信息结果"]
    if "报名" in title and "取消" not in title:
        return ["报名记录被创建，活动已报名人数被更新"]
    if "取消报名" in title:
        return ["报名状态被取消，名额被释放"]
    if any(keyword in title for keyword in ("创建", "编辑")):
        return ["活动草稿或活动信息被保存"]
    if "提交审核" in title:
        return ["活动状态变为待审核"]
    if any(keyword in title for keyword in ("审核", "发布", "驳回")):
        return ["活动状态与审核记录被更新"]
    if "统计" in title:
        return ["管理员可查看最新统计结果"]
    return [f"系统完成“{title}”相关处理"]


def _nfr_category_from_ref(ref: str) -> str:
    mapping = {
        "易用性": "usability",
        "性能": "performance",
        "可靠性": "reliability",
        "可维护性": "maintainability",
    }
    for key, category in mapping.items():
        if key in ref:
            return category
    return ""


def _infer_metric(item: str, category: str) -> str:
    if category == "performance":
        if "2 秒" in item or "2秒" in item:
            return "response_time_lt_2s"
        return "metric_to_be_confirmed"
    if category == "reliability":
        return "error_handling_defined"
    if category == "usability":
        return "flow_steps_minimized"
    if category == "maintainability":
        return "module_boundaries_clear"
    return "metric_to_be_confirmed"


def _clean_requirement_title(item: str) -> str:
    item = item.strip("：:。 ")
    if len(item) <= 24:
        return item
    for separator in ("，", "。", "；", "、"):
        if separator in item:
            return item.split(separator, 1)[0].strip()
    return item[:24].strip()


def _truncate_title(item: str) -> str:
    if len(item) <= 30:
        return item
    for separator in ("，", "。", "；", "、"):
        if separator in item:
            return item.split(separator, 1)[0].strip()
    return item[:30].strip()


def _coerce_functional_requirement(item: dict[str, Any]) -> FunctionalRequirement:
    return FunctionalRequirement(
        id=str(item.get("id", "")),
        title=str(item.get("title", "")),
        description=str(item.get("description", "")),
        actors=[str(value) for value in item.get("actors", [])],
        preconditions=[str(value) for value in item.get("preconditions", [])],
        main_flow=[str(value) for value in item.get("main_flow", [])],
        alternate_flow=[str(value) for value in item.get("alternate_flow", [])],
        postconditions=[str(value) for value in item.get("postconditions", [])],
        priority=str(item.get("priority", "medium")),
        source=[str(value) for value in item.get("source", [])],
        acceptance_ids=[str(value) for value in item.get("acceptance_ids", [])],
        status=str(item.get("status", "proposed")),
    )


def _coerce_non_functional_requirement(item: dict[str, Any]) -> NonFunctionalRequirement:
    return NonFunctionalRequirement(
        id=str(item.get("id", "")),
        category=str(item.get("category", "")),
        title=str(item.get("title", "")),
        description=str(item.get("description", "")),
        metric=str(item.get("metric", "")),
        scope=[str(value) for value in item.get("scope", [])],
        priority=str(item.get("priority", "medium")),
        source=[str(value) for value in item.get("source", [])],
    )


def _coerce_business_rule(item: dict[str, Any]) -> BusinessRule:
    return BusinessRule(
        id=str(item.get("id", "")),
        title=str(item.get("title", "")),
        description=str(item.get("description", "")),
        priority=str(item.get("priority", "medium")),
        source=[str(value) for value in item.get("source", [])],
        status=str(item.get("status", "proposed")),
    )


def _coerce_edge_case(item: dict[str, Any]) -> EdgeCase:
    return EdgeCase(
        id=str(item.get("id", "")),
        title=str(item.get("title", "")),
        description=str(item.get("description", "")),
        related_requirement_ids=[str(value) for value in item.get("related_requirement_ids", [])],
        source=[str(value) for value in item.get("source", [])],
        status=str(item.get("status", "proposed")),
    )


def _coerce_acceptance_criterion(item: dict[str, Any]) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        id=str(item.get("id", "")),
        requirement_id=str(item.get("requirement_id", "")),
        scenario=str(item.get("scenario", "")),
        given=str(item.get("given", "")),
        when=str(item.get("when", "")),
        then=str(item.get("then", "")),
        source=[str(value) for value in item.get("source", [])],
        linked_requirement_title=str(item.get("linked_requirement_title", "")),
    )


def _coerce_question(item: dict[str, Any]) -> ClarificationQuestion:
    return ClarificationQuestion(
        question_id=str(item.get("question_id", "")),
        question=str(item.get("question", "")),
        reason=str(item.get("reason", "")),
        default_option=str(item.get("default_option", "")),
        blocking=bool(item.get("blocking", False)),
    )
