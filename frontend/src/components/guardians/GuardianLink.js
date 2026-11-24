import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { exclamationTriangle } from "solid-heroicons/outline";
import { createSignal, Show } from "solid-js";

import { continueGuardianLink, fetchGuardianLink } from "../../queries";
import { Bar, Loading } from "../../skeletons/primitives";

const button =
  "min-h-[44px] w-full rounded-lg bg-blue-700 px-4 py-2 text-base font-semibold text-white hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-2 disabled:opacity-60 sm:w-auto sm:min-w-[200px]";

// Signs the guardian (or an adult player) in only on Continue, so an email
// scanner that opens the link changes nothing.
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
      setError(
        [403, 404, 410].includes(err.status)
          ? err.message
          : "Something went wrong. Please try again."
      );
      setBusy(false);
    }
  };

  const unusable = () => link.isError || link.data?.valid === false;
  const signInHref = () =>
    link.data?.player_id
      ? `/login?redirect=/waiver/${link.data.player_id}`
      : "/login";

  const waiverDue = () => link.data.to_sign.includes("waiver");
  const ownTitle = () =>
    waiverDue() ? "Sign your waiver" : "Agree to the code of conduct";
  const ownTask = () =>
    waiverDue() ? "sign your waiver" : "agree to the code of conduct";

  const guardianFirst = () => link.data.guardian_name?.split(" ")[0] || "there";

  return (
    <div class="mx-auto max-w-md px-4 py-8 text-gray-900 dark:text-white">
      <Show
        when={!link.isLoading}
        fallback={
          <Loading label="Loading your link">
            <Bar class="h-8 w-56" />
            <Bar class="mt-5 h-24 w-full !rounded-lg" />
          </Loading>
        }
      >
        <Show
          when={!unusable()}
          fallback={
            <div class="flex flex-col gap-4">
              <Show
                when={link.data?.for_self}
                fallback={
                  <>
                    <h1 class="text-2xl font-bold">
                      This link is no longer working
                    </h1>
                    <p>
                      It may be older than 7 days, or a newer link was sent.
                      Open the latest email from India Ultimate, or get a code
                      by email to sign in.
                    </p>
                  </>
                }
              >
                <h1 class="text-2xl font-bold">
                  This link has already been used or has expired
                </h1>
                <p>
                  Open the Hub and sign in with your email. We will send you a
                  code.
                </p>
              </Show>
              <Show when={link.data?.guardian_email_masked}>
                <p class="text-sm text-gray-700 dark:text-gray-300">
                  Use the email address that{" "}
                  {link.data.for_self
                    ? `starts with ${link.data.guardian_email_masked[0]}, like`
                    : "looks like"}{" "}
                  {link.data.guardian_email_masked}.
                </p>
              </Show>
              <A
                id="guardian-sign-in"
                href={signInHref()}
                class={`${button} inline-flex items-center justify-center text-center`}
              >
                Sign in with an email code
              </A>
            </div>
          }
        >
          <div class="flex flex-col gap-4">
            <Show
              when={!link.data.for_self}
              fallback={
                <>
                  <h1 class="text-2xl font-bold">{ownTitle()}</h1>
                  <p>
                    Hi {guardianFirst()}, Continue to sign in and {ownTask()}.
                    You do not need a password.
                  </p>
                </>
              }
            >
              <h1 class="text-2xl font-bold">
                Hi {guardianFirst()}, {link.data.ward_first_name} needs you to{" "}
                {waiverDue()
                  ? "sign their waiver"
                  : "agree to their code of conduct"}
              </h1>
              <p>
                You are {link.data.ward_first_name}'s guardian. Tap Continue to
                read and {waiverDue() ? "sign" : "agree"}.
              </p>
            </Show>
            <Show when={link.data.signed_in_name}>
              <p>
                This device is signed in as {link.data.signed_in_name}.
                Continuing will sign them out and sign you in as{" "}
                {link.data.guardian_name}.
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
              <p
                role="alert"
                class="flex items-start gap-1.5 text-red-700 dark:text-red-400"
              >
                <Icon
                  path={exclamationTriangle}
                  class="mt-1 h-4 w-4 flex-none"
                  aria-hidden="true"
                />
                <span>{error()}</span>
              </p>
            </Show>
            <Show when={!link.data.for_self}>
              <p class="text-sm text-gray-700 dark:text-gray-300">
                Link sent to {link.data.guardian_email_masked}
              </p>
            </Show>
          </div>
        </Show>
      </Show>
    </div>
  );
};

export default GuardianLink;
