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
  const [countdown, setCountdown] = createSignal(20);

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
    if (!acceptMutation.isLoading && !declineMutation.isLoading) {
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
    }
  });

  const acceptMutation = createMutation({
    mutationFn: acceptSeriesInvitationFromEmail,
    onSuccess: (data) => {
      setResponseMessage(`Invitation accepted successfully for ${data.team.name}`);
      setTeamName(data.team.name);
      setTeamLogo(data.team.image_url);
    },
    onError: (error) => {
      setResponseMessage(error.message);
    }
  });

  const declineMutation = createMutation({
    mutationFn: declineSeriesInvitationFromEmail,
    onSuccess: (data) => {
      setResponseMessage(`Invitation declined successfully for ${data.team.name}`);
    },
    onError: (error) => {
      setResponseMessage(error.message);
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
    <div class="min-h-screen bg-gray-100 flex flex-col items-center pt-40">
      <div class="max-w-md w-full bg-white shadow-md rounded-lg p-8">   
        <Show
          when={!acceptMutation.isLoading && !declineMutation.isLoading}
          fallback={<p>Processing your invitation...</p>}
        >
          <p class="mb-4">{responseMessage()}</p>
          <Show when={teamName()}>
            <div class="mt-4">
              <img src={teamLogo()} alt={`${teamName()} logo`} class="mt-2 w-32 h-32 object-cover" />
            </div>
          </Show>
          <hr class="my-4 border-t border-gray-300" />
          <p class="text-center text-gray-600">
            Redirecting to homepage in {countdown()} seconds...
          </p>
          <hr class="my-4 border-t border-gray-300" />
        </Show>
        <button
          onClick={() => navigate('/')}
          class="mt-4 bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded w-full"
        >
          Go to Homepage
        </button>
      </div>
    </div>
  );
};

export default EmailInvitationHandler;