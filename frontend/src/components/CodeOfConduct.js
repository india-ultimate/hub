import { A, useParams } from "@solidjs/router";
import { inboxStack } from "solid-heroicons/solid";
import { createSignal, Match, Show, Switch } from "solid-js";

import text from "../markdowns/code-of-conduct.md";
import { useStore } from "../store";
import { displayDate, getCookie, getPlayer } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import ReasonButton from "./registration/ReasonButton";
import StyledMarkdown from "./StyledMarkdown";

// No class map: the typography plugin's prose styles set a readable
// size, line height and measure for long text on a phone.
const Text = () => (
  <div class="prose max-w-prose text-base leading-relaxed dark:prose-invert">
    <StyledMarkdown markdown={text} classMap={{}} headingIds={false} />
  </div>
);

// This season's Safeguarding Code of Conduct, agreed like the waiver: by an
// adult for themselves, or by a minor's guardian on their behalf.
const CodeOfConduct = () => {
  const params = useParams();
  const [store, { setPlayerById }] = useStore();
  const player = () => getPlayer(store.data, Number(params.playerId));
  const sub = () => player()?.subscription;
  const me = () => store.data?.id;
  const isGuardian = () => player()?.guardian && player().guardian === me();
  const isSelf = () => player()?.user === me() && !player()?.guardian;

  const [ticked, setTicked] = createSignal(false);
  const [saving, setSaving] = createSignal(false);
  const [error, setError] = createSignal("");
  let confirmation;

  const agree = async () => {
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/code-of-conduct", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({ player_id: player().id }),
        credentials: "same-origin"
      });
      const data = await response.json().catch(() => null);
      if (!response.ok)
        throw new Error(data?.message || "Couldn't save that. Try again.");
      setPlayerById(data);
      queueMicrotask(() => confirmation?.focus());
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const label = () =>
    isGuardian()
      ? `I have read this Code of Conduct with ${
          player().full_name
        }, and they understand and agree to follow it. I agree on their behalf.`
      : "I have read, understood and agree to follow this Code of Conduct.";

  return (
    <div class="mx-auto max-w-3xl pb-8">
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Code of conduct" }
        ]}
      />
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
        Code of conduct
      </h1>
      <Switch>
        <Match when={!player()}>
          <p class="mt-2 text-base text-gray-700 dark:text-gray-300">
            Code of conduct for player {params.playerId} isn't available to you.
          </p>
        </Match>
        <Match when={!sub()?.is_active}>
          <p class="mt-2 text-base text-gray-700 dark:text-gray-300">
            Get this season's subscription first.{" "}
            <A
              href={`/subscription/${player().id}`}
              class="font-semibold text-blue-700 underline dark:text-blue-400"
            >
              Get subscription
            </A>
          </p>
        </Match>
        <Match when={sub()?.coc_agreed}>
          <p
            id="coc-agreed"
            tabindex="-1"
            class="mt-3 rounded-lg bg-green-50 p-3 text-base text-green-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-green-600 dark:bg-green-900/30 dark:text-green-100"
          >
            Agreed by {sub().coc_agreed_by} on{" "}
            {displayDate(sub().coc_agreed_at)} for {sub().season_name}.
          </p>
          <details class="mt-4">
            <summary class="inline-flex min-h-[44px] cursor-pointer items-center font-semibold text-blue-700 dark:text-blue-400">
              Show the code of conduct
            </summary>
            <Text />
          </details>
        </Match>
        <Match when={player()?.guardian && !isGuardian()}>
          <p class="mt-2 text-base text-gray-700 dark:text-gray-300">
            Your guardian needs to agree to this for you. They can log in to the
            Hub with their email to do it.
          </p>
        </Match>
        <Match when={isGuardian() || isSelf()}>
          <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
            {[
              sub().season_name,
              `${displayDate(sub().start_date)} – ${displayDate(
                sub().end_date
              )}`,
              player().iu_id && `IU ID ${player().iu_id}`
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p class="mt-3 rounded-lg bg-blue-50 p-3 text-base text-blue-900 dark:bg-blue-900/30 dark:text-blue-100">
            Agree once a season. It covers how you treat others, safety, online
            conduct and, for coaches and captains, extra duties of care.
          </p>
          <div class="mt-4">
            <Text />
          </div>
          <label class="mt-6 flex min-h-[44px] cursor-pointer items-start gap-3 rounded-lg border border-gray-200 p-3 text-base text-gray-900 dark:border-gray-700 dark:text-white">
            <input
              type="checkbox"
              class="mt-1 h-5 w-5 flex-none cursor-pointer rounded border-gray-300 text-blue-700 focus:ring-2 focus:ring-blue-600"
              checked={ticked()}
              onChange={e => setTicked(e.currentTarget.checked)}
            />
            <span>{label()}</span>
          </label>
          <div class="mt-3">
            <ReasonButton
              label="I agree"
              busy={saving()}
              busyLabel="Saving…"
              reason={
                ticked() ? null : { kind: "timing", text: "Tick the box first" }
              }
              onClick={agree}
            />
          </div>
          <Show when={error()}>
            <p role="alert" class="mt-2 text-sm text-red-700 dark:text-red-400">
              {error()}
            </p>
          </Show>
        </Match>
        <Match when={true}>
          <p class="mt-2 text-base text-gray-700 dark:text-gray-300">
            Only {player().full_name} can agree to their code of conduct.
          </p>
        </Match>
      </Switch>
    </div>
  );
};

export default CodeOfConduct;
