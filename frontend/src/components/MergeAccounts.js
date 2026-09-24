import { useParams, useSearchParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import { getCookie } from "../utils";
import Modal from "./Modal";

const fetchCluster = async token => {
  const response = await fetch(`/api/merge-accounts/${token}`, {
    credentials: "same-origin"
  });
  if (!response.ok) throw new Error("This link is not valid any more");
  return response.json();
};

const post = async (path, body) => {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data?.message || "Something went wrong");
    error.reason = data?.reason;
    throw error;
  }
  return data;
};

const FIELD_LABELS = {
  first_name: "First name",
  last_name: "Last name",
  phone: "Phone",
  date_of_birth: "Date of birth",
  gender: "Gender",
  match_up: "Match up",
  other_gender: "Gender (self-described)",
  city: "City",
  state_ut: "State / UT",
  occupation: "Occupation",
  educational_institution: "Institution",
  profile_pic_url: "Profile picture",
  not_in_india: "Living outside India"
};

// ponytail: codes like gender show raw. Add a display map if people ask.
const fieldLabel = field =>
  FIELD_LABELS[field] ||
  field.replace(/_/g, " ").replace(/^./, c => c.toUpperCase());

const isBlank = value => value === null || value === undefined || value === "";

/** Fields where two of the chosen accounts hold different answers. A blank
 *  against a value is not a disagreement - the merge already takes the one
 *  that is filled in. */
const conflictsBetween = members => {
  const withProfile = members.filter(m => m && m.profile);
  if (withProfile.length < 2) return [];

  const fields = new Set(withProfile.flatMap(m => Object.keys(m.profile)));
  const found = [];

  for (const field of fields) {
    const options = [];
    for (const member of withProfile) {
      const value = member.profile[field];
      if (isBlank(value)) continue;
      const seen = options.find(o => String(o.value) === String(value));
      if (seen) seen.members.push(member);
      else options.push({ value, members: [member] });
    }
    if (options.length > 1) found.push({ field, options });
  }

  return found.sort((a, b) => a.field.localeCompare(b.field));
};

const STATE_WORDS = {
  open: "Not confirmed",
  verified: "Confirmed",
  "pending-staff": "With our team",
  rejected: "Our team couldn't confirm it",
  merged: "Merged",
  "merged-elsewhere": "Merged elsewhere",
  gone: "Account deleted"
};

const stateWords = row => {
  if (row.is_yours) return "You keep this one";
  if (row.state === "merged" && row.merged_into_you) return "Merged into yours";
  return STATE_WORDS[row.state] || row.state;
};

const since = row =>
  row.since ? new Date(row.since).toLocaleDateString() : "";

// Why a row confirmed itself (spec §3): a row can turn Confirmed on page
// load just by sharing an inbox with the keeper, which is correct but
// unexplained without this.
const PROOF_WORDS = {
  "same-inbox": "same inbox",
  "email-code": "code",
  staff: "our team"
};

const proofReason = row =>
  row.state === "verified" ? PROOF_WORDS[row.proof] : undefined;

