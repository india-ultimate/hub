import hashlib
import secrets
from typing import Any

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import File, Router
from ninja.files import UploadedFile

from server.core.models import User

from .models import (
    Candidate,
    Election,
    ElectionResult,
    EligibleVoter,
    RankedVote,
    RankedVoteChoice,
    VoterVerification,
)
from .schema import (
    CandidateCreateSchema,
    CandidateSchema,
    ElectionCreateSchema,
    ElectionResultSchema,
    ElectionSchema,
    EligibleVoterSchema,
    ErrorSchema,
    RankedVoteCreateSchema,
    RankedVoteSchema,
    VoterVerificationSchema,
)
from .voting import instant_runoff_voting, single_transferable_vote

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


def check_staff(request: AuthenticatedHttpRequest) -> tuple[int, dict[str, str]] | None:
    """Check if the user is staff, return 403 response if not"""
    if not request.user.is_staff:
        return 403, {"message": "Only staff members can perform this action"}
    return None


@router.get("/", response=list[ElectionSchema])
def list_elections(request: AuthenticatedHttpRequest) -> list[dict[str, Any]]:
    """List all elections"""
    elections = Election.objects.filter(is_active=True)
    return [
        {
            "id": election.id,
            "title": election.title,
            "description": election.description,
            "start_date": election.start_date,
            "end_date": election.end_date,
            "is_active": election.is_active,
            "num_winners": election.num_winners,
            "voting_method": election.voting_method,
            "created_at": election.created_at,
            "updated_at": election.updated_at,
        }
        for election in elections
    ]


@router.post("/", response=ElectionSchema)
def create_election(
    request: AuthenticatedHttpRequest, data: ElectionCreateSchema
) -> Election | tuple[int, dict[str, str]]:
    """Create a new election"""
    if error := check_staff(request):
        return error
    return Election.objects.create(**data.dict())


@router.get("/{election_id}/", response=ElectionSchema)
def get_election(request: AuthenticatedHttpRequest, election_id: int) -> dict[str, Any]:
    election = get_object_or_404(Election, id=election_id)

    # Get winners if election is over
    winners = None
    if ElectionResult.objects.filter(election=election).exists():
        # Get the final round results
        final_round = (
            ElectionResult.objects.filter(election=election)
            .values("round_number")
            .order_by("-round_number")
            .first()
        )

        if final_round is not None:
            final_results = ElectionResult.objects.filter(
                election=election, round_number=final_round["round_number"]
            ).filter(status="winner")

            winners = []
            for result in final_results:
                winners.append(
                    {
                        "id": result.candidate.id,
                        "name": result.candidate.user.get_full_name(),
                        "votes": result.votes,
                    }
                )

    # Convert election to dict and add winners
    election_dict = {
        "id": election.id,
        "title": election.title,
        "description": election.description,
        "start_date": election.start_date,
        "end_date": election.end_date,
        "is_active": election.is_active,
        "num_winners": election.num_winners,
        "voting_method": election.voting_method,
        "created_at": election.created_at,
        "updated_at": election.updated_at,
        "winners": winners,
    }

    return election_dict


@router.get("/{election_id}/candidates/", response=list[CandidateSchema])
def list_candidates(request: AuthenticatedHttpRequest, election_id: int) -> list[dict[str, Any]]:
    candidates = Candidate.objects.filter(election_id=election_id).select_related("user")
    return [
        {
            "id": candidate.id,
            "election_id": candidate.election_id,
            "user_id": candidate.user_id,
            "bio": candidate.bio,
            "created_at": candidate.created_at,
            "user": {
                "id": candidate.user.id,
                "username": candidate.user.username,
                "full_name": candidate.user.get_full_name(),
            },
        }
        for candidate in candidates
    ]


