import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import {
  checkCircle,
  clock,
  exclamationTriangle
} from "solid-heroicons/outline";
import { createSignal, Show } from "solid-js";

import { relationChoices } from "../../constants";
import { fetchGuardian, resendGuardianLink } from "../../queries";
import { displayDateShort, timeAgo } from "../../utils";
import ReasonButton from "../registration/ReasonButton";
import ChangeGuardian from "./ChangeGuardian";

const tones = {
  done: "text-green-700 dark:text-green-400",
  waiting: "text-gray-700 dark:text-gray-300",
  problem: "text-red-700 dark:text-red-400"
};
const icons = {
  done: checkCircle,
  waiting: clock,
  problem: exclamationTriangle
};

const Line = props => (
  <p class={`flex items-start gap-1.5 text-sm ${tones[props.kind]}`}>
    <Icon
      path={icons[props.kind]}
      class="mt-0.5 h-4 w-4 flex-none"
      aria-hidden="true"
    />
    <span>{props.children}</span>
  </p>
);

const signedLine = (what, step) =>
  step.done
    ? `${what} signed by ${step.by_name} on ${displayDateShort(step.at)}`
    : null;

// A minor's guardian and whether they have signed. Shows nothing to people
// who may not manage the guardian.
const GuardianCard = props => {
  const query = createQuery(
    () => ["guardian", props.playerId],
    () => fetchGuardian(props.playerId),
    { retry: false }
  );
  const [notice, setNotice] = createSignal("");
  const [sending, setSending] = createSignal(false);
  let dialog;

  const resend = async () => {
    setSending(true);
    try {
      setNotice((await resendGuardianLink(props.playerId)).message);
    } catch (e) {
      setNotice(e.message);
    } finally {
      setSending(false);
      query.refetch();
    }
  };

  const d = () => query.data;
  const g = () => d()?.guardian;
  const relation = () =>
    relationChoices.find(c => c.value === g().relation)?.label;
  const open = () => dialog.showModal();

  return (
    <Show when={d()}>
      <section
        id={`guardian-card-${props.playerId}`}
        aria-label="Guardian"
        class="my-4 rounded-lg border border-gray-300 bg-white p-4 dark:border-gray-600 dark:bg-gray-800"
      >
        <h2 class="text-base font-semibold">Guardian</h2>
        <div
          id={`guardian-status-${props.playerId}`}
          class="mt-2 flex flex-col gap-1.5"
        >
          <Show
            when={g()}
            fallback={
              <Line kind="problem">
                No guardian yet. A guardian must sign before you can play.
              </Line>
            }
          >
            <p class="text-base">
              {g().name}
              <Show when={relation()}> · {relation()}</Show>
            </p>
            <p class="break-all text-sm text-gray-600 dark:text-gray-300">
              {g().email}
            </p>
            <Show when={g().is_minor}>
              <Line kind="problem">
                This guardian is under 18. Please change them.
              </Line>
            </Show>
            <Show when={g().is_self}>
              <Line kind="problem">
                You are listed as your own guardian. Please change the guardian.
              </Line>
            </Show>
            <Show
              when={d().waiver.done}
              fallback={
                <Line kind="waiting">
                  Waiting for the guardian to sign ·{" "}
                  {g().link_sent_at
                    ? `link sent ${timeAgo(g().link_sent_at)}`
                    : "no link sent yet"}
                </Line>
              }
            >
              <Line kind="done">{signedLine("Waiver", d().waiver)}</Line>
              <Show
                when={d().coc.done}
                fallback={
                  <Line kind="waiting">Code of conduct not agreed yet</Line>
                }
              >
                <Line kind="done">
                  {signedLine("Code of conduct", d().coc)}
                </Line>
              </Show>
            </Show>
          </Show>
        </div>
        <Show when={notice()}>
          <p
            role="status"
            class="mt-2 text-sm font-semibold text-gray-800 dark:text-gray-100"
          >
            {notice()}
          </p>
        </Show>
        <div class="mt-3 flex flex-wrap gap-2">
          <Show when={g() && d().can_resend}>
            <div id={`guardian-resend-${props.playerId}`}>
              <ReasonButton
                primary={false}
                label={g().link_sent_at ? "Resend link" : "Send link"}
                busy={sending()}
                busyLabel="Sending…"
                onClick={resend}
              />
            </div>
          </Show>
          <Show when={d().can_change}>
            <div id={`guardian-change-${props.playerId}`}>
              <ReasonButton
                primary={!g()}
                label={g() ? "Change guardian" : "Add guardian"}
                onClick={open}
              />
            </div>
          </Show>
        </div>
        <ChangeGuardian
          ref={el => (dialog = el)}
          playerId={props.playerId}
          guardian={g()}
          onSaved={setNotice}
        />
      </section>
    </Show>
  );
};

export default GuardianCard;
