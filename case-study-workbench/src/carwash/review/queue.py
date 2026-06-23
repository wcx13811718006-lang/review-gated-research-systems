from __future__ import annotations

from carwash.review.routing import create_review, route_claim
from carwash.schemas import Case, Claim, Review, ReviewDecision, ReviewQueueItem, ReviewRoute, Source


def build_review_queue(
    *,
    cases: list[Case],
    claims: list[Claim],
    sources: list[Source],
    reviews: list[Review] | None = None,
    random_audit_rate: float = 0.0,
    default_reviewer_role: str = "reviewer",
) -> list[ReviewQueueItem]:
    cases_by_id = {case.id: case for case in cases}
    sources_by_id = {source.id: source for source in sources}
    reviews_by_object = {review.object_id: review for review in reviews or []}
    queue: list[ReviewQueueItem] = []

    for claim in claims:
        case = cases_by_id.get(claim.case_id)
        if case is None:
            continue
        claim_sources = [sources_by_id[source_id] for source_id in claim.source_ids if source_id in sources_by_id]
        existing_review = reviews_by_object.get(claim.id)
        if existing_review is not None:
            route = existing_review.route
            reviewer_role = existing_review.reviewer_role
            decision = existing_review.decision
            note = existing_review.note
        else:
            route = route_claim(
                case=case,
                claim=claim,
                sources=claim_sources,
                random_audit_rate=random_audit_rate,
            )
            reviewer_role = claim.reviewer or default_reviewer_role
            decision = ReviewDecision.PENDING
            generated_review = (
                create_review(
                    case=case,
                    claim=claim,
                    sources=claim_sources,
                    reviewer_role=reviewer_role,
                    random_audit_rate=random_audit_rate,
                )
                if route != ReviewRoute.NONE
                else None
            )
            note = generated_review.note if generated_review is not None else "No review required."

        if route == ReviewRoute.NONE:
            continue

        queue.append(
            ReviewQueueItem(
                id=f"QUEUE_{claim.id}",
                case_id=case.id,
                case_title=case.public_title,
                claim_id=claim.id,
                claim_text=claim.text,
                claim_class=claim.claim_class,
                route=route,
                reviewer_role=reviewer_role,
                decision=decision,
                note=note,
                source_ids=claim.source_ids,
                source_summaries=[
                    {
                        "id": source.id,
                        "owner": source.owner,
                        "authority": str(source.authority_level),
                        "url": str(source.url),
                        "fetch_status": str(source.fetch_status),
                    }
                    for source in claim_sources
                ],
                locator=claim.locator,
                risk_flags=claim.risk_flags,
            )
        )

    return sorted(queue, key=_queue_sort_key)


def filter_review_queue(
    items: list[ReviewQueueItem],
    *,
    route: ReviewRoute | None = None,
    decision: ReviewDecision | None = None,
    reviewer_role: str | None = None,
) -> list[ReviewQueueItem]:
    filtered = items
    if route is not None:
        filtered = [item for item in filtered if item.route == route]
    if decision is not None:
        filtered = [item for item in filtered if item.decision == decision]
    if reviewer_role is not None:
        filtered = [item for item in filtered if item.reviewer_role == reviewer_role]
    return filtered


def _queue_sort_key(item: ReviewQueueItem) -> tuple[int, str]:
    route_rank = {
        ReviewRoute.BLOCKED_EXPORT: 0,
        ReviewRoute.MANDATORY_FULL_REVIEW: 1,
        ReviewRoute.TARGETED_REVIEW: 2,
        ReviewRoute.RANDOM_AUDIT: 3,
        ReviewRoute.NONE: 4,
    }
    return route_rank[item.route], item.claim_id