function Row(props) {
  const [code, setCode] = createSignal("");
  const [note, setNote] = createSignal("");
  const [asking, setAsking] = createSignal(false);
  const [picked, setPicked] = createSignal({});
  const [blocked, setBlocked] = createSignal(false);
  const [modalError, setModalError] = createSignal("");
  let modalRef;

  const row = () => props.row;
  const canAct = () => props.canAct && !row().is_yours;
  const actionable = () =>
    canAct() && ["open", "rejected", "pending-staff"].includes(row().state);

  const conflicts = () => conflictsBetween([props.you, row()]);
  const defaultFor = conflict => {
    const mine = conflict.options.find(o => o.members.some(m => m.is_yours));
    return String((mine || conflict.options[0]).value);
  };
  const selectionFor = c => picked()[c.field] ?? defaultFor(c);
  // A choice is always one of the two accounts' own values (design: no
  // free-text "something else" - they can edit their profile afterwards).
  const valueFor = c => {
    const option = c.options.find(o => String(o.value) === selectionFor(c));
    return option ? option.value : c.options[0].value;
  };
  // A blank answer is left out entirely; the server refuses one anyway.
  const resolved = () =>
    Object.fromEntries(
      conflicts()
        .map(c => [c.field, valueFor(c)])
        .filter(([, value]) => !isBlank(value))
    );

  const act = (path, body) =>
    props.act(path, { user_id: row().user_id, ...body });

  const openConfirm = () => {
    setModalError("");
    modalRef.showModal();
  };

  // Always confirms through the dialog, even with nothing to pick between
  // (owner decision) - an irreversible action gets a confirmation either way.
  // A failure here is the modal's own to show - silent skips the page-level
  // error, so nothing is left behind once the dialog closes, however it closes.
  const doMerge = async () => {
    setModalError("");
    const failure = await props.act(
      "confirm",
      { absorb_user_id: row().user_id, resolved: resolved() },
      { silent: true }
    );
    if (!failure) {
      modalRef.close();
      return;
    }
    if (failure.reason === "blocked") setBlocked(true);
    setModalError(failure.message);
  };

  return (
    <tr id={`merge-row-${row().row_id}`} class="border-b dark:border-gray-700">
      <td class="py-3 pr-3 font-mono text-sm text-gray-900 dark:text-white">
        {row().email}
        <Show when={row().last_seen}>
          <span class="block text-xs text-gray-500 dark:text-gray-400">
            last signed in {row().last_seen}
          </span>
        </Show>
      </td>
      <td class="py-3 pr-3 text-sm">
        <span id={`merge-state-${row().row_id}`} data-state={row().state}>
          {stateWords(row())}
        </span>
        <Show when={proofReason(row())}>
          <span
            id={`merge-proof-${row().row_id}`}
            class="block text-xs text-gray-500 dark:text-gray-400"
          >
            {proofReason(row())}
          </span>
        </Show>
        <Show when={since(row())}>
          <span class="block text-xs text-gray-500 dark:text-gray-400">
            {since(row())}
          </span>
        </Show>

        <Show when={actionable()}>
          <div class="mt-2 space-y-2">
            <button
              id={`merge-send-code-${row().row_id}`}
              disabled={props.busy}
              onClick={() => act("code")}
              class="inline-flex min-h-[44px] items-center rounded bg-blue-700 px-3 py-1 text-xs text-white disabled:opacity-50"
            >
              Send code
            </button>
            <div class="flex items-end gap-2">
              <label class="block text-xs text-gray-700 dark:text-gray-300">
                6-digit code
                <input
                  id={`merge-code-${row().row_id}`}
                  inputmode="numeric"
                  placeholder="6-digit code"
                  class="mt-1 w-32 rounded border border-gray-300 p-1 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  value={code()}
                  onInput={e => setCode(e.currentTarget.value)}
                />
              </label>
              <button
                id={`merge-verify-${row().row_id}`}
                disabled={props.busy || !code().trim()}
                onClick={() => act("verify", { code: code() })}
                class="inline-flex min-h-[44px] items-center rounded border border-blue-700 px-3 py-1 text-xs text-blue-700 disabled:opacity-50 dark:text-blue-300"
              >
                Confirm
              </button>
            </div>
            <Show when={row().state !== "pending-staff"}>
              <button
                id={`merge-staff-open-${row().row_id}`}
                onClick={() => setAsking(!asking())}
                class="inline-flex min-h-[44px] items-center text-xs text-gray-600 underline dark:text-gray-300"
              >
                I can&apos;t reach this inbox
              </button>
              <Show when={asking()}>
                <label class="block text-xs text-gray-700 dark:text-gray-300">
                  Why can&apos;t you reach it?
                  <textarea
                    id={`merge-staff-note-${row().row_id}`}
                    class="mt-1 block w-full rounded border border-gray-300 p-1 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    value={note()}
                    onInput={e => setNote(e.currentTarget.value)}
                  />
                </label>
                <button
                  id={`merge-staff-send-${row().row_id}`}
                  disabled={props.busy}
                  onClick={() => act("staff", { note: note() })}
                  class="inline-flex min-h-[44px] items-center rounded bg-gray-700 px-3 py-1 text-xs text-white disabled:opacity-50"
                >
                  Ask our team
                </button>
              </Show>
            </Show>
          </div>
        </Show>

        <Show when={canAct() && row().verified_for_you}>
          <button
            id={`merge-confirm-${row().row_id}`}
            disabled={props.busy}
            onClick={openConfirm}
            aria-label={`Merge ${row().email} into your account`}
            class="mt-2 inline-flex min-h-[44px] items-center rounded bg-green-700 px-3 py-1 text-xs text-white focus:outline-none focus:ring-4 focus:ring-green-300 disabled:opacity-50 dark:focus:ring-green-800"
          >
            Merge
          </button>
          <Modal
            ref={modalRef}
            title="Confirm merge"
            close={() => modalRef.close()}
          >
            <p class="text-sm text-gray-700 dark:text-gray-300">
              Merging <span class="font-medium">{row().email}</span> into your
              account.
            </p>
            <Show when={conflicts().length > 0}>
              <div class="mt-3">
                <p class="mb-1 text-xs text-gray-700 dark:text-gray-300">
                  These differ. Pick what&apos;s right:
                </p>
                <For each={conflicts()}>
                  {conflict => (
                    <fieldset
                      id={`merge-field-${row().row_id}-${conflict.field}`}
                      class="mb-2 rounded border border-gray-200 p-2 dark:border-gray-700"
                    >
                      <legend class="px-1 text-xs font-medium">
                        {fieldLabel(conflict.field)}
                      </legend>
                      <For each={conflict.options}>
                        {(option, index) => (
                          <label class="flex min-h-[44px] cursor-pointer items-center gap-2 rounded p-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700">
                            <input
                              type="radio"
                              id={`merge-option-${row().row_id}-${
                                conflict.field
                              }-${index()}`}
                              name={`merge-field-${row().row_id}-${
                                conflict.field
                              }`}
                              class="h-5 w-5 shrink-0 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-2"
                              checked={
                                selectionFor(conflict) === String(option.value)
                              }
                              onChange={() =>
                                setPicked({
                                  ...picked(),
                                  [conflict.field]: String(option.value)
                                })
                              }
                            />
                            {String(option.value)}
                          </label>
                        )}
                      </For>
                    </fieldset>
                  )}
                </For>
              </div>
            </Show>
            <p class="mt-3 text-sm font-medium text-gray-700 dark:text-gray-300">
              This can&apos;t be undone.
            </p>
            <Show when={modalError()}>
              <p
                id={`merge-modal-error-${row().row_id}`}
                role="alert"
                class="mt-2 text-sm text-red-600 dark:text-red-400"
              >
                {modalError()}
              </p>
            </Show>
            <div class="mt-4 flex justify-end gap-2">
              <button
                id={`merge-modal-cancel-${row().row_id}`}
                type="button"
                onClick={() => modalRef.close()}
                class="min-h-[44px] rounded-lg border border-gray-200 bg-white px-5 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-gray-500 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-600"
              >
                Cancel
              </button>
              <button
                id={`merge-modal-confirm-${row().row_id}`}
                type="button"
                disabled={props.busy}
                onClick={doMerge}
                class="min-h-[44px] rounded-lg bg-red-700 px-5 text-sm font-medium text-white hover:bg-red-800 focus:outline-none focus:ring-4 focus:ring-red-300 disabled:opacity-50 dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-800"
              >
                Merge
              </button>
            </div>
          </Modal>
        </Show>

        <Show when={canAct() && row().verified_for_you && blocked()}>
          <div class="mt-2 space-y-2">
            <p class="text-xs text-gray-700 dark:text-gray-300">
              If they really are both yours, our team can check and correct the
              details, then merge them.
            </p>
            <label class="block text-xs text-gray-700 dark:text-gray-300">
              Tell our team why these are both yours
              <textarea
                id={`merge-blocked-note-${row().row_id}`}
                class="mt-1 block w-full rounded border border-gray-300 p-1 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                value={note()}
                onInput={e => setNote(e.currentTarget.value)}
              />
            </label>
            <button
              id={`merge-blocked-send-${row().row_id}`}
              disabled={props.busy}
              onClick={() => act("staff", { note: note() })}
              class="inline-flex min-h-[44px] items-center rounded bg-gray-700 px-3 py-1 text-xs text-white disabled:opacity-50"
            >
              Ask our team to review
            </button>
          </div>
        </Show>
      </td>
    </tr>
  );
}

