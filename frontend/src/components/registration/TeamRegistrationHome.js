import { useNavigate, useParams } from "@solidjs/router";
import { createQuery, useQueryClient } from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { check, trophy } from "solid-heroicons/solid";
import {
  createEffect,
  createSignal,
  For,
  Index,
  Match,
  on,
  onCleanup,
  Show,
  Switch
} from "solid-js";

import { inr } from "../../money";
import {
  addRosterEntry,
  addTeamRegistration,
  addTeamSeriesRegistration,
  checkoutRoster,
  fetchRegistrationStatus,
  fetchTournamentBySlug,
  removeRosterEntry,
  resendRosterInvite
} from "../../queries";
import { openCheckout } from "../../razorpay";
import { useStore } from "../../store";
import { getCookie, latestDate, parseLocalDate, todayIST } from "../../utils";
import Breadcrumbs from "../Breadcrumbs";
import Modal from "../Modal";
import AddPlayersDialog from "./AddPlayersDialog";
import Callout from "./Callout";
import PayBar from "./PayBar";
import ReasonButton from "./ReasonButton";
import RosterMeter from "./RosterMeter";
import RosterRow from "./RosterRow";
import Step from "./Step";
import SwapDialog from "./SwapDialog";

const NOT_PAID = "Payment cancelled. You weren't charged.";
const UNAVAILABLE = "Payments aren't working right now. You weren't charged.";
const CONFIRMING = "Confirming payment. Don't pay again.";
// The team fee step offers the rest once part of the fee is paid.
const isPartPaid = fee => fee?.callout?.action?.op === "pay_team_rest";
const TEAM_FEE_OPS = ["pay_team", "pay_team_partial", "pay_team_rest"];
const POLL_MS = 3000;
const POLL_FOR_MS = 2 * 60 * 1000;

const tryAgain =
  "ml-1 inline-flex min-h-[44px] items-center font-semibold underline focus:outline-none focus-visible:ring-2 focus-visible:ring-red-600 dark:focus-visible:ring-red-400";
const errorText = "text-sm text-red-700 dark:text-red-400";

const shortDate = day =>
  day.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
const DAY_MS = 24 * 60 * 60 * 1000;

// "21–23 Oct", "21 Oct", or "30 Oct – 2 Nov".
const dateRange = (start, end) => {
  const s = new Date(start);
  const e = new Date(end);
  const dm = d =>
    d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      timeZone: "UTC"
    });
  if (start === end) return dm(s);
  if (s.getUTCMonth() === e.getUTCMonth()) return `${s.getUTCDate()}–${dm(e)}`;
  return `${dm(s)} – ${dm(e)}`;
};

// The one deadline worth a line: a late fee starting within a week, else
// when rostering closes. A late fee starts the day after the end date.
const nextDeadline = (event, steps) => {
  const today = todayIST();
  const feeDone = steps.find(s => s.key === "team_fee")?.state === "done";
  const late = [
    !feeDone && [
      "Team",
      event.team_registration_end_date,
      event.team_late_penalty_end_date,
      event.team_late_penalty
    ],
    [
      "Player",
      event.player_registration_end_date,
      event.player_late_penalty_end_date,
      event.player_late_penalty
    ]
  ]
    .filter(
      c =>
        c &&
        c[3] > 0 &&
        c[1] &&
        c[2] &&
        parseLocalDate(c[2]) > parseLocalDate(c[1]) &&
        parseLocalDate(c[1]) >= today
    )
    .map(([who, end]) => {
      const from = parseLocalDate(end);
      from.setDate(from.getDate() + 1);
      return { who, from, days: Math.round((from - today) / DAY_MS) };
    })
    .sort((a, b) => a.from - b.from)[0];
  if (late && late.days <= 7)
    return `${late.who} late fee from ${shortDate(late.from)}`;
  const closes = latestDate(
    event.player_late_penalty_end_date,
    event.player_registration_end_date
  );
  if (Number.isNaN(closes)) return null;
  return `Rostering ${closes >= today ? "closes" : "closed"} ${shortDate(
    new Date(closes)
  )}`;
};

// The older team endpoints throw the JSON body as the message.
const messageOf = error => {
  try {
    return JSON.parse(error.message).message || error.message;
  } catch {
    return error.message;
  }
};

// A team-fee order, the same one the old register page made.
const teamOrder = async body => {
  const response = await fetch("/api/transactions/razorpay", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify(body),
    credentials: "same-origin"
  });
  const data = await response.json().catch(() => null);
  if (response.ok) return data;
  throw new Error((response.status < 500 && data?.message) || UNAVAILABLE);
};

