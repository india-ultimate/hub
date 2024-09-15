import { createMutation } from "@tanstack/solid-query";
import { createSignal, onMount, Show, createEffect } from "solid-js";
import { useNavigate, useSearchParams } from "@solidjs/router";
import { acceptSeriesInvitationFromEmail, declineSeriesInvitationFromEmail } from "../../queries";

const EmailInvitationHandler = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const [token, setToken] = createSignal("");
  const [responseMessage, setResponseMessage] = createSignal("");
  const [isAccepting, setIsAccepting] = createSignal(false);
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
      const action = window.location.pathname.includes('invitation/accept') ? 'accept' : 'decline';
      setIsAccepting(action === 'accept');
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
          navigate('/');
          return 0;
        }
        return c - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  });

  const acceptMutation = createMutation({
    mutationFn: acceptSeriesInvitationFromEmail,
    onSuccess: (data) => {
      setIsSuccess(true);
      setResponseMessage(`Invitation accepted successfully`);
      setTeamName(data.team.name);
      setTeamLogo(data.team.image_url);
      setFromUser(data.from_user);
      setToPlayer(data.to_player);
    },
    onError: (error) => {
      setIsSuccess(false);
      setResponseMessage(error.message || "An error occurred while processing your invitation.");
    }
  });

  const declineMutation = createMutation({
    mutationFn: declineSeriesInvitationFromEmail,
    onSuccess: (data) => {
      setIsSuccess(true);
      setResponseMessage(`Invitation declined successfully`);
      setTeamName(data.team.name);
      setTeamLogo(data.team.image_url);
      setFromUser(data.from_user);
      setToPlayer(data.to_player);
    },
    onError: (error) => {
      setIsSuccess(false);
      setResponseMessage(error.message || "An error occurred while processing your invitation.");
    }
  });

  const handleInvitation = (action) => {
    if (action === 'accept') {
      acceptMutation.mutate({ token: token() });
    } else {
      declineMutation.mutate({ token: token() });
    }
  };

  return (
    <div class="min-h-screen bg-gray-100 flex flex-col items-center pt-30 py-12 px-4 sm:px-6 lg:px-8">
      <div class="max-w-md w-full space-y-8 bg-white shadow-xl rounded-xl p-8">
        <Show
          when={!acceptMutation.isLoading && !declineMutation.isLoading}
          fallback={<p class="text-center text-xl font-semibold text-gray-700">Processing your invitation...</p>}
        >
          <Show
            when={isSuccess()}
            fallback={
              <div class="text-center">
                <p class="text-xl font-semibold text-red-600 mb-4">{responseMessage()}</p>
              </div>
            }
          >
            <div class="flex items-center space-x-4 mb-6">
              <img src={teamLogo()} alt={`${teamName()} logo`} class="w-16 h-16 object-cover rounded-full" />
              <div>
                <h2 class="text-2xl font-bold text-gray-900">{teamName()}</h2>
                <Show when={fromUser()}>
                  <p class="text-sm text-gray-600">Invitation from: {fromUser().full_name}</p>
                </Show>
                <Show when={toPlayer()}>
                <p class="text-sm text-gray-600">To: {toPlayer().full_name}</p>
                </Show>
              </div>
            </div>
            
            <div class="bg-gray-50 rounded-lg p-4 mb-6">
              <p class="text-lg font-medium text-gray-900 mb-2">{responseMessage()}</p>
            </div>
          </Show>
        </Show>
        <div class="text-center">
          <p class="text-gray-600 mb-2">
            Redirecting to homepage in <span class="font-bold">{countdown()}</span> seconds...
          </p>
          <button
            onClick={() => navigate('/')}
            class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition duration-150 ease-in-out"
          >
            Go to Homepage
          </button>
        </div>
      </div>
    </div>
  );
};

export default EmailInvitationHandler;