export default function MergeAccounts() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const [error, setError] = createSignal();
  const [notice, setNotice] = createSignal();
  const [busy, setBusy] = createSignal(false);
  // The email's old dismiss link opens the confirmation, never acts on load.
  const [confirmingDismiss, setConfirmingDismiss] = createSignal(
    Boolean(searchParams.dismiss)
  );

  const query = createQuery(
    () => ["merge-cluster", params.token],
    () => fetchCluster(params.token)
  );

  const data = () => query.data;
  const signedIn = () => data()?.signed_in_as != null;
  const you = () => (data()?.rows || []).find(r => r.is_yours);
  const finished = () =>
    data()?.status === "Resolved" || data()?.status === "Dismissed";

  const act = async (action, body, { silent } = {}) => {
    setBusy(true);
    setError();
    setNotice();
    let failure;
    try {
      const result = await post(
        `/api/merge-accounts/${params.token}/${action}`,
        body
      );
      if (result?.message) setNotice(result.message);
      await query.refetch();
    } catch (e) {
      if (!silent) setError(e.message);
      failure = e;
    }
    setBusy(false);
    return failure;
  };

  // Signed in to none of these accounts: sign out and come back through
  // the login, which returns here.
  const signOut = async () => {
    try {
      await post("/api/logout");
      window.location = `/login?redirect=${encodeURIComponent(
        `/merge-accounts/${params.token}`
      )}`;
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div class="mx-auto max-w-3xl px-4 py-8">
      <h1 class="mb-2 text-2xl font-bold text-gray-900 dark:text-white">
        Merge your accounts
      </h1>

      <Show when={query.isLoading}>
        <p class="text-gray-500">Loading…</p>
      </Show>
      <Show when={query.isError}>
        <p id="merge-link-invalid" class="text-red-600 dark:text-red-400">
          This link is not valid any more.
        </p>
      </Show>

      <Show when={query.isSuccess}>
        <Show when={!finished()}>
          <p id="merge-intro" class="mb-4 text-gray-700 dark:text-gray-300">
            {data().is_requester
              ? "You asked to merge these accounts."
              : data().origin === "requested"
              ? "Someone asked to merge these accounts."
              : "These accounts look like yours."}
          </p>
        </Show>

        <Show when={finished() && data().rows.length === 0}>
          <p id="merge-finished" class="text-gray-700 dark:text-gray-300">
            {data().status === "Dismissed"
              ? "Someone in this group said these aren't the same person."
              : data().anything_merged
              ? "These accounts were merged."
              : "These accounts were sorted out."}
          </p>
        </Show>
        <Show when={data().status === "Dismissed" && data().rows.length > 0}>
          <p id="merge-finished" class="mb-2 text-gray-700 dark:text-gray-300">
            {data().cancelled_by_you
              ? "You cancelled this merge request."
              : "Someone in this group said these aren't the same person."}
          </p>
        </Show>
        <Show
          when={
            data().status === "Resolved" &&
            data().rows.some(row => row.state === "merged")
          }
        >
          <p id="merge-finished" class="mb-2 text-gray-700 dark:text-gray-300">
            These accounts were merged.
          </p>
        </Show>

        <Show when={data().signed_in_elsewhere && !finished()}>
          <div id="merge-wrong-account" class="mb-4">
            <p class="mb-2 text-gray-700 dark:text-gray-300">
              You&apos;re signed in as {data().signed_in_elsewhere} — not one of
              these accounts.
            </p>
            <button
              id="merge-sign-out"
              onClick={signOut}
              class="min-h-[44px] rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            >
              Sign out
            </button>
          </div>
        </Show>

        <Show when={!signedIn() && !data().signed_in_elsewhere && !finished()}>
          <div
            id="merge-sign-in-prompt"
            class="mb-4 rounded-lg border border-gray-200 p-6 text-center dark:border-gray-700"
          >
            <a
              id="merge-login-link"
              href={`/login?redirect=${encodeURIComponent(
                `/merge-accounts/${params.token}`
              )}`}
              class="inline-block min-h-[44px] rounded-lg bg-blue-700 px-8 py-2.5 text-base font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            >
              Sign in
            </a>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
              You&apos;ll come back here.
            </p>
          </div>
        </Show>

        <Show when={data().rows.length > 0}>
          <table id="merge-table" class="mb-4 w-full text-left">
            <thead>
              <tr class="border-b text-xs uppercase text-gray-500 dark:border-gray-700">
                <th class="py-2 pr-3">Account</th>
                <th class="py-2 pr-3">Status</th>
              </tr>
            </thead>
            <tbody>
              <For each={data().rows}>
                {row => (
                  <Row
                    row={row}
                    you={you()}
                    canAct={data().can_act}
                    busy={busy()}
                    act={act}
                  />
                )}
              </For>
            </tbody>
          </table>
        </Show>

        <Show when={signedIn() && !finished() && !data().can_act}>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            This link has expired. You can still see where things stand.
          </p>
        </Show>

        <Show when={signedIn() && !finished()}>
          <Show
            when={confirmingDismiss()}
            fallback={
              <button
                id="merge-dismiss-button"
                onClick={() => setConfirmingDismiss(true)}
                class="mt-2 inline-flex min-h-[44px] items-center text-sm text-gray-500 underline dark:text-gray-400"
              >
                {data().is_requester
                  ? "Cancel this request"
                  : "These aren't the same person"}
              </button>
            }
          >
            <div class="mt-2 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
              <p class="mb-2 text-sm text-gray-700 dark:text-gray-300">
                {data().is_requester
                  ? "Cancel this merge request?"
                  : "End this for everyone? We won't ask again."}
              </p>
              <button
                id="merge-dismiss-confirm"
                disabled={busy()}
                onClick={() => act("dismiss")}
                class="inline-flex min-h-[44px] items-center rounded bg-red-700 px-3 py-1 text-sm text-white disabled:opacity-50"
              >
                Yes
              </button>
            </div>
          </Show>
        </Show>
      </Show>

      <Show when={notice()}>
        <p id="merge-notice" class="mt-4 text-green-700 dark:text-green-400">
          {notice()}
        </p>
      </Show>
      <Show when={error()}>
        <p
          id="merge-error"
          role="alert"
          class="mt-4 text-red-600 dark:text-red-400"
        >
          {error()}
        </p>
      </Show>
    </div>
  );
}
