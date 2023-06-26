from django.shortcuts import render, redirect
from .forms import UserForm, PlayerForm, MembershipForm, VaccinationForm
from .models import User


def home(request):
    return render(request, "index.html")


def registration_view(request):
    if request.method == "POST":
        user_form = UserForm(request.POST)
        player_form = PlayerForm(request.POST)
        membership_form = MembershipForm(request.POST)
        vaccination_form = VaccinationForm(request.POST)

        if (
            user_form.is_valid()
            and player_form.is_valid()
            and membership_form.is_valid()
            and vaccination_form.is_valid()
        ):
            user = user_form.save()
            player = player_form.save()
            membership = membership_form.save()
            vaccination = vaccination_form.save()
            return redirect("registration_success")

    else:
        user_form = UserForm()
        player_form = PlayerForm()
        membership_form = MembershipForm()
        vaccination_form = VaccinationForm()

    context = {
        "user_form": user_form,
        "player_form": player_form,
        "membership_form": membership_form,
        "vaccination_form": vaccination_form,
    }

    return render(request, "registration.html", context)


def registration_success_view(request):
    return render(request, "success.html")
