import { useNavigate, useSearchParams } from "@solidjs/router";
import { createMutation } from "@tanstack/solid-query";
import { createEffect, createSignal, onMount, Show } from "solid-js";

import {
  acceptSeriesInvitationFromEmail,
  declineSeriesInvitationFromEmail
} from "../../queries";

const EmailInvitationHandler = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [token, setToken] = createSignal("");
  const [responseMessage, setResponseMessage] = createSignal("");
  const [setIsAccepting] = createSignal(false);
  const [teamName, setTeamName] = createSignal("");
  const [teamLogo, setTeamLogo] = createSignal("");
  const [fromUser, setFromUser] = createSignal(null);
  const [toPlayer, setToPlayer] = createSignal(null);
  const [countdown, setCountdown] = createSignal(20);
  const [isSuccess, setIsSuccess] = createSignal(false);

  onMount(() => {
    const urlToken = searchParams.token;
    if (urlToken) {
      setToken(urlToken);
      const action = window.location.pathname.includes("invitation/accept")
        ? "accept"
        : "decline";
      setIsAccepting(action === "accept");
      handleInvitation(action);
    } else {
      setResponseMessage("Invalid invitation link. No token found.");
    }
  });

  createEffect(() => {
    const timer = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          clearInterval(timer);
          navigate("/");
          return 0;
        }
        return c - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  });

  const acceptMutation = createMutation({
    mutationFn: acceptSeriesInvitationFromEmail,
    onSuccess: data => {
      setIsSuccess(true);
      setResponseMessage("Invitation accepted successfully");
      setTeamName(data.team.name);
      setTeamLogo(data.team.image ?? data.team.image_url);
      setFromUser(data.from_user);
      setToPlayer(data.to_player);
    },
    onError: error => {
      setIsSuccess(false);
      setResponseMessage(
        error.message || "An error occurred while processing your invitation."
      );
    }
  });

  const declineMutation = createMutation({
    mutationFn: declineSeriesInvitationFromEmail,
    onSuccess: data => {
      setIsSuccess(true);
      setResponseMessage("Invitation declined successfully");
      setTeamName(data.team.name);
      setTeamLogo(data.team.image_url);
      setFromUser(data.from_user);
      setToPlayer(data.to_player);
    },
    onError: error => {
      setIsSuccess(false);
      setResponseMessage(
        error.message || "An error occurred while processing your invitation."
      );
    }
  });

  const handleInvitation = action => {
    if (action === "accept") {
      acceptMutation.mutate({ token: token() });
    } else {
      declineMutation.mutate({ token: token() });
    }
  };

  return (
    <div class="pt-30 flex min-h-screen flex-col items-center bg-gray-100 px-4 py-12 sm:px-6 lg:px-8">
      <div class="w-full max-w-md space-y-8 rounded-xl bg-white p-8 shadow-xl">
        <Show
          when={!acceptMutation.isLoading && !declineMutation.isLoading}
          fallback={
            <p class="text-center text-xl font-semibold text-gray-700">
              Processing your invitation...
            </p>
          }
        >
          <Show
            when={isSuccess()}
            fallback={
              <div class="text-center">
                <p class="mb-4 text-xl font-semibold text-red-600">
                  {responseMessage()}
                </p>
              </div>
            }
          >
            <div class="mb-6 flex items-center space-x-4">
              <img
                src={teamLogo()}
                alt={`${teamName()} logo`}
                class="h-16 w-16 rounded-full object-cover"
              />
              <div>
                <h2 class="text-2xl font-bold text-gray-900">{teamName()}</h2>
                <Show when={fromUser()}>
                  <p class="text-sm text-gray-600">
                    Invitation from: {fromUser().full_name}
                  </p>
                </Show>
                <Show when={toPlayer()}>
                  <p class="text-sm text-gray-600">
                    To: {toPlayer().full_name}
                  </p>
                </Show>
              </div>
            </div>

            <div class="mb-6 rounded-lg bg-gray-50 p-4">
              <p class="mb-2 text-lg font-medium text-gray-900">
                {responseMessage()}
              </p>
            </div>
          </Show>
        </Show>
        <div class="text-center">
          <p class="mb-2 text-gray-600">
            Redirecting to homepage in{" "}
            <span class="font-bold">{countdown()}</span> seconds...
          </p>
          <button
            onClick={() => navigate("/")}
            class="w-full rounded-lg bg-blue-600 px-4 py-2 font-bold text-white transition duration-150 ease-in-out hover:bg-blue-700"
          >
            Go to Homepage
          </button>
        </div>
      </div>
    </div>
  );
};

export default EmailInvitationHandler;
