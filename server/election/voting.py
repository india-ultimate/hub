from collections import defaultdict
from dataclasses import dataclass

from django.shortcuts import get_object_or_404

from server.election.models import Candidate, Election, ElectionResult, RankedVote, RankedVoteChoice


@dataclass
class RoundResult:
    """Results of a single round of voting"""

    votes: dict[int, int]  # candidate_id -> vote count
    eliminated: list[Candidate]  # candidates eliminated in this round
    candidates: list[Candidate]  # all candidates in this round


def get_first_choice_votes(
    election_id: int, active_candidate_ids: set[int] | None = None
) -> dict[int, int]:
    """Get first choice votes for each candidate (optionally only for active candidates)"""
    votes: dict[int, int] = defaultdict(int)
    for vote in RankedVote.objects.filter(election_id=election_id):
        # Find the first ranked choice that is still active
        choices = RankedVoteChoice.objects.filter(vote=vote).order_by("rank")
        for choice in choices:
            if active_candidate_ids is None or choice.candidate_id in active_candidate_ids:
                votes[choice.candidate_id] += 1
                break
    return votes


def get_quota(total_votes: int, num_winners: int) -> int:
    """Calculate the quota for STV"""
    return (total_votes // (num_winners + 1)) + 1


def save_round_results(
    election_id: int, round_num: int, round_result: RoundResult, round_winners: list[Candidate]
) -> None:
    """Save the results of a voting round"""
    ElectionResult.objects.filter(election_id=election_id, round_number=round_num).delete()
    for candidate in round_result.candidates:
        status = (
            "winner"
            if candidate in round_winners
            else "eliminated"
            if candidate in round_result.eliminated
            else "active"
        )
        ElectionResult.objects.create(
            election_id=election_id,
            candidate=candidate,
            round_number=round_num,
            votes=round_result.votes.get(candidate.id, 0),
            status=status,
        )


def instant_runoff_voting(election_id: int) -> list[RoundResult]:
    """Implement Instant Runoff Voting (IRV)"""
    election = Election.objects.get(id=election_id)
    candidates = list(Candidate.objects.filter(election=election))
    if not candidates:
        return []
    results: list[RoundResult] = []
    active_candidates = set(candidates)
    active_candidate_ids = {c.id for c in active_candidates}
    eliminated_ids: set[int] = set()
    current_votes = get_first_choice_votes(election_id, active_candidate_ids)
    results.append(
        RoundResult(votes=current_votes.copy(), eliminated=[], candidates=list(active_candidates))
    )
    round_num = 1
    round_winners_per_round: list[list[Candidate]] = []
    while len(active_candidates) > 1:
        print(f"\n[IRV] Round {round_num} votes: {current_votes}")
        total_votes = sum(current_votes.get(c.id, 0) for c in active_candidates)
        round_winners = []
        if total_votes == 0:
            print("[IRV] No votes left. Stopping.")
            break
        for c in active_candidates:
            if current_votes.get(c.id, 0) > total_votes / 2:
                round_winners.append(c)
        if round_winners:
            print("[IRV] Winner found. Stopping.")
            round_winners_per_round.append(round_winners)
            break
        min_votes = min(current_votes.get(c.id, 0) for c in active_candidates)
        eliminated = [c for c in active_candidates if current_votes.get(c.id, 0) == min_votes]
        print(f"[IRV] Eliminating candidates: {[c.id for c in eliminated]}")
        if len(eliminated) == len(active_candidates):
            eliminated = list(eliminated)[:-1]
        for candidate in eliminated:
            active_candidates.remove(candidate)
            eliminated_ids.add(candidate.id)
            results[-1].eliminated.append(candidate)
        if active_candidates:
            current_votes = get_first_choice_votes(election_id, {c.id for c in active_candidates})
            results.append(
                RoundResult(
                    votes=current_votes.copy(), eliminated=[], candidates=list(active_candidates)
                )
            )
        round_winners_per_round.append([])
        round_num += 1
    # Save results for each round
    for i, round_result in enumerate(results):
        round_winners = round_winners_per_round[i] if i < len(round_winners_per_round) else []
        save_round_results(election_id, i + 1, round_result, round_winners)
    print(f"[IRV] Final results: {[(r.votes, [c.id for c in r.eliminated]) for r in results]}")
    return results


def single_transferable_vote(election_id: int, num_seats: int | None = None) -> list[RoundResult]:
    """Calculate election results using Single Transferable Vote"""
    election = get_object_or_404(Election, id=election_id)
    candidates = list(election.candidates.all())

    # If num_seats is not provided, use election.num_winners
    if num_seats is None:
        num_seats = election.num_winners

    # Get all votes
    votes = RankedVote.objects.filter(election=election)
    total_votes = votes.count()

    if total_votes == 0:
        return [RoundResult(candidates=candidates, votes={}, eliminated=[])]

    # Calculate quota
    quota = get_quota(total_votes, num_seats)

    results: list[RoundResult] = []
    active_candidates = set(candidates)
    active_candidate_ids = {c.id for c in active_candidates}
    eliminated_ids: set[int] = set()
    current_votes = get_first_choice_votes(election_id, active_candidate_ids)
    total_votes = sum(current_votes.values())
    winners: list[Candidate] = []
    results.append(
        RoundResult(votes=current_votes.copy(), eliminated=[], candidates=list(active_candidates))
    )
    round_num = 1
    round_winners_per_round: list[list[Candidate]] = []
    while len(winners) < num_seats and active_candidates:
        print(f"\n[STV] Round {round_num} votes: {current_votes}")
        if len(active_candidates) == (num_seats - len(winners)):
            print(
                f"[STV] All remaining candidates are winners: {[c.id for c in active_candidates]}"
            )
            round_winners = list(active_candidates)
            winners.extend(round_winners)
            round_winners_per_round.append(round_winners)
            break
        round_winners = [c for c in active_candidates if current_votes.get(c.id, 0) >= quota]
        if round_winners:
            round_winners.sort(key=lambda c: current_votes.get(c.id, 0), reverse=True)
            print(f"[STV] Winners this round: {[c.id for c in round_winners]}")
            winners.extend(round_winners)
            for winner in round_winners:
                active_candidates.remove(winner)
            round_winners_per_round.append(round_winners)
            if len(winners) < num_seats and active_candidates:
                current_votes = get_first_choice_votes(
                    election_id, {c.id for c in active_candidates}
                )
                results.append(
                    RoundResult(
                        votes=current_votes.copy(),
                        eliminated=[],
                        candidates=list(active_candidates),
                    )
                )
            round_num += 1
            continue
        min_votes = min(current_votes.get(c.id, 0) for c in active_candidates)
        eliminated = [c for c in active_candidates if current_votes.get(c.id, 0) == min_votes]
        print(f"[STV] Eliminating candidates: {[c.id for c in eliminated]}")
        if len(eliminated) == len(active_candidates):
            eliminated = list(eliminated)[: -(num_seats - len(winners))]
        for candidate in eliminated:
            active_candidates.remove(candidate)
            eliminated_ids.add(candidate.id)
            results[-1].eliminated.append(candidate)
        round_winners_per_round.append([])
        if active_candidates:
            current_votes = get_first_choice_votes(election_id, {c.id for c in active_candidates})
            results.append(
                RoundResult(
                    votes=current_votes.copy(), eliminated=[], candidates=list(active_candidates)
                )
            )
        round_num += 1
    for i, round_result in enumerate(results):
        round_winners = round_winners_per_round[i] if i < len(round_winners_per_round) else []
        save_round_results(election_id, i + 1, round_result, round_winners)
    print(f"[STV] Final results: {[(r.votes, [c.id for c in r.eliminated]) for r in results]}")
    return results
