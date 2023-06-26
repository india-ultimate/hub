from django import forms
from .models import User, Player, Membership, Vaccination

GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'phone']


class PlayerForm(forms.ModelForm):
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type' : 'date'}))
    gender = forms.ChoiceField(choices=GENDER_CHOICES)
    other_gender = forms.CharField(required=False, max_length=20)

    class Meta:
        model = Player
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'other_gender','city', 'state_ut', 'team_name',
                  'occupation', 'educational_institution', 'india_ultimate_profile']
        labels = {
            'state_ut' : 'State/UT',
        }

    def clean(self):
        cleaned_data = super().clean()
        gender = cleaned_data.get('gender')
        other_gender = cleaned_data.get('other_gender')

        if gender == 'other' and not other_gender:
            self.add_error('other_gender', 'Please specify the gender.')

        return cleaned_data


class MembershipForm(forms.ModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type' : 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type' : 'date'}))
    class Meta:
        model = Membership
        fields = ['membership_number', 'is_annual', 'start_date', 'end_date', 'is_active']
        labels = {
            'is_annual' : 'Is Annual membership',
            'start_date' : 'Membership start date',
            'end_date' : 'Membership end date',
            'is_active' : 'Membership currently active'
        }


class VaccinationForm(forms.ModelForm):
    class Meta:
        model = Vaccination
        fields = ['is_vaccinated', 'vaccination_name', 'vaccination_certificate', 'explain_not_vaccinated']
        label = {
            'vaccination_certificate': 'Please upload your vaccination certificate',
            'explain_not_vaccinated': 'Explanation for not being vaccinated',
        }