// One team's registration for one tournament: the steps, the roster, and
// one payment for every ready player.
const TeamRegistrationHome = () => {
  const params = useParams();
  const navigate = useNavigate();
  const [store] = useStore();
  const queryClient = useQueryClient();
  const args = () => ({ eventSlug: params.slug, teamSlug: params.team_slug });

  // The one place state changes are announced.
  const [notice, setNotice] = createSignal({ text: "", tone: "info" });
  const announce = (text, tone = "info") => setNotice({ text, tone });
  const [paying, setPaying] = createSignal(false);
  // What a payment is waiting on: { kind, done(), message }.
  const [confirming, setConfirming] = createSignal(null);
  const [changed, setChanged] = createSignal(null); // a 409's body
  const [busy, setBusy] = createSignal(null);
  const [opError, setOpError] = createSignal(null);
  let changedRef;
  const [addOpen, setAddOpen] = createSignal(false);
  let addDialog;
  let addOpener;
  let swapDialog;
  let swapOpener;
  let poll;

  const status = createQuery(
    () => ["registration", args()],
    () => fetchRegistrationStatus(args()),
    // Always fresh: people come back from paying elsewhere (a subscription
    // handoff) and must see what changed, not the app-wide 60 s cache.
    {
      retry: false,
      staleTime: 0,
      refetchOnMount: "always",
      refetchOnWindowFocus: true
    }
  );
  const d = () => status.data;
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["registration"] });
  const readOnly = () => d().viewer !== "admin";

  // Payment: after Razorpay says paid, ask again every 3 s until the paid
  // payment reads done (its players, or the team fee), for up to 2 minutes.
  const stopConfirming = () => {
    clearInterval(poll);
    setConfirming(null);
  };
  const startConfirming = check => {
    setPaying(false);
    setConfirming(check);
    announce(CONFIRMING);
    const started = Date.now();
    clearInterval(poll);
    poll = setInterval(() => {
      if (Date.now() - started < POLL_FOR_MS) return refresh();
      stopConfirming();
      announce(
        "Still confirming. Don't pay again; check back in a few minutes.",
        "error"
      );
    }, POLL_MS);
  };
  onCleanup(() => clearInterval(poll));

  createEffect(() => {
    const check = confirming();
    if (check && d() && check.done()) {
      stopConfirming();
      announce(check.message, "success");
    }
  });
  const playersPaid = ids => ({
    kind: "players",
    done: () => {
      const done = new Set(
        d()
          .roster.entries.filter(e => e.state.kind === "done")
          .map(e => e.player.id)
      );
      return ids.every(id => done.has(id));
    },
    message: `Paid. ${ids.length} ${
      ids.length === 1 ? "player" : "players"
    } rostered.`
  });
  const teamFeePaid = partial => ({
    kind: "team",
    done: () => {
      const fee = d().steps.find(s => s.key === "team_fee");
      return fee?.state === "done" || (partial && isPartPaid(fee));
    },
    message: partial ? "Part of the team fee paid." : "Team fee paid."
  });

  // Another team: nothing from this one carries over.
  createEffect(
    on(
      () => params.team_slug,
      () => {
        stopConfirming();
        setPaying(false);
        setOpError(null);
        announce("");
      },
      { defer: true }
    )
  );

  const notPaid = () => {
    if (confirming()) return; // paid; the callback failing doesn't undo it
    setPaying(false);
    announce(NOT_PAID, "error");
    refresh();
  };

  const pay = async () => {
    const c = d().checkout;
    const ids = [...c.ready_ids];
    setPaying(true);
    announce("");
    try {
      if (!window.Razorpay) throw new Error(UNAVAILABLE);
      const order = await checkoutRoster({
        ...args(),
        expectedAmount: c.amount,
        expectedIds: ids
      });
      openCheckout(order, {
        onPaid: () => startConfirming(playersPaid(ids)),
        onSuccess: refresh,
        onFailure: notPaid,
        onDismiss: notPaid,
        onUnconfirmed: announce
      });
    } catch (error) {
      setPaying(false);
      if (error.status === 409) {
        setChanged(error.body);
        announce("The total changed. Check it before you pay.");
        changedRef.showModal();
      } else {
        announce(
          error.status && error.status < 500 ? error.message : UNAVAILABLE,
          "error"
        );
      }
      refresh();
    }
  };

  const payNewTotal = async () => {
    changedRef.close();
    await status.refetch();
    pay();
  };

  const payTeam = async partial => {
    if (!window.Razorpay) throw new Error(UNAVAILABLE);
    const order = await teamOrder({
      team_id: d().team.id,
      event_id: d().event.id,
      partial
    });
    openCheckout(order, {
      onPaid: () => startConfirming(teamFeePaid(partial)),
      onSuccess: refreshTeam,
      onFailure: notPaid,
      onDismiss: notPaid,
      onUnconfirmed: announce
    });
  };

  const tournament = () =>
    queryClient.fetchQuery({
      queryKey: ["tournaments", params.slug],
      queryFn: () => fetchTournamentBySlug(params.slug)
    });
  const refreshTeam = () => {
    queryClient.invalidateQueries({ queryKey: ["tournaments", params.slug] });
    refresh();
  };

  const entryOp = fn => playerId => fn({ ...args(), playerId });
  const OPS = {
    remove: entryOp(removeRosterEntry),
    resend_invite: entryOp(resendRosterInvite),
    invite: entryOp(addRosterEntry),
    roster: entryOp(addRosterEntry),
    pay_team: () => payTeam(false),
    pay_team_partial: () => payTeam(true),
    pay_team_rest: () => payTeam(false),
    register_free: async () => {
      const t = await tournament();
      await addTeamRegistration({
        tournament_id: t.id,
        body: { team_id: d().team.id }
      }).catch(e => {
        throw new Error(messageOf(e));
      });
    },
    register_series: async () => {
      const t = await tournament();
      await addTeamSeriesRegistration({
        series_slug: t.event.series.slug,
        body: { team_slug: d().team.slug }
      });
    }
  };

  const keyOf = (op, playerId) => (playerId ? `${op}:${playerId}` : op);
  const runOp = async (op, playerId) => {
    const key = keyOf(op, playerId);
    setBusy(key);
    setOpError(null);
    try {
      await OPS[op](playerId);
    } catch (error) {
      setOpError({ key, op, playerId, message: error.message });
    } finally {
      setBusy(null);
      refreshTeam();
    }
  };

  // Only controls this page can carry out; "remind" has no endpoint yet,
  // so its reason shows without a button.
  const shown = action =>
    action && !readOnly() && (action.href || OPS[action.op]) ? action : null;
  const withAction = entry => ({
    ...entry,
    state: { ...entry.state, action: shown(entry.state.action) }
  });
  const withActions = callout => ({
    ...callout,
    action: shown(callout.action),
    secondary_action: shown(callout.secondary_action)
  });

  const OpError = props => (
    <Show when={props.when}>
      <p role="alert" class={errorText}>
        {opError().message}
        <button
          type="button"
          class={tryAgain}
          onClick={() => runOp(opError().op, opError().playerId)}
        >
          Try again
        </button>
      </p>
    </Show>
  );

  const payReason = () => {
    const callout = d().steps.find(s => s.key === "roster")?.callout;
    if (callout?.kind === "blocked")
      return { kind: "blocked", text: callout.text };
    if (d().checkout.ready_ids.length) return null;
    const waiting = d().roster.entries.filter(
      e => e.state.kind === "waiting"
    ).length;
    if (waiting)
      return {
        kind: "waiting",
        text: `Waiting on ${waiting} ${waiting === 1 ? "player" : "players"}`
      };
    // Players on the list, none ready (say, a subscription to buy): the
    // step's callout says what to do, so the button only says why it's grey.
    return unpaidRows().length
      ? { kind: "timing", text: "No players ready yet" }
      : { kind: "timing", text: "Add players first" };
  };

  const nameOf = playerId =>
    d()?.roster.entries.find(e => e.player.id === playerId)?.player.name ||
    "A player";

  const adminTeams = () => store.data?.admin_teams || [];

  // Paid players apart; mid-payment rows first among the rest.
  const paidRows = () =>
    d().roster.entries.filter(e => e.state.kind === "done");
  const unpaidRows = () =>
    d()
      .roster.entries.filter(e => e.state.kind !== "done")
      .sort(
        (a, b) => (b.state.kind === "progress") - (a.state.kind === "progress")
      );
  const removeReason = entry =>
    entry.state.kind === "progress"
      ? "Being paid for. Try again in a few minutes."
      : entry.state.code === "timing.closed"
      ? entry.state.text
      : null;
  // How many rows share each name; only then do rows show city and IU ID.
  const shared = () => {
    const counts = {};
    for (const e of d().roster.entries)
      counts[e.player.name] = (counts[e.player.name] || 0) + 1;
    return counts;
  };
  const free = () => !d().checkout.per_player;

  // Swaps are open from when rostering opens until it closes.
  const swapUntil = () =>
    latestDate(
      d().event.player_late_penalty_end_date,
      d().event.player_registration_end_date
    );
  const swapReason = () => {
    const today = todayIST();
    if (today < parseLocalDate(d().event.player_registration_start_date))
      return "Rostering hasn't opened yet";
    if (today > swapUntil())
      return `Swaps closed ${shortDate(new Date(swapUntil()))}`;
    return null;
  };

  // Removing asks first, and says when it also withdraws a series invite.
  const [removing, setRemoving] = createSignal(null); // the entry to confirm
  let removeRef;
  const askRemove = player => {
    setRemoving(d().roster.entries.find(e => e.player.id === player.id));
    removeRef.showModal();
  };
  const confirmRemove = async () => {
    const entry = removing();
    removeRef.close();
    await runOp("remove", entry.player.id);
    if (opError()) return;
    announce(`Removed ${entry.player.name}`);
    // The row is gone; land keyboard users on its list, not the page.
    document.getElementById("unpaid-heading")?.focus();
  };
  const invitePending = entry => entry?.state.code === "waiting.invite";

  return (
    // Bottom padding so the phone's fixed pay bar never covers the page.
    <div class="mx-auto max-w-3xl pb-32 pt-2 sm:pb-8">
      <Switch>
        <Match when={d()}>
          <Breadcrumbs
            icon={trophy}
            pageList={[
              { url: "/tournaments", name: "All Tournaments" },
              { url: `/tournament/${d().event.slug}`, name: d().event.title },
              { name: d().team.name }
            ]}
          />
          <div class="flex flex-wrap items-end justify-between gap-3">
            <div class="min-w-0">
              <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
                {d().team.name}
              </h1>
              <p class="text-sm text-gray-600 dark:text-gray-400">
                {[
                  dateRange(d().event.start_date, d().event.end_date),
                  nextDeadline(d().event, d().steps)
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <Show when={!readOnly() && adminTeams().length > 1}>
              <div>
                <label
                  for="registration-team-switcher"
                  class="block text-xs font-medium text-gray-600 dark:text-gray-400"
                >
                  Your teams
                </label>
                <select
                  id="registration-team-switcher"
                  class="min-h-[44px] rounded-lg border border-gray-300 bg-gray-50 px-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  onChange={e =>
                    navigate(
                      `/tournament/${params.slug}/team/${e.currentTarget.value}/registration`
                    )
                  }
                >
                  <For each={adminTeams()}>
                    {team => (
                      <option
                        value={team.slug}
                        selected={team.slug === d().team.slug}
                      >
                        {team.name}
                      </option>
                    )}
                  </For>
                </select>
              </div>
            </Show>
          </div>

          <Show when={readOnly()}>
            <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
              View only
            </p>
          </Show>

          <Show when={d().steps.some(s => s.state === "done")}>
            <ul
              aria-label="Done"
              class="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-green-800 dark:text-green-300"
            >
              <For each={d().steps.filter(s => s.state === "done")}>
                {s => (
                  <li class="inline-flex items-center gap-1">
                    <Icon path={check} class="h-4 w-4" aria-hidden="true" />
                    {s.title}
                  </li>
                )}
              </For>
            </ul>
          </Show>
          <Show when={d().all_set}>
            <p class="mt-3 rounded-lg bg-green-50 p-3 text-sm text-green-900 dark:bg-green-900/30 dark:text-green-100">
              <b>You're all set.</b> {paidRows().length}{" "}
              {paidRows().length === 1 ? "player" : "players"}{" "}
              {free() ? "rostered" : "paid"}.
              <Show when={!swapReason() && !Number.isNaN(swapUntil())}>
                {" "}
                You can still add or swap players until{" "}
                {shortDate(new Date(swapUntil()))}.
              </Show>
            </p>
          </Show>

          <div
            role="status"
            aria-live="polite"
            class={clsx(
              notice().text && "mt-3 rounded-lg p-3 text-sm",
              notice().text &&
                {
                  info: "bg-blue-50 text-blue-900 dark:bg-blue-900/30 dark:text-blue-100",
                  success:
                    "bg-green-50 text-green-900 dark:bg-green-900/30 dark:text-green-100",
                  error:
                    "bg-red-50 text-red-900 dark:bg-red-900/30 dark:text-red-100"
                }[notice().tone]
            )}
          >
            {notice().text}
          </div>
          <Show when={status.isError}>
            <p role="alert" class={clsx("mt-3", errorText)}>
              Couldn't refresh this page.
              <button type="button" class={tryAgain} onClick={refresh}>
                Try again
              </button>
            </p>
          </Show>

          {/* Index, not For: each refetch brings new step objects, and the
              roster step must stay mounted across them. */}
          <div class="mt-3">
            <Index each={d().steps}>
              {(step, i) => (
                <Show when={step().state !== "done" || step().key === "roster"}>
                  <Step
                    step={step()}
                    index={i + 1}
                    meta={
                      step().key === "roster" && (
                        <RosterMeter
                          meter={d().roster.meter}
                          hasSeries={Boolean(d().event.series)}
                        />
                      )
                    }
                    aside={
                      step().key === "roster" &&
                      !readOnly() && (
                        <button
                          type="button"
                          ref={addOpener}
                          class="inline-flex min-h-[44px] flex-none items-center rounded-lg border border-blue-700 px-3 text-sm font-semibold text-blue-700 hover:bg-blue-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:border-blue-400 dark:text-blue-400 dark:hover:bg-gray-700"
                          onClick={() => {
                            setAddOpen(true);
                            addDialog.showModal();
                          }}
                        >
                          + Add players
                        </button>
                      )
                    }
                  >
                    {step().key === "roster" ? (
                      <>
                        <Show when={step().callout}>
                          <Callout callout={withActions(step().callout)} />
                        </Show>
                        <section aria-labelledby="unpaid-heading">
                          <h3
                            id="unpaid-heading"
                            tabindex="-1"
                            class="mb-1 text-xs font-bold uppercase tracking-wide text-gray-700 dark:text-gray-300"
                          >
                            {free() ? "Not rostered" : "Not paid"}{" "}
                            <span class="font-semibold normal-case tracking-normal text-gray-600 dark:text-gray-400">
                              · {unpaidRows().length}
                            </span>
                          </h3>
                          <Show
                            when={unpaidRows().length}
                            fallback={
                              <p class="text-sm text-gray-600 dark:text-gray-400">
                                No players yet
                              </p>
                            }
                          >
                            <ul
                              aria-label={free() ? "Not rostered" : "Not paid"}
                              class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700"
                            >
                              <For each={unpaidRows()}>
                                {entry => (
                                  <>
                                    <RosterRow
                                      entry={withAction(entry)}
                                      readOnly={readOnly()}
                                      showDetail={
                                        shared()[entry.player.name] > 1
                                      }
                                      busy={
                                        busy() ===
                                        keyOf(
                                          entry.state.action?.op,
                                          entry.player.id
                                        )
                                      }
                                      onOp={runOp}
                                      removeReason={removeReason(entry)}
                                      removing={
                                        busy() ===
                                        keyOf("remove", entry.player.id)
                                      }
                                      onRemove={askRemove}
                                    />
                                    <Show
                                      when={
                                        opError()?.playerId === entry.player.id
                                      }
                                    >
                                      <li class="px-2 py-1">
                                        <OpError when={true} />
                                      </li>
                                    </Show>
                                  </>
                                )}
                              </For>
                            </ul>
                          </Show>
                        </section>
                        <Show when={paidRows().length}>
                          <section aria-labelledby="paid-heading" class="mt-4">
                            <div class="mb-1 flex items-center justify-between gap-2">
                              <h3
                                id="paid-heading"
                                class="text-xs font-bold uppercase tracking-wide text-green-800 dark:text-green-300"
                              >
                                {free() ? "Rostered" : "Paid"}{" "}
                                <span class="font-semibold normal-case tracking-normal text-gray-600 dark:text-gray-400">
                                  · {paidRows().length}
                                </span>
                              </h3>
                              <Show when={!readOnly()}>
                                <ReasonButton
                                  ref={swapOpener}
                                  link
                                  label="Swap a player"
                                  reason={
                                    swapReason()
                                      ? { kind: "timing", text: swapReason() }
                                      : null
                                  }
                                  onClick={() => swapDialog.showModal()}
                                />
                              </Show>
                            </div>
                            <ul
                              aria-label={free() ? "Rostered" : "Paid"}
                              class="overflow-hidden rounded-lg border border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/40"
                            >
                              <For each={paidRows()}>
                                {entry => (
                                  <RosterRow
                                    entry={entry}
                                    paid
                                    readOnly
                                    showDetail={shared()[entry.player.name] > 1}
                                  />
                                )}
                              </For>
                            </ul>
                          </section>
                        </Show>
                        <Show
                          when={
                            !readOnly() &&
                            d().checkout.per_player > 0 &&
                            step().state !== "locked" &&
                            unpaidRows().length > 0
                          }
                        >
                          <PayBar
                            checkout={d().checkout}
                            busy={paying() || confirming()?.kind === "players"}
                            busyLabel={
                              paying()
                                ? "Opening payment…"
                                : "Confirming payment…"
                            }
                            disabledReason={payReason()}
                            onPay={pay}
                          />
                        </Show>
                      </>
                    ) : step().callout ? (
                      <>
                        <Callout
                          callout={withActions(step().callout)}
                          busyOp={
                            confirming()?.kind === "team"
                              ? TEAM_FEE_OPS
                              : busy()
                          }
                          onOp={op => runOp(op)}
                        />
                        <OpError
                          when={
                            opError() &&
                            !opError().playerId &&
                            [
                              step().callout.action?.op,
                              step().callout.secondary_action?.op
                            ].includes(opError().op)
                          }
                        />
                      </>
                    ) : undefined}
                  </Step>
                </Show>
              )}
            </Index>
          </div>
        </Match>
        <Match when={status.error?.status === 404}>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
            Not found
          </h1>
          <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
            There's no such team registration, or it isn't one you can see.
          </p>
        </Match>
        <Match when={status.isError}>
          <p role="alert" class={errorText}>
            The registration could not be loaded.
            <button type="button" class={tryAgain} onClick={refresh}>
              Try again
            </button>
          </p>
        </Match>
        <Match when={true}>
          <p class="text-sm text-gray-600 dark:text-gray-400">Loading…</p>
        </Match>
      </Switch>

      <Show when={d() && !readOnly()}>
        <AddPlayersDialog
          setRef={el => {
            addDialog = el;
            el.addEventListener("close", () => {
              setAddOpen(false);
              addOpener?.focus();
            });
          }}
          open={addOpen()}
          teamName={d().team.name}
          series={d().event.series}
          meter={d().roster.meter}
          args={args()}
          onChanged={refresh}
          announce={announce}
        />
        <SwapDialog
          setRef={el => {
            swapDialog = el;
            el.addEventListener("close", () => swapOpener?.focus());
          }}
          paid={paidRows()}
          unpaid={unpaidRows()}
          until={
            Number.isNaN(swapUntil()) ? null : shortDate(new Date(swapUntil()))
          }
          args={args()}
          onChanged={refresh}
          announce={announce}
        />
      </Show>

      <Modal
        ref={changedRef}
        title={
          <span class="font-semibold text-gray-900 dark:text-white">
            The total changed
          </span>
        }
        close={() => changedRef.close()}
      >
        <Show when={changed()}>
          <Show when={changed().removed.length}>
            <p class="text-sm">No longer in this payment:</p>
            <ul class="mb-2 list-inside list-disc text-sm">
              <For each={changed().removed}>
                {r => (
                  <li>
                    {nameOf(r.player_id)}
                    {r.reason ? ` — ${r.reason}` : ""}
                  </li>
                )}
              </For>
            </ul>
          </Show>
          <p class="text-base font-semibold tabular-nums">
            {inr(changed().old_amount)} → {inr(changed().new_amount)}
          </p>
          <div class="mt-4 flex flex-wrap justify-end gap-2">
            <ReasonButton
              primary={false}
              label="Cancel"
              onClick={() => changedRef.close()}
            />
            <ReasonButton
              label={`Pay ${inr(changed().new_amount)}`}
              onClick={payNewTotal}
            />
          </div>
        </Show>
      </Modal>

      <Modal
        ref={removeRef}
        title={
          <span class="font-semibold text-gray-900 dark:text-white">
            Remove {removing()?.player.name}?
          </span>
        }
        close={() => removeRef.close()}
      >
        <p class="text-sm">
          {invitePending(removing())
            ? "This also withdraws their series invite."
            : "They'll come off this team's list."}
        </p>
        <div class="mt-4 flex flex-wrap justify-end gap-2">
          <ReasonButton
            primary={false}
            label="Cancel"
            onClick={() => removeRef.close()}
          />
          <button
            type="button"
            class="inline-flex min-h-[44px] items-center rounded-lg bg-red-700 px-4 text-sm font-semibold text-white hover:bg-red-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-600"
            onClick={confirmRemove}
          >
            Remove
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default TeamRegistrationHome;
