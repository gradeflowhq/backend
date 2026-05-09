from collections.abc import Sequence

from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.questions.types import QuestionId
from gradeflow_engine.rules.context import RuleContext
from gradeflow_engine.rules.schema import (
    compatible_rule_classes,
    context_for_path,
    rule_class,
    rule_label,
    rule_type,
)
from gradeflow_engine.submissions.models import Submission

from gradeflow_backend.schemas.rules import (
    CompatibleRulesResponse,
    RuleSchemaResponse,
    RuleTypeOption,
)
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError


def list_compatible_rules(
    question_set: QuestionSet,
    *,
    question_id: QuestionId | None = None,
    path: str | None = None,
) -> CompatibleRulesResponse:
    context = _rule_context(question_set, question_id=question_id, path=path)
    return CompatibleRulesResponse(
        rules=[
            RuleTypeOption(
                type=rule_type(rule),
                label=rule_label(rule),
            )
            for rule in compatible_rule_classes(context)
        ]
    )


def build_rule_schema(
    question_set: QuestionSet,
    *,
    rule_type: str,
    question_id: QuestionId | None = None,
    path: str | None = None,
    submissions: Sequence[Submission] = (),
) -> RuleSchemaResponse:
    context = _rule_context(
        question_set,
        question_id=question_id,
        path=path,
        submissions=submissions,
    )
    try:
        rule = rule_class(rule_type, context)
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    model = rule.from_context(context)
    schema = model.model_json_schema(mode="validation", union_format="primitive_type_array")
    return RuleSchemaResponse(
        schema=schema,
        initial_value=rule.initial_value_from_context(context),
    )


def _rule_context(
    question_set: QuestionSet,
    *,
    question_id: QuestionId | None,
    path: str | None,
    submissions: Sequence[Submission] = (),
) -> RuleContext:
    if not question_id:
        base_context = RuleContext(
            scope="global",
            question_set=question_set,
            submissions=submissions,
        )
    else:
        question = question_set.question_map.get(question_id)
        if question is None:
            raise NotFoundError(f"Question {question_id} not found")
        base_context = RuleContext(
            scope="question",
            question_set=question_set,
            submissions=submissions,
            question_id=question_id,
            question=question,
            question_id_editable=path is not None,
        )

    try:
        return context_for_path(base_context, path)
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
