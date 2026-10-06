"""Turn a candidate extraction into the atomic questions that verify it."""

from clinical_extraction.decisioning.schema import DecisionQuery
from clinical_extraction.decisioning.tasks import DecisionTask
from clinical_extraction.schema import ClinicalCaseExtraction


def build_queries(case: ClinicalCaseExtraction) -> list[DecisionQuery]:
    """Every check for one case, so a provider can answer them in a single call.

    Ids are positional (`findings.2.support`) rather than derived from the text,
    so they can be logged and stored without carrying clinical content.
    """
    queries: list[DecisionQuery] = []
    for index, finding in enumerate(case.findings):
        target = f"findings[{index}]"
        queries.append(
            DecisionQuery(
                id=f"findings.{index}.support",
                task=DecisionTask.FINDING_SUPPORT,
                target=target,
                subject=finding.value,
                index=index,
            )
        )
        queries.append(
            DecisionQuery(
                id=f"findings.{index}.category",
                task=DecisionTask.FINDING_CATEGORY,
                target=target,
                subject=finding.value,
                index=index,
            )
        )

    for index, answer in enumerate(case.answers):
        queries.append(
            DecisionQuery(
                id=f"answers.{index}.status",
                task=DecisionTask.DIAGNOSIS_STATUS,
                target=f"answers[{index}]",
                subject=answer.text,
                index=index,
            )
        )

    # The participant reads the title and the presentation before answering,
    # so neither may give the answer away.
    established = tuple(a.text for a in case.answers if a.is_correct)
    for field_name, text in (("title", case.title), ("presentation", case.presentation)):
        queries.append(
            DecisionQuery(
                id=f"{field_name}.leak",
                task=DecisionTask.DIAGNOSIS_LEAK,
                target=field_name,
                subject=text,
                reference=established,
            )
        )

    # One question about the list as a whole: support checks what was
    # extracted, this checks what was left out.
    queries.append(
        DecisionQuery(
            id="findings.completeness",
            task=DecisionTask.FINDING_COMPLETENESS,
            target="findings",
            subject="",
            reference=tuple(f.value for f in case.findings),
        )
    )
    return queries
