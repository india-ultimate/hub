from django import forms
from .models import User, Player, Membership, Vaccination


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "phone"]


class PlayerForm(forms.ModelForm):
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = Player
        fields = [
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "city",
            "state_ut",
            "team_name",
            "occupation",
            "educational_institution",
            "india_ultimate_profile",
        ]
        labels = {
            "state_ut": "State/UT",
        }


class MembershipForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), initial="2023-04-01"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), initial="2024-03-31"
    )

    class Meta:
        model = Membership
        fields = [
            "start_date",
            "end_date",
        ]
        labels = {
            "start_date": "Membership start date",
            "end_date": "Membership end date",
        }


class VaccinationForm(forms.ModelForm):
    class Meta:
        model = Vaccination
        fields = [
            "is_vaccinated",
            "vaccination_name",
            "vaccination_certificate",
            "explain_not_vaccinated",
        ]
        labels = {
            "vaccination_certificate": "Please upload your vaccination certificate",
            "explain_not_vaccinated": "Explanation for not being vaccinated",
        }
