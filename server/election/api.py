import hashlib
import secrets
import time
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from ninja import File, Router
from ninja.files import UploadedFile

from server.core.models import Guardianship, Player, User
from server.lib.email_worker import get_email_worker_status, queue_emails

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
    WardVoterVerificationSchema,
)
from .voting import instant_runoff_voting, single_transferable_vote

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


@router.get("/email-worker-status/", response={200: dict[str, Any], 403: ErrorSchema})
def get_email_worker_status_endpoint(
    request: AuthenticatedHttpRequest,
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Get the status of the email worker thread and queue"""
    if error := check_staff(request):
        return error

    return get_email_worker_status()


def check_staff(request: AuthenticatedHttpRequest) -> tuple[int, dict[str, str]] | None:
    """Check if the user is staff, return 403 response if not"""
    if not request.user.is_staff:
        return 403, {"message": "Only staff members can perform this action"}
    return None


@router.get("/", response=list[ElectionSchema], auth=None)
def list_elections(request: HttpRequest) -> list[dict[str, Any]]:
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


@router.get("/{election_id}/", response=ElectionSchema, auth=None)
def get_election(request: HttpRequest, election_id: int) -> dict[str, Any]:
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


@router.get("/{election_id}/candidates/", response=list[CandidateSchema], auth=None)
def list_candidates(request: HttpRequest, election_id: int) -> list[dict[str, Any]]:
    candidates = Candidate.objects.filter(election_id=election_id).select_related("user")
    return [
        {
            "id": candidate.id,
            "election_id": candidate.election_id,
            "user_id": candidate.user_id,
            "bio": candidate.bio,
            "manifesto_link": candidate.manifesto_link,
            "profile_pic_url": candidate.user.player_profile.profile_pic_url,
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
        "manifesto_link": candidate.manifesto_link,
        "profile_pic_url": candidate.user.player_profile.profile_pic_url,
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

    player = request.user.player_profile
    if player.was_minor_on_date(election.end_date.date()):
        try:
            guardian = Guardianship.objects.get(player=player).user
        except Guardianship.DoesNotExist:
            return 400, {
                "message": "Minors cannot vote directly. Only guardians can vote on their behalf. Please ask your guardian to vote on your behalf."
            }

        return 400, {
            "message": f"Minors cannot vote directly. Only guardians can vote on their behalf. Please ask your guardian({guardian.username}) to vote on your behalf."
        }

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

    # Check if user was a minor on the last day of voting and prevent direct voting
    player = request.user.player_profile
    if player.was_minor_on_date(election.end_date.date()):
        return 400, {
            "message": "Minors cannot vote directly. Only guardians can vote on their behalf."
        }

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


@router.post("/{election_id}/vote-for-ward/", response={200: RankedVoteSchema, 400: ErrorSchema})
def cast_ranked_vote_for_ward(
    request: AuthenticatedHttpRequest,
    election_id: int,
    payload: RankedVoteCreateSchema,
    ward_id: int,
) -> RankedVote | tuple[int, dict[str, str]]:
    """Allow guardians to vote on behalf of their minor wards"""
    election = get_object_or_404(Election, id=election_id)

    # Get the ward (minor player)
    try:
        ward = Player.objects.get(id=ward_id)
    except Player.DoesNotExist:
        return 400, {"message": "Ward not found"}

    # Check if the ward was a minor on the last day of voting
    if not ward.was_minor_on_date(election.end_date.date()):
        return 400, {"message": "Only minors can have guardians vote on their behalf"}

    # Check if the current user is the guardian of this ward
    try:
        Guardianship.objects.get(player=ward, user=request.user)
    except Guardianship.DoesNotExist:
        return 400, {"message": "You are not the guardian of this ward"}

    # Check if the ward is eligible to vote in this election
    if not EligibleVoter.objects.filter(election=election, user=ward.user).exists():
        return 400, {"message": "The ward is not eligible to vote in this election"}

    # Verify the ward's verification token
    verification = VoterVerification.objects.filter(
        election=election,
        user=ward.user,
        verification_token=payload.verification_token,
    ).first()
    if not verification:
        return 400, {"message": "Invalid verification token"}

    # Check if the ward has already voted (verification token is already used)
    if verification.is_used:
        return 400, {"message": "The ward has already voted in this election"}

    # Generate a unique voter hash for the ward
    voter_identifier = f"{ward.user.id}:{election_id}:{secrets.token_hex(16)}"
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


@router.get(
    "/{election_id}/my-wards/", response={200: list[WardVoterVerificationSchema], 400: ErrorSchema}
)
def get_my_wards_for_election(
    request: AuthenticatedHttpRequest, election_id: int
) -> list[dict[str, Any]] | tuple[int, dict[str, str]]:
    """Get the current user's wards who are eligible to vote in this election"""
    election = get_object_or_404(Election, id=election_id)

    # Get all wards of the current user who were minors on the last day of voting
    wards = Player.objects.filter(guardianship__user=request.user).select_related("user")

    # Filter wards who were minors on the last day of voting
    eligible_wards = []
    for ward in wards:
        if (
            ward.was_minor_on_date(election.end_date.date())
            and EligibleVoter.objects.filter(election=election, user=ward.user).exists()
        ):
            # Check if the ward is eligible to vote in this election and if the ward has already voted
            verification = VoterVerification.objects.filter(
                election=election, user=ward.user
            ).first()

            if not verification:
                token = VoterVerification.generate_token(election.id, ward.user.id)
                verification = VoterVerification.objects.get(verification_token=token)

            eligible_wards.append(
                {
                    "id": ward.id,
                    "name": ward.user.get_full_name(),
                    "email": ward.user.username,
                    "is_used": verification.is_used,
                    "verification_token": verification.verification_token,
                }
            )

    return eligible_wards


@router.post("/{election_id}/send-notification/", response={200: dict[str, str], 403: ErrorSchema})
def send_election_notification(
    request: AuthenticatedHttpRequest, election_id: int
) -> dict[str, str] | tuple[int, dict[str, str]]:
    """Send email notification to all eligible voters for an election. Only staff can access this endpoint."""
    if error := check_staff(request):
        return error

    election = get_object_or_404(Election, id=election_id)

    # Get all eligible voters
    eligible_voters = EligibleVoter.objects.filter(election=election).select_related("user")
    total_voters = eligible_voters.count()

    if not total_voters:
        return 400, {"message": "No eligible voters found for this election"}

    # Prepare email content
    subject = f"Vote for {election.title}!"

    # Create the election URL
    election_url = f"{settings.EMAIL_INVITATION_BASE_URL}/election/{election.id}"

    # Get candidates for the election
    candidates = Candidate.objects.filter(election=election).select_related("user")
    users = []
    for candidate in candidates:
        users.append(
            {
                "name": candidate.user.get_full_name(),
                "profile_pic_url": candidate.user.player_profile.profile_pic_url,
            }
        )

    # Calculate days remaining for voting
    import pytz
    from django.utils import timezone

    now = timezone.now()
    ist_tz = pytz.timezone("Asia/Kolkata")

    # Convert times to IST for display
    now_ist = now.astimezone(ist_tz)
    start_date_ist = election.start_date.astimezone(ist_tz)
    end_date_ist = election.end_date.astimezone(ist_tz)

    days_remaining = None
    time_remaining = None

    if election.end_date > now:
        delta = election.end_date - now
        days_remaining = delta.days

        # Calculate detailed time remaining
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if days_remaining > 0:
            time_remaining = f"{days_remaining} days, {hours % 24} hours, {minutes} minutes"
        elif hours > 0:
            time_remaining = f"{hours} hours, {minutes} minutes"
        else:
            time_remaining = f"{minutes} minutes"

    # Format times as strings to avoid template timezone issues
    start_date_ist_str = start_date_ist.strftime("%B %d, %Y at %I:%M %p")
    end_date_ist_str = end_date_ist.strftime("%B %d, %Y at %I:%M %p")
    current_time_ist_str = now_ist.strftime("%B %d, %Y at %I:%M %p")

    # HTML version
    html_message = render_to_string(
        "emails/election_notification.html",
        {
            "election": election,
            "election_url": election_url,
            "site_url": settings.EMAIL_INVITATION_BASE_URL,
            "candidates": users,
            "days_remaining": days_remaining,
            "current_time": now_ist,
            "start_date_ist": start_date_ist,
            "end_date_ist": end_date_ist,
            "start_date_ist_str": start_date_ist_str,
            "end_date_ist_str": end_date_ist_str,
            "current_time_ist_str": current_time_ist_str,
            "time_remaining": time_remaining,
        },
    )

    # Plain text version
    plain_message = f"""
Election Notification: {election.title}

{election.description}

Election Details:
- Start Date: {start_date_ist.strftime('%B %d, %Y at %I:%M %p')} IST
- End Date: {end_date_ist.strftime('%B %d, %Y at %I:%M %p')} IST
- Current Time: {now_ist.strftime('%B %d, %Y at %I:%M %p')} IST
{f"- Time Remaining: {time_remaining}" if time_remaining else ""}

Please cast your vote by visiting: {election_url}

This is an automated message from the India Ultimate Hub.
Please do not reply directly to this email.
"""

    # Prepare email messages with HTML support
    email_messages = []
    emails_failed = 0
    failed_emails = []

    for eligible_voter in eligible_voters:
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                to=[eligible_voter.user.email],
            )
            email.attach_alternative(html_message, "text/html")
            email_messages.append(email)
        except Exception as e:
            emails_failed += 1
            failed_emails.append(f"{eligible_voter.user.email}: {e!s}")
            continue

    # Queue the email sending task for background processing
    task_id = f"election_{election_id}_{int(time.time())}"
    try:
        success = queue_emails(email_messages, task_id)
        if not success:
            return 500, {"message": "Failed to queue emails for sending"}
        print(
            f"Queued {len(email_messages)} emails for election {election_id} for background sending"
        )
    except Exception as e:
        return 500, {"message": f"Failed to queue emails for sending: {e!s}"}

    # Return immediate response
    response_message = (
        f"Email notifications queued for sending to {len(email_messages)} eligible voters"
    )

    if emails_failed > 0:
        response_message += f" ({emails_failed} failed to prepare)"

    return {"message": response_message}


@router.get("/{election_id}/vote-count/", response={200: dict[str, Any]}, auth=None)
def get_election_vote_count(request: HttpRequest, election_id: int) -> dict[str, Any]:
    """Get the number of people who have voted in this election"""
    election = get_object_or_404(Election, id=election_id)

    # Count total eligible voters
    total_eligible = EligibleVoter.objects.filter(election=election).count()

    # Count voters who have used their verification token (i.e., have voted)
    total_voted = VoterVerification.objects.filter(election=election, is_used=True).count()

    return {
        "total_eligible": total_eligible,
        "total_voted": total_voted,
        "turnout_percentage": round((total_voted / total_eligible * 100), 1)
        if total_eligible > 0
        else 0,
    }