@router.post("/{election_id}/candidates/", response=CandidateSchema)
def create_candidate(
    request: AuthenticatedHttpRequest, election_id: int, data: CandidateCreateSchema
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Create a new candidate for an election"""
    if error := check_staff(request):
        return error
    election = get_object_or_404(Election, id=election_id)
    candidate = Candidate.objects.create(election=election, **data.dict())

    return {
        "id": candidate.id,
        "election_id": candidate.election_id,
        "user_id": candidate.user_id,
        "bio": candidate.bio,
        "created_at": candidate.created_at,
        "user": {
            "id": candidate.user.id,
            "username": candidate.user.username,
            "full_name": candidate.user.get_full_name(),
        },
    }


@router.post("/{election_id}/eligible-voters/", response=list[EligibleVoterSchema])
def import_eligible_voters(
    request: AuthenticatedHttpRequest,
    election_id: int,
    file: UploadedFile = File(...),  # noqa: B008
) -> list[dict[str, Any]] | tuple[int, dict[str, str]]:
    """Import eligible voters from a CSV file"""
    if error := check_staff(request):
        return error

    if not file:
        return 400, {"message": "No file provided"}

    election = get_object_or_404(Election, id=election_id)

    # Read CSV data
    csv_data = file.read().decode("utf-8")

    # Import voters
    election.import_eligible_voters(csv_data)

    # Return updated list of eligible voters
    return [
        {
            "id": voter.id,
            "election_id": voter.election_id,
            "user_id": voter.user_id,
            "created_at": voter.created_at,
            "user": {
                "id": voter.user.id,
                "username": voter.user.username,
                "full_name": voter.user.get_full_name(),
            },
        }
        for voter in election.eligible_voters.all()
    ]


@router.get(
    "/{election_id}/eligible-voters/", response={200: list[EligibleVoterSchema], 403: ErrorSchema}
)
def list_eligible_voters(
    request: AuthenticatedHttpRequest, election_id: int
) -> list[dict[str, Any]] | tuple[int, dict[str, str]]:
    """List all eligible voters for an election"""
    if error := check_staff(request):
        return error
    election = get_object_or_404(Election, id=election_id)
    eligible_voters = election.eligible_voters.all().select_related("user")
    return [
        {
            "id": voter.id,
            "election_id": voter.election_id,
            "user_id": voter.user_id,
            "created_at": voter.created_at,
            "user": {
                "id": voter.user.id,
                "username": voter.user.username,
                "full_name": voter.user.get_full_name(),
            },
        }
        for voter in eligible_voters
    ]


@router.delete(
    "/{election_id}/eligible-voters/{user_id}/", response={200: dict[str, bool], 403: ErrorSchema}
)
def remove_eligible_voter(
    request: AuthenticatedHttpRequest, election_id: int, user_id: int
) -> dict[str, bool] | tuple[int, dict[str, str]]:
    """Remove a voter from the eligible voters list"""
    if error := check_staff(request):
        return error
    election = get_object_or_404(Election, id=election_id)
    user = get_object_or_404(User, id=user_id)
    EligibleVoter.objects.filter(election=election, user=user).delete()
    return {"success": True}


@router.get("/{election_id}/verify/", response={200: VoterVerificationSchema, 400: ErrorSchema})
def get_voter_verification(
    request: AuthenticatedHttpRequest, election_id: int
) -> VoterVerification | tuple[int, dict[str, str]]:
    """Get a verification token for voting"""
    election = get_object_or_404(Election, id=election_id)

    # Check if user is eligible to vote
    if not EligibleVoter.objects.filter(election=election, user=request.user).exists():
        return 400, {"message": "You are not eligible to vote in this election"}

    # Check if user already has a verification token
    verification = VoterVerification.objects.filter(election=election, user=request.user).first()

    if verification:
        return verification

    # Generate new verification token
    token = VoterVerification.generate_token(election.id, request.user.id)
    return VoterVerification.objects.get(verification_token=token)


@router.post("/{election_id}/vote/", response={200: RankedVoteSchema, 400: ErrorSchema})
def cast_ranked_vote(
    request: AuthenticatedHttpRequest, election_id: int, payload: RankedVoteCreateSchema
) -> RankedVote | tuple[int, dict[str, str]]:
    election = get_object_or_404(Election, id=election_id)

    # Verify the voter's token
    verification = get_object_or_404(
        VoterVerification,
        election=election,
        user=request.user,
        verification_token=payload.verification_token,
        is_used=False,
    )

    # Generate a unique voter hash
    voter_identifier = f"{request.user.id}:{election_id}:{secrets.token_hex(16)}"
    voter_hash = hashlib.sha256(voter_identifier.encode()).hexdigest()

    try:
        # Create the vote record with hashed identifier
        vote = RankedVote.objects.create(election=election, voter_hash=voter_hash)

        # Create the ranked choices
        for choice in payload.choices:
            RankedVoteChoice.objects.create(
                vote=vote, candidate_id=choice.candidate_id, rank=choice.rank
            )

        # Mark verification token as used
        verification.mark_as_used()

        return vote
    except Exception as e:
        # If anything fails, ensure the verification token isn't marked as used
        verification.refresh_from_db()
        if not verification.is_used:
            verification.delete()
        return 400, {"message": str(e)}


@router.post(
    "/{election_id}/generate-results/", response={200: ElectionResultSchema, 403: ErrorSchema}
)
def generate_election_results(
    request: AuthenticatedHttpRequest, election_id: int
) -> dict[str, list[dict[str, Any]]] | tuple[int, dict[str, str]]:
    """Generate election results. Only staff can access this endpoint."""
    if error := check_staff(request):
        return error
    election = get_object_or_404(Election, id=election_id)

    # Clear existing results
    ElectionResult.objects.filter(election=election).delete()

    # Get results based on voting method
    if election.voting_method == "IRV":
        rounds = instant_runoff_voting(election_id)
    else:  # STV
        rounds = single_transferable_vote(election_id)

    # Convert rounds to schema format
    round_results = []
    for round in rounds:
        candidates = []
        for candidate in round.candidates:
            candidates.append(
                {
                    "id": candidate.id,
                    "name": candidate.user.get_full_name(),
                    "votes": round.votes.get(candidate.id, 0),
                    "status": "eliminated" if candidate in round.eliminated else "active",
                }
            )
        round_results.append({"candidates": candidates})

    return {"rounds": round_results}


@router.get("/{election_id}/results/", response={200: ElectionResultSchema, 403: ErrorSchema})
def get_election_results(
    request: AuthenticatedHttpRequest, election_id: int
) -> dict[str, list[dict[str, Any]]] | tuple[int, dict[str, str]]:
    """Get election results from database. Only staff can access this endpoint."""
    if error := check_staff(request):
        return error
    election = get_object_or_404(Election, id=election_id)

    # Get all rounds for this election
    rounds = ElectionResult.objects.filter(election=election).order_by("round_number")

    # Group results by round
    round_results = []
    current_round = None
    current_candidates: list[dict[str, Any]] = []

    # Process each result
    for result in rounds:
        # Handle round changes
        if current_round is None:
            # First round
            current_round = result.round_number
        elif result.round_number != current_round:  # type: ignore[unreachable]
            # Round change - save previous results and start new round
            round_results.append({"candidates": current_candidates})
            current_candidates = []
            current_round = result.round_number

        # Add the current result
        current_candidates.append(
            {
                "id": result.candidate.id,
                "name": result.candidate.user.get_full_name(),
                "votes": result.votes,
                "status": result.status,
            }
        )

    # Add the final round's results
    if current_candidates:
        round_results.append({"candidates": current_candidates})

    return {"rounds": round_results}
