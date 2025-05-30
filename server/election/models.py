from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from typing import List, Optional, Any
from server.core.models import User
import secrets
import csv
from io import StringIO

class Election(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Number of winners to select
    num_winners = models.IntegerField(default=1)
    
    # Voting method (IRV or STV)
    VOTING_METHODS = [
        ('IRV', 'Instant Runoff Voting'),
        ('STV', 'Single Transferable Vote'),
    ]
    voting_method = models.CharField(max_length=3, choices=VOTING_METHODS, default='IRV')

    def __str__(self) -> str:
        return self.title

    def import_eligible_voters(self, csv_data: str) -> None:
        """Import eligible voters from CSV data"""
        
        # Parse CSV data
        reader = csv.DictReader(StringIO(csv_data))
        
        # Process each row
        for row in reader:
            email = row.get('email', '').strip().lower()
            if not email:
                continue
                
            try:
                # Find user by email
                user = User.objects.get(email=email)
                
                # Skip if user is already an eligible voter
                if self.eligible_voters.filter(user=user).exists():
                    continue
                
                # Add user as eligible voter
                EligibleVoter.objects.create(
                    election=self,
                    user=user
                )
            except User.DoesNotExist:
                # Skip invalid emails
                continue

class Candidate(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bio = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"{self.user.get_full_name()}"

class RankedVote(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='votes')
    voter_hash = models.CharField(max_length=64)  # Store hashed voter identifier
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"Anonymous vote for {self.election.title} at {self.timestamp}"

    class Meta:
        unique_together = ('election', 'voter_hash')

class RankedVoteChoice(models.Model):
    vote = models.ForeignKey(RankedVote, on_delete=models.CASCADE, related_name='choices')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    rank = models.IntegerField()  # 1 for first choice, 2 for second choice, etc.
    
    def __str__(self) -> str:
        return f"Rank {self.rank} for {self.candidate}"

    class Meta:
        unique_together = ('vote', 'rank')
        ordering = ['rank']

class VoterVerification(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    verification_token = models.CharField(max_length=64, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"Verification for {self.user.email} - {self.election.title}"

    @classmethod
    def generate_token(cls, election_id: int, user_id: int) -> str:
        """Generate a unique verification token for a voter"""
        token = secrets.token_urlsafe(32)
        cls.objects.create(
            election_id=election_id,
            user_id=user_id,
            verification_token=token
        )
        return token
    
    def mark_as_used(self) -> None:
        """Mark this verification token as used"""
        self.is_used = True
        self.save()

    class Meta:
        unique_together = ('election', 'user')

class EligibleVoter(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='eligible_voters')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.election.title}" 

    class Meta:
        unique_together = ('election', 'user')

class ElectionResult(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='results')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    round_number = models.IntegerField()
    votes = models.IntegerField()
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('eliminated', 'Eliminated'),
        ('winner', 'Winner')
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('election', 'candidate', 'round_number')
        ordering = ['round_number', '-votes']

    def __str__(self) -> str:
        return f"{self.candidate} in round {self.round_number} of {self.election}"