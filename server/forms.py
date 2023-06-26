from django import forms
from .models import User, Player, Membership, Vaccination
from .helpers import calculate_startdate_enddate


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

        if not state_ut and not not_in_india:
            self.add_error("state_ut", "Please select a State/UT")
            self.add_error("not_in_india", "Are you not in India? Please select so.")
        elif state_ut and not_in_india:
            self.add_error("state_ut", "State/UT already selected")
            self.add_error("not_in_india", "Are you in India?")

        return cleaned_data


class MembershipForm(forms.ModelForm):
    membership_start, membership_end = calculate_startdate_enddate()

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "readonly": "readonly"}),
        initial=membership_start,
        label="Membership start date",
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "readonly": "readonly"}),
        initial=membership_end,
        label="Membership end date",
    )

    class Meta:
        model = Membership
        fields = [
            "start_date",
            "end_date",
        ]


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

    def clean(self):
        cleaned_data = super().clean()
        is_vaccinated = cleaned_data.get("is_vaccinated")
        explain_not_vaccinated = cleaned_data.get("explain_not_vaccinated")
        vaccination_name = cleaned_data.get("vaccination_name")

        if not is_vaccinated and not explain_not_vaccinated:
            self.add_error("is_vaccinated", "Please check box")
            self.add_error("vaccination_name", "Select you vaccination name")
        elif is_vaccinated and explain_not_vaccinated:
            self.add_error("vaccination_name", "Select your vaccination name")
            self.add_error(
                "explain_not_vaccinated", "No explanation needed if you are vaccinated!"
            )
        elif is_vaccinated and not vaccination_name:
            self.add_error("vaccination_name", "Select vaccination name")

        return cleaned_data
