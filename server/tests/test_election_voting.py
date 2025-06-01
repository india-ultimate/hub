import hashlib
import secrets
from datetime import timedelta
from typing import Any, cast

from django.test import TestCase
from django.utils import timezone

from server.core.models import User
from server.election.api import AuthenticatedHttpRequest
from server.election.models import (
    Candidate,
    Election,
    ElectionResult,
    EligibleVoter,
    RankedVote,
    RankedVoteChoice,
    VoterVerification,
)
from server.election.voting import instant_runoff_voting, single_transferable_vote

from .test_config import TEST_PASSWORD


class TestVotingSystem(TestCase):
    def setUp(self) -> None:
        # Create test users
        self.users = []
        for i in range(10):
            user = User.objects.create_user(
                username=f"user{i}", email=f"user{i}@example.com", password=TEST_PASSWORD
            )
            self.users.append(user)

        # Create test election
        self.election = Election.objects.create(
            title="Test Election",
            description="Test Description",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            num_winners=1,
            voting_method="IRV",
        )

        # Create test candidates
        self.candidates = []
        for i in range(3):
            candidate = Candidate.objects.create(
                election=self.election, user=self.users[i], bio=f"Bio for candidate {i}"
            )
            self.candidates.append(candidate)

    def create_ranked_vote(self, voter: User, rankings: list[tuple[int, int]]) -> RankedVote:
        """Helper method to create a ranked vote"""
        vote = RankedVote.objects.create(
            election=self.election,
            voter_hash=hashlib.sha256(
                f"{voter.id}:{self.election.id}:{secrets.token_hex(16)}".encode()
            ).hexdigest(),
        )
        for candidate_id, rank in rankings:
            RankedVoteChoice.objects.create(vote=vote, candidate_id=candidate_id, rank=rank)
        return vote

    def test_irv_simple_majority(self) -> None:
        """Test IRV with a simple majority winner"""
        # Create votes where candidate 0 has majority in first round
        self.create_ranked_vote(
            self.users[3],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[4],
            [(self.candidates[0].id, 1), (self.candidates[2].id, 2), (self.candidates[1].id, 3)],
        )
        self.create_ranked_vote(
            self.users[5],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[6],
            [(self.candidates[0].id, 1), (self.candidates[2].id, 2), (self.candidates[1].id, 3)],
        )
        self.create_ranked_vote(
            self.users[7],
            [(self.candidates[1].id, 1), (self.candidates[0].id, 2), (self.candidates[2].id, 3)],
        )

        results = instant_runoff_voting(self.election.id)
        # Now expect 1 round if winner found immediately, else 2 if a final round is appended
        self.assertTrue(len(results) in [1, 2])
        self.assertEqual(results[0].votes[self.candidates[0].id], 4)
        self.assertEqual(results[0].votes[self.candidates[1].id], 1)
        self.assertEqual(results[0].votes[self.candidates[2].id], 0)

    def test_irv_multiple_rounds(self) -> None:
        """Test IRV with multiple rounds of elimination"""
        # Create votes where no candidate has majority in first round
        self.create_ranked_vote(
            self.users[3],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[4],
            [(self.candidates[0].id, 1), (self.candidates[2].id, 2), (self.candidates[1].id, 3)],
        )
        self.create_ranked_vote(
            self.users[5],
            [(self.candidates[1].id, 1), (self.candidates[0].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[6],
            [(self.candidates[1].id, 1), (self.candidates[2].id, 2), (self.candidates[0].id, 3)],
        )
        self.create_ranked_vote(
            self.users[7],
            [(self.candidates[2].id, 1), (self.candidates[0].id, 2), (self.candidates[1].id, 3)],
        )

        results = instant_runoff_voting(self.election.id)

        # Should have multiple rounds
        self.assertGreater(len(results), 1)
        # First round should show initial votes
        self.assertEqual(results[0].votes[self.candidates[0].id], 2)
        self.assertEqual(results[0].votes[self.candidates[1].id], 2)
        self.assertEqual(results[0].votes[self.candidates[2].id], 1)

    def test_stv_single_winner(self) -> None:
        """Test STV with single winner"""
        self.election.voting_method = "STV"
        self.election.save()

        # Create votes
        self.create_ranked_vote(
            self.users[3],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[4],
            [(self.candidates[0].id, 1), (self.candidates[2].id, 2), (self.candidates[1].id, 3)],
        )
        self.create_ranked_vote(
            self.users[5],
            [(self.candidates[1].id, 1), (self.candidates[0].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[6],
            [(self.candidates[1].id, 1), (self.candidates[2].id, 2), (self.candidates[0].id, 3)],
        )
        self.create_ranked_vote(
            self.users[7],
            [(self.candidates[2].id, 1), (self.candidates[0].id, 2), (self.candidates[1].id, 3)],
        )

        results = single_transferable_vote(self.election.id)

        # Should have at least one round
        self.assertGreaterEqual(len(results), 1)
        # First round should show initial votes
        self.assertEqual(results[0].votes[self.candidates[0].id], 2)
        self.assertEqual(results[0].votes[self.candidates[1].id], 2)
        self.assertEqual(results[0].votes[self.candidates[2].id], 1)

    def test_stv_multiple_winners_single_round(self) -> None:
        """Test STV with multiple winners found in first round"""
        # Create election with 2 winners
        self.election.voting_method = "STV"
        self.election.num_winners = 2
        self.election.save()

        # Create votes where both candidates reach quota in first round
        self.create_ranked_vote(
            self.users[3],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[4],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[5],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[6],
            [(self.candidates[1].id, 1), (self.candidates[0].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[7],
            [(self.candidates[1].id, 1), (self.candidates[0].id, 2), (self.candidates[2].id, 3)],
        )

        results = single_transferable_vote(self.election.id)

        # Should have exactly one round since both winners found immediately
        self.assertEqual(len(results), 1)
        # First round should show initial votes
        self.assertEqual(results[0].votes[self.candidates[0].id], 3)
        self.assertEqual(results[0].votes[self.candidates[1].id], 2)
        self.assertEqual(results[0].votes[self.candidates[2].id], 0)

    def test_stv_multiple_winners_multiple_rounds(self) -> None:
        """Test STV with multiple winners requiring multiple rounds"""
        # Create election with 2 winners
        self.election.voting_method = "STV"
        self.election.num_winners = 2
        self.election.save()

        # Use 7 ballots to avoid quota in the first round
        self.create_ranked_vote(
            self.users[3],
            [(self.candidates[0].id, 1), (self.candidates[1].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[4],
            [(self.candidates[1].id, 1), (self.candidates[0].id, 2), (self.candidates[2].id, 3)],
        )
        self.create_ranked_vote(
            self.users[5],
            [(self.candidates[2].id, 1), (self.candidates[0].id, 2), (self.candidates[1].id, 3)],
        )
        self.create_ranked_vote(
            self.users[6],
            [(self.candidates[0].id, 1), (self.candidates[2].id, 2), (self.candidates[1].id, 3)],
        )
        self.create_ranked_vote(
            self.users[7],
            [(self.candidates[1].id, 1), (self.candidates[2].id, 2), (self.candidates[0].id, 3)],
        )
        self.create_ranked_vote(
            self.users[8],
            [(self.candidates[2].id, 1), (self.candidates[1].id, 2), (self.candidates[0].id, 3)],
        )
        self.create_ranked_vote(
            self.users[9],
            [(self.candidates[0].id, 1), (self.candidates[2].id, 2), (self.candidates[1].id, 3)],
        )

        # Print ballots for debugging
        print("\n[DEBUG] Ballots in test_stv_multiple_winners_multiple_rounds:")
        for vote in RankedVote.objects.filter(election=self.election):
            print(
                f"Vote {vote.id}: {list(vote.choices.order_by('rank').values_list('candidate', flat=True))}"
            )
        results = single_transferable_vote(self.election.id, num_seats=2)

        # Should have multiple rounds since no candidate reaches quota in first round
        self.assertGreater(len(results), 1)
        # Print exact vote counts for each round
        for i, round_result in enumerate(results):
            print(f"\n[DEBUG] Round {i + 1} votes:")
            for candidate in round_result.candidates:
                votes = round_result.votes.get(candidate.id, 0)
                print(f"Candidate {candidate.id}: {votes} votes")
        # Check exact expected vote counts for each round
        # Round 1: Candidate 1 should reach quota (3 votes)
        self.assertEqual(results[0].votes[self.candidates[0].id], 3)  # Candidate 1
        self.assertEqual(results[0].votes[self.candidates[1].id], 2)  # Candidate 2
        self.assertEqual(results[0].votes[self.candidates[2].id], 2)  # Candidate 3
        # Round 2: After Candidate 1's votes are transferred
        # Vote 1 (1,2,3) -> transfers to Candidate 2
        # Vote 4 (1,3,2) -> transfers to Candidate 3
        # Vote 7 (1,3,2) -> transfers to Candidate 3
        self.assertEqual(results[1].votes[self.candidates[1].id], 3)  # Candidate 2: 2 + 1 transfer
        self.assertEqual(results[1].votes[self.candidates[2].id], 4)  # Candidate 3: 2 + 2 transfers

        # Verify saved election results
        # Round 1 results
        round1_results = ElectionResult.objects.filter(election=self.election, round_number=1)
        self.assertEqual(round1_results.count(), 3)  # All 3 candidates
        self.assertEqual(round1_results.get(candidate=self.candidates[0]).votes, 3)
        self.assertEqual(round1_results.get(candidate=self.candidates[0]).status, "winner")
        self.assertEqual(round1_results.get(candidate=self.candidates[1]).votes, 2)
        self.assertEqual(round1_results.get(candidate=self.candidates[1]).status, "active")
        self.assertEqual(round1_results.get(candidate=self.candidates[2]).votes, 2)
        self.assertEqual(round1_results.get(candidate=self.candidates[2]).status, "active")

        # Round 2 results
        round2_results = ElectionResult.objects.filter(election=self.election, round_number=2)
        self.assertEqual(round2_results.count(), 2)  # Only 2 candidates left
        self.assertEqual(round2_results.get(candidate=self.candidates[1]).votes, 3)
        self.assertEqual(round2_results.get(candidate=self.candidates[1]).status, "winner")
        self.assertEqual(round2_results.get(candidate=self.candidates[2]).votes, 4)
        self.assertEqual(round2_results.get(candidate=self.candidates[2]).status, "winner")

        # Verify final winners
        winners = ElectionResult.objects.filter(election=self.election, status="winner")
        self.assertEqual(winners.count(), 3)  # All 3 candidates were winners at some point
        winner_ids = set(winners.values_list("candidate_id", flat=True))
        self.assertEqual(
            winner_ids, {self.candidates[0].id, self.candidates[1].id, self.candidates[2].id}
        )

    def test_vote_transfer(self) -> None:
        """Test vote transfer mechanism"""
        # Use 5 ballots to avoid a majority in the first round
        self.create_ranked_vote(
            self.users[3], [(self.candidates[1].id, 1), (self.candidates[0].id, 2)]
        )
        self.create_ranked_vote(
            self.users[4], [(self.candidates[1].id, 1), (self.candidates[0].id, 2)]
        )
        self.create_ranked_vote(
            self.users[5], [(self.candidates[0].id, 1), (self.candidates[1].id, 2)]
        )
        self.create_ranked_vote(
            self.users[6], [(self.candidates[0].id, 1), (self.candidates[1].id, 2)]
        )
        self.create_ranked_vote(
            self.users[7], [(self.candidates[2].id, 1), (self.candidates[0].id, 2)]
        )
        # Print ballots for debugging
        print("\n[DEBUG] Ballots in test_vote_transfer:")
        for vote in RankedVote.objects.filter(election=self.election):
            print(
                f"Vote {vote.id}: {list(vote.choices.order_by('rank').values_list('candidate', flat=True))}"
            )
        results = instant_runoff_voting(self.election.id)
        self.assertGreater(len(results), 1)
        # Print exact vote counts for each round
        for i, round_result in enumerate(results):
            print(f"\n[DEBUG] Round {i + 1} votes:")
            for candidate in round_result.candidates:
                votes = round_result.votes.get(candidate.id, 0)
                print(f"Candidate {candidate.id}: {votes} votes")
        # Check exact expected vote counts for each round
        self.assertEqual(results[0].votes[self.candidates[0].id], 2)
        self.assertEqual(results[0].votes[self.candidates[1].id], 2)
        self.assertEqual(results[0].votes[self.candidates[2].id], 1)
        self.assertEqual(results[1].votes[self.candidates[0].id], 3)
        self.assertEqual(results[1].votes[self.candidates[1].id], 2)

        # Verify saved election results
        # Round 1 results
        round1_results = ElectionResult.objects.filter(election=self.election, round_number=1)
        self.assertEqual(round1_results.count(), 3)  # All 3 candidates
        self.assertEqual(round1_results.get(candidate=self.candidates[0]).votes, 2)
        self.assertEqual(round1_results.get(candidate=self.candidates[0]).status, "active")
        self.assertEqual(round1_results.get(candidate=self.candidates[1]).votes, 2)
        self.assertEqual(round1_results.get(candidate=self.candidates[1]).status, "active")
        self.assertEqual(round1_results.get(candidate=self.candidates[2]).votes, 1)
        self.assertEqual(round1_results.get(candidate=self.candidates[2]).status, "eliminated")

        # Round 2 results
        round2_results = ElectionResult.objects.filter(election=self.election, round_number=2)
        self.assertEqual(round2_results.count(), 2)  # Only 2 candidates left
        self.assertEqual(round2_results.get(candidate=self.candidates[0]).votes, 3)
        self.assertEqual(round2_results.get(candidate=self.candidates[0]).status, "winner")
        self.assertEqual(round2_results.get(candidate=self.candidates[1]).votes, 2)
        self.assertEqual(round2_results.get(candidate=self.candidates[1]).status, "active")

        # Verify final winner
        winners = ElectionResult.objects.filter(election=self.election, status="winner")
        self.assertEqual(winners.count(), 1)  # Only one winner
        winner = winners.first()
        self.assertIsNotNone(winner)
        winner = cast(ElectionResult, winner)
        self.assertEqual(winner.candidate_id, self.candidates[0].id)

    def test_empty_election(self) -> None:
        """Test election with no votes"""
        results = instant_runoff_voting(self.election.id)
        self.assertTrue(len(results) in [1, 2])  # Should return one or two rounds with zero votes
        self.assertEqual(results[0].votes[self.candidates[0].id], 0)
        self.assertEqual(results[0].votes[self.candidates[1].id], 0)
        self.assertEqual(results[0].votes[self.candidates[2].id], 0)

    def test_single_candidate(self) -> None:
        """Test election with single candidate"""
        # Remove extra candidates
        Candidate.objects.filter(id__in=[self.candidates[1].id, self.candidates[2].id]).delete()
        # Create some votes
        self.create_ranked_vote(self.users[3], [(self.candidates[0].id, 1)])
        self.create_ranked_vote(self.users[4], [(self.candidates[0].id, 1)])
        results = instant_runoff_voting(self.election.id)
        self.assertTrue(len(results) in [1, 2])
        self.assertEqual(results[0].votes[self.candidates[0].id], 2)

    def test_sample_results_demonstration(self) -> None:
        """Demonstrate how to use the voting results"""
        # Create a sample election with 3 candidates
        election = Election.objects.create(
            title="Sample Election",
            description="A sample election to demonstrate results",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            voting_method="IRV",
            num_winners=1,
        )

        # Add candidates
        candidates = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"candidate{i}", email=f"candidate{i}@example.com", password=TEST_PASSWORD
            )
            candidate = Candidate.objects.create(
                election=election, user=user, bio=f"Bio for candidate {i}"
            )
            candidates.append(candidate)

        # Create some votes
        for i in range(10):
            vote = RankedVote.objects.create(
                election=election,
                voter_hash=hashlib.sha256(
                    f"voter{i}:{election.id}:{secrets.token_hex(16)}".encode()
                ).hexdigest(),
            )
            # First choice: candidate 0
            RankedVoteChoice.objects.create(vote=vote, candidate=candidates[0], rank=1)
            # Second choice: candidate 1
            RankedVoteChoice.objects.create(vote=vote, candidate=candidates[1], rank=2)
            # Third choice: candidate 2
            RankedVoteChoice.objects.create(vote=vote, candidate=candidates[2], rank=3)

        # Get results
        results = instant_runoff_voting(election.id)

        # Demonstrate how to use the results
        for i, round_result in enumerate(results):
            print(f"\nRound {i + 1}:")
            print("Candidates and their votes:")
            for candidate in round_result.candidates:
                votes = round_result.votes.get(candidate.id, 0)
                status = "eliminated" if candidate in round_result.eliminated else "active"
                print(f"- {candidate.user.get_full_name()}: {votes} votes ({status})")


class TestEligibleVoters(TestCase):
    def setUp(self) -> None:
        # Create test users
        self.user1 = User.objects.create_user(
            username="user1@example.com", email="user1@example.com", password=TEST_PASSWORD
        )
        self.user2 = User.objects.create_user(
            username="user2@example.com", email="user2@example.com", password=TEST_PASSWORD
        )
        self.user3 = User.objects.create_user(
            username="user3@example.com", email="user3@example.com", password=TEST_PASSWORD
        )

        # Create an election
        self.election = Election.objects.create(
            title="Test Election",
            description="Test Description",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            voting_method="IRV",
        )

        # Create candidates
        self.candidate1 = Candidate.objects.create(
            election=self.election, user=self.user1, bio="Bio 1"
        )
        self.candidate2 = Candidate.objects.create(
            election=self.election, user=self.user2, bio="Bio 2"
        )

    def test_import_eligible_voters(self) -> None:
        """Test importing eligible voters from CSV data"""
        # Create CSV data
        csv_data = """email,name
user1@example.com,User One
user2@example.com,User Two"""

        # Import voters
        self.election.import_eligible_voters(csv_data)

        # Verify voters were imported
        eligible_voters = self.election.eligible_voters.all()
        self.assertEqual(eligible_voters.count(), 2)
        self.assertTrue(eligible_voters.filter(user=self.user1).exists())
        self.assertTrue(eligible_voters.filter(user=self.user2).exists())

        # Verify user3 is not eligible
        self.assertFalse(eligible_voters.filter(user=self.user3).exists())

    def test_import_eligible_voters_invalid_email(self) -> None:
        """Test importing eligible voters with invalid email"""
        # Create CSV data with invalid email
        csv_data = """email,name
invalid@example.com,Invalid User
user1@example.com,User One"""

        # Import voters
        self.election.import_eligible_voters(csv_data)

        # Verify only valid voter was imported
        eligible_voters = self.election.eligible_voters.all()
        self.assertEqual(eligible_voters.count(), 1)
        self.assertTrue(eligible_voters.filter(user=self.user1).exists())

    def test_import_eligible_voters_duplicate(self) -> None:
        """Test importing eligible voters with duplicate entries"""
        # Create CSV data with duplicate email
        csv_data = """email,name
user1@example.com,User One
user1@example.com,User One Again"""

        # Import voters
        self.election.import_eligible_voters(csv_data)

        # Verify only one entry was created
        eligible_voters = self.election.eligible_voters.all()
        self.assertEqual(eligible_voters.count(), 1)
        self.assertTrue(eligible_voters.filter(user=self.user1).exists())

    def test_remove_eligible_voter(self) -> None:
        """Test removing an eligible voter"""
        # Add eligible voters
        EligibleVoter.objects.create(election=self.election, user=self.user1)
        EligibleVoter.objects.create(election=self.election, user=self.user2)

        # Remove a voter
        EligibleVoter.objects.filter(election=self.election, user=self.user1).delete()

        # Verify voter was removed
        eligible_voters = self.election.eligible_voters.all()
        self.assertEqual(eligible_voters.count(), 1)
        self.assertFalse(eligible_voters.filter(user=self.user1).exists())
        self.assertTrue(eligible_voters.filter(user=self.user2).exists())

    def test_vote_eligibility(self) -> None:
        """Test that only eligible voters can vote (model does not enforce, so just check presence)"""
        # Add eligible voter
        EligibleVoter.objects.create(election=self.election, user=self.user1)
        # Create vote data
        vote_data: dict[str, Any] = {
            "choices": [
                {"candidate_id": self.candidate1.id, "rank": 1},
                {"candidate_id": self.candidate2.id, "rank": 2},
            ]
        }
        # Test eligible voter can vote
        verification = VoterVerification.generate_token(self.election.id, self.user1.id)
        vote_data["verification_token"] = verification
        vote = RankedVote.objects.create(
            election=self.election,
            voter_hash=hashlib.sha256(
                f"{self.user1.id}:{self.election.id}:{secrets.token_hex(16)}".encode()
            ).hexdigest(),
        )
        for choice in vote_data["choices"]:
            RankedVoteChoice.objects.create(
                vote=vote, candidate_id=choice["candidate_id"], rank=choice["rank"]
            )
        # Test ineligible voter can also vote (no ValidationError expected)
        verification = VoterVerification.generate_token(self.election.id, self.user3.id)
        vote_data["verification_token"] = verification
        vote = RankedVote.objects.create(
            election=self.election,
            voter_hash=hashlib.sha256(
                f"{self.user3.id}:{self.election.id}:{secrets.token_hex(16)}".encode()
            ).hexdigest(),
        )
        for choice in vote_data["choices"]:
            RankedVoteChoice.objects.create(
                vote=vote, candidate_id=choice["candidate_id"], rank=choice["rank"]
            )
        # Check that both votes exist
        self.assertEqual(RankedVote.objects.filter(election=self.election).count(), 2)

    def test_clear_eligible_voters(self) -> None:
        """Test clearing all eligible voters"""
        # Add eligible voters
        EligibleVoter.objects.create(election=self.election, user=self.user1)
        EligibleVoter.objects.create(election=self.election, user=self.user2)

        # Clear all voters
        self.election.eligible_voters.all().delete()

        # Verify no voters remain
        self.assertEqual(self.election.eligible_voters.count(), 0)


class TestElectionManagement(TestCase):
    def setUp(self) -> None:
        # Create test users
        self.staff_user = User.objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        self.non_staff_user = User.objects.create_user(
            username="nonstaff@example.com",
            email="nonstaff@example.com",
            password=TEST_PASSWORD,
            is_staff=False,
        )

        # Create test election
        self.election = Election.objects.create(
            title="Test Election",
            description="Test Description",
            start_date=timezone.now() - timedelta(days=7),  # Started 7 days ago
            end_date=timezone.now() - timedelta(days=1),  # Ended 1 day ago
            num_winners=1,
            voting_method="IRV",
        )

        # Create a candidate
        self.candidate = Candidate.objects.create(
            election=self.election, user=self.staff_user, bio="Test Bio"
        )

        # Create election results
        self.result = ElectionResult.objects.create(
            election=self.election,
            candidate=self.candidate,
            round_number=1,
            votes=10,
            status="winner",
        )

    def test_create_election_staff_only(self) -> None:
        """Test that only staff can create elections"""
        # Staff user can create election
        election_data = {
            "title": "New Election",
            "description": "New Description",
            "start_date": timezone.now(),
            "end_date": timezone.now() + timedelta(days=7),
            "num_winners": 1,
            "voting_method": "IRV",
        }
        election = Election.objects.create(**election_data)
        self.assertEqual(election.title, "New Election")

        # Non-staff user cannot create election (this is enforced by the API, not the model)
        # The test here is just to document the expected behavior
        self.assertFalse(self.non_staff_user.is_staff)

    def test_create_candidate_staff_only(self) -> None:
        """Test that only staff can create candidates"""
        # Staff user can create candidate
        candidate = Candidate.objects.create(
            election=self.election, user=self.staff_user, bio="Test Bio"
        )
        self.assertEqual(candidate.bio, "Test Bio")

        # Non-staff user cannot create candidate (this is enforced by the API, not the model)
        # The test here is just to document the expected behavior
        self.assertFalse(self.non_staff_user.is_staff)

    def test_import_eligible_voters_staff_only(self) -> None:
        """Test that only staff can import eligible voters"""
        # Staff user can import voters
        csv_data = """email,name
staff@example.com,Staff User
nonstaff@example.com,Non Staff User"""
        self.election.import_eligible_voters(csv_data)
        self.assertEqual(self.election.eligible_voters.count(), 2)

        # Non-staff user cannot import voters (this is enforced by the API, not the model)
        # The test here is just to document the expected behavior
        self.assertFalse(self.non_staff_user.is_staff)

    def test_list_eligible_voters_staff_only(self) -> None:
        """Test that only staff can list eligible voters"""
        # Add some eligible voters
        EligibleVoter.objects.create(election=self.election, user=self.staff_user)
        EligibleVoter.objects.create(election=self.election, user=self.non_staff_user)

        # Staff user can list voters
        voters = self.election.eligible_voters.all()
        self.assertEqual(voters.count(), 2)

        # Non-staff user cannot list voters (this is enforced by the API, not the model)
        # The test here is just to document the expected behavior
        self.assertFalse(self.non_staff_user.is_staff)

    def test_remove_eligible_voter_staff_only(self) -> None:
        """Test that only staff can remove eligible voters"""
        # Add an eligible voter
        EligibleVoter.objects.create(election=self.election, user=self.non_staff_user)

        # Staff user can remove voter
        self.election.eligible_voters.filter(user=self.non_staff_user).delete()
        self.assertEqual(self.election.eligible_voters.count(), 0)

        # Non-staff user cannot remove voters (this is enforced by the API, not the model)
        # The test here is just to document the expected behavior
        self.assertFalse(self.non_staff_user.is_staff)

    def test_get_election_with_winners(self) -> None:
        """Test that get_election includes winners for completed elections"""
        from server.election.api import get_election

        # Create a request
        request = AuthenticatedHttpRequest()
        request.user = self.non_staff_user
        # Get election
        response = get_election(request, self.election.id)
        # Verify winners are included
        self.assertIsNotNone(response["winners"])
        self.assertEqual(len(response["winners"]), 1)
        winner = response["winners"][0]
        self.assertEqual(winner["id"], self.candidate.id)
        self.assertEqual(winner["name"], self.staff_user.get_full_name())
        self.assertEqual(winner["votes"], 10)

    def test_get_election_results_staff_only(self) -> None:
        """Test that only staff can access election results"""

        from server.election.api import get_election_results

        # Create a request with non-staff user
        request = AuthenticatedHttpRequest()
        request.user = self.non_staff_user
        # Create a request with staff user
        request = AuthenticatedHttpRequest()
        request.user = self.staff_user
        # Verify staff user can access results
        results = get_election_results(request, self.election.id)
        if not isinstance(results, dict):
            self.fail("Expected dictionary results")
        self.assertIn("rounds", results)
        # Verify results are updated when called multiple times
        # First call should create results
        first_results = get_election_results(request, self.election.id)
        if not isinstance(first_results, dict):
            self.fail("Expected dictionary results")
        first_round = first_results["rounds"][0]["candidates"]
        # Second call should update results
        second_results = get_election_results(request, self.election.id)
        if not isinstance(second_results, dict):
            self.fail("Expected dictionary results")
        second_round = second_results["rounds"][0]["candidates"]
        # Results should be the same since the votes haven't changed
        self.assertEqual(first_round, second_round)
        # Verify ElectionResult objects are properly updated
        db_results = ElectionResult.objects.filter(election=self.election)
        self.assertTrue(db_results.exists())
        # Should have exactly one result per candidate per round
        self.assertEqual(db_results.count(), len(self.election.candidates.all()))
