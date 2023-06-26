from django.shortcuts import redirect, render

from .forms import MembershipForm, PlayerForm, UserForm, VaccinationForm


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
            user = user_form.save(commit=False)
            player = player_form.save(commit=False)
            membership = membership_form.save(commit=False)
            vaccination = vaccination_form.save(commit=False)

            # Ensure unique username for user
            user.username = user.email

            # Connect the objects
            player.user = user
            membership.player = player
            vaccination.player = player

            # Save to database
            user.save()
            player.save()
            membership.save()
            vaccination.save()

            # Get the membership_number
            membership.refresh_from_db()
            membership_number = membership.membership_number

            return redirect("registration_success", membership_number=membership_number)

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


def registration_success_view(request, membership_number):
    context = {
        "membership_number": membership_number,
    }
    return render(request, "success.html", context)
