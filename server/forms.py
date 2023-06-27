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
            "not_in_india",
            "team_name",
            "occupation",
            "educational_institution",
            "india_ultimate_profile",
        ]
        labels = {
            "state_ut": "State/UT",
            "not_in_india": "I'm not in India",
        }

    def clean(self):
        cleaned_data = super().clean()
        state_ut = cleaned_data.get("state_ut")
        not_in_india = cleaned_data.get("not_in_india")

        if (not state_ut and not not_in_india) or (state_ut and not_in_india):
            raise forms.ValidationError(
                "State/UT & 'Not in India' cannot be both checked or cannot be both empty"
            )

        return cleaned_data


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
