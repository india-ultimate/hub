import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { createSignal, Show } from "solid-js";

import { continueGuardianLink, fetchGuardianLink } from "../../queries";

const button =
  "min-h-[44px] w-full rounded-lg bg-blue-700 px-4 py-2 text-base font-semibold text-white hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-2 disabled:opacity-60 sm:w-auto sm:min-w-[200px]";

// Signs the guardian in only on Continue, so an email scanner that opens
// the link changes nothing.
const GuardianLink = () => {
  const params = useParams();
  const link = createQuery(
    () => ["guardian-link", params.token],
    () => fetchGuardianLink(params.token),
    { retry: false, refetchOnWindowFocus: false }
  );
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal("");

  const proceed = async () => {
    setBusy(true);
    setError("");
    try {
      const { redirect } = await continueGuardianLink(params.token);
      history.replaceState(null, "", "/guardian");
      window.location.assign(redirect);
    } catch (err) {
      if (err.status === 404 || err.status === 410) {
        await link.refetch();
      }
      setError(err.message);
      setBusy(false);
    }
  };

  const unusable = () => link.isError || link.data?.valid === false;
  const signInHref = () =>
    link.data?.player_id
      ? `/login?redirect=/waiver/${link.data.player_id}`
      : "/login";

  return (
    <div class="mx-auto max-w-md px-4 py-8 text-gray-900 dark:text-white">
      <Show when={!link.isLoading} fallback={<p role="status">Loading…</p>}>
        <Show
          when={!unusable()}
          fallback={
            <div class="flex flex-col gap-4">
              <h1 class="text-2xl font-bold">Link expired</h1>
              <p>This link has expired or was already used.</p>
              <A
                id="guardian-sign-in"
                href={signInHref()}
                class={`${button} inline-flex items-center justify-center text-center`}
              >
                Sign in with a code
              </A>
            </div>
          }
        >
          <div class="flex flex-col gap-4">
            <h1 class="text-2xl font-bold">
              Sign {link.data.ward_first_name}'s waiver
            </h1>
            <p>
              You're signing in as {link.data.guardian_name} (
              {link.data.guardian_email_masked}), {link.data.ward_first_name}'s
              guardian.
            </p>
            <Show when={link.data.signed_in_name}>
              <p>
                You're signed in as {link.data.signed_in_name}. Continuing signs
                you out and in as {link.data.guardian_name}.
              </p>
            </Show>
            <button
              id="guardian-continue"
              type="button"
              class={button}
              disabled={busy()}
              onClick={proceed}
            >
              {busy() ? "Signing in…" : "Continue"}
            </button>
            <Show when={error()}>
              <p role="alert" class="text-red-700 dark:text-red-400">
                {error()}
              </p>
            </Show>
          </div>
        </Show>
      </Show>
    </div>
  );
};

export default GuardianLink;
