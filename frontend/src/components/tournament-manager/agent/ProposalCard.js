import { createSignal, For, Show } from "solid-js";

import { Spinner } from "../../../icons";

const TOOL_TITLES = {
  propose_create_pool: "Create pool",
  propose_create_swiss_round: "Create Swiss round",
  propose_create_cross_pool: "Create cross pool",
  propose_create_cross_pool_matches: "Create cross pool matches",
  propose_create_bracket: "Create bracket",
  propose_create_position_pool: "Create position pool",
  propose_create_field: "Add field",
  propose_update_seeding: "Update seeding",
  propose_update_match: "Update match",
  propose_delete_match: "Delete match",
  propose_bulk_schedule: "Schedule matches",
  propose_recommended_schedule: "Schedule matches",
  propose_full_setup: "Full tournament setup",
  propose_start_tournament: "Start tournament"
};

/** Destructive/irreversible proposals get a heavier confirm treatment. */
const HIGH_IMPACT = new Set([
  "propose_delete_match",
  "propose_start_tournament",
  "propose_update_seeding"
]);

const Field = props => (
  <div class="flex gap-2 text-xs">
    <span
      class="w-20 shrink-0"
      style={{ color: "var(--agent-ink-muted)" }}
    >
      {props.label}
    </span>
    <span class="min-w-0 flex-1" style={{ color: "var(--agent-ink)" }}>
      {props.children}
    </span>
  </div>
);

const SeedList = props => (
  <div class="flex flex-wrap gap-1">
    <For each={props.seeds || []}>
      {seed => (
        <span
          class="rounded px-1.5 py-0.5 text-[11px] font-medium tabular-nums"
          style={{
            "background-color": "var(--agent-user-chip)",
            color: "var(--agent-ink)"
          }}
          title={props.teamName?.(seed)}
        >
          {seed}
          <Show when={props.teamName?.(seed)}>
            <span class="ml-1 font-normal opacity-70">
              {props.teamName(seed)}
            </span>
          </Show>
        </span>
      )}
    </For>
  </div>
);

/**
 * Human preview of a proposal payload, per tool. Falls back to the raw JSON
 * disclosure for shapes without a bespoke view - staff should be able to check
 * what they are confirming without reading JSON.
 */
const ProposalPreview = props => {
  const p = () => props.proposal.payload || {};
  const tool = () => props.proposal.tool_name;
  const teamName = seed => props.seedToTeamName?.(seed);

  return (
    <div class="space-y-1.5">
      <Show when={tool() === "propose_create_pool"}>
        <Field label="Pool">{p().name}</Field>
        <Field label="Seeds">
          <SeedList seeds={p().seeding} teamName={teamName} />
        </Field>
      </Show>

      <Show when={tool() === "propose_create_swiss_round"}>
        <Field label="Group">{p().name}</Field>
        <Field label="Rounds">{p().num_rounds}</Field>
        <Field label="Seeds">
          <SeedList seeds={p().seeding} teamName={teamName} />
        </Field>
      </Show>

      <Show when={tool() === "propose_create_bracket"}>
        <Field label="Bracket">{p().name}</Field>
        <Field label="Covers">
          Seeds {String(p().name || "").replace("-", " through ")}
        </Field>
      </Show>

      <Show when={tool() === "propose_create_position_pool"}>
        <Field label="Pool">{p().name}</Field>
        <Field label="Seeds">
          <SeedList seeds={p().seeding} teamName={teamName} />
        </Field>
      </Show>

      <Show when={tool() === "propose_create_field"}>
        <Field label="Name">{p().name}</Field>
        <Show when={p().address}>
          <Field label="Address">{p().address}</Field>
        </Show>
        <Field label="Broadcast">{p().is_broadcasted ? "Yes" : "No"}</Field>
      </Show>

      <Show when={tool() === "propose_create_cross_pool_matches"}>
        <Field label="Matches">{(p().seed_pairs || []).length}</Field>
        <div class="space-y-1">
          <For each={p().seed_pairs || []}>
            {pair => (
              <div
                class="flex items-center gap-1.5 text-xs"
                style={{ color: "var(--agent-ink)" }}
              >
                <span class="tabular-nums">Seed {pair[0]}</span>
                <span style={{ color: "var(--agent-ink-muted)" }}>vs</span>
                <span class="tabular-nums">Seed {pair[1]}</span>
                <Show when={teamName(pair[0]) && teamName(pair[1])}>
                  <span class="truncate opacity-70">
                    ({teamName(pair[0])} vs {teamName(pair[1])})
                  </span>
                </Show>
              </div>
            )}
          </For>
        </div>
      </Show>

      <Show when={tool() === "propose_update_seeding"}>
        <Field label="Teams">{Object.keys(p().seeding || {}).length}</Field>
        <p class="text-xs text-amber-700 dark:text-amber-500">
          Reseeds every pool and Swiss group. Only possible before the
          tournament starts.
        </p>
      </Show>

      <Show
        when={
          tool() === "propose_bulk_schedule" ||
          tool() === "propose_recommended_schedule"
        }
      >
        <Field label="Matches">{(p().assignments || []).length}</Field>
        <div
          class="max-h-40 overflow-y-auto rounded border"
          style={{ "border-color": "var(--agent-line)" }}
        >
          <table class="w-full text-left text-[11px]">
            <thead
              class="sticky top-0"
              style={{
                "background-color": "var(--agent-canvas)",
                color: "var(--agent-ink-muted)"
              }}
            >
              <tr>
                <th class="px-2 py-1 font-medium">Match</th>
                <th class="px-2 py-1 font-medium">Field</th>
                <th class="px-2 py-1 font-medium">Time</th>
              </tr>
            </thead>
            <tbody style={{ color: "var(--agent-ink)" }}>
              <For each={p().assignments || []}>
                {a => (
                  <tr
                    class="border-t"
                    style={{ "border-color": "var(--agent-line)" }}
                  >
                    <td class="px-2 py-1 tabular-nums">
                      {a.match_name || `#${a.match_id}`}
                    </td>
                    <td class="px-2 py-1">{props.fieldName?.(a.field_id) || a.field_id}</td>
                    <td class="px-2 py-1 tabular-nums">
                      {String(a.time || "").replace("T", " ").slice(0, 16)}
                    </td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>

      <Show when={tool() === "propose_delete_match"}>
        <Field label="Match">#{p().match_id}</Field>
        <p class="text-xs text-red-700 dark:text-red-400">
          Deleting a match cannot be undone from this tab.
        </p>
      </Show>

      <Show when={tool() === "propose_start_tournament"}>
        <p class="text-xs" style={{ color: "var(--agent-ink)" }}>
          Assigns teams into pools and Swiss groups from the current seeding and
          moves the tournament to Live.
        </p>
        <p class="text-xs text-amber-700 dark:text-amber-500">
          Seeding can no longer be changed afterwards.
        </p>
      </Show>
    </div>
  );
};

const ProposalCard = props => {
  const [showJson, setShowJson] = createSignal(false);
  const p = () => props.proposal;
  const locked = () => props.disabled || props.confirming || props.rejecting;
  const title = () => TOOL_TITLES[p().tool_name] || p().tool_name;
  const highImpact = () => HIGH_IMPACT.has(p().tool_name);

  return (
    <div
      class="rounded-lg border transition-shadow duration-200"
      style={{
        "border-color": highImpact()
          ? "rgb(217 119 6 / 0.5)"
          : "var(--agent-line-strong)",
        "background-color": "var(--agent-raised)"
      }}
    >
      <div class="p-3">
        <div class="mb-2 flex items-center gap-2">
          <span
            class="text-sm font-semibold"
            style={{ color: "var(--agent-ink)" }}
          >
            {title()}
          </span>
          <Show when={highImpact()}>
            <span class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-800 dark:bg-amber-900/60 dark:text-amber-300">
              High impact
            </span>
          </Show>
        </div>

        <ProposalPreview
          proposal={p()}
          seedToTeamName={props.seedToTeamName}
          fieldName={props.fieldName}
        />

        <div class="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white transition-colors duration-150 hover:bg-emerald-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-emerald-600 dark:hover:bg-emerald-700"
            disabled={locked()}
            onClick={() => props.onConfirm?.()}
          >
            <Show when={props.confirming}>
              <Spinner noMargin height="12" width="12" />
            </Show>
            Confirm
          </button>
          <button
            type="button"
            class="cursor-pointer rounded-md border px-3 py-1.5 text-xs font-medium transition-colors duration-150 hover:bg-black/[0.04] focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-white/[0.06]"
            style={{
              "border-color": "var(--agent-line-strong)",
              color: "var(--agent-ink-muted)"
            }}
            disabled={locked()}
            onClick={() => props.onReject?.()}
          >
            Reject
          </button>
          <button
            type="button"
            class="ml-auto cursor-pointer text-[11px] underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            style={{ color: "var(--agent-ink-muted)" }}
            onClick={() => setShowJson(!showJson())}
            aria-expanded={showJson()}
          >
            {showJson() ? "Hide payload" : "View payload"}
          </button>
        </div>
      </div>

      <Show when={showJson()}>
        <pre
          class="max-h-40 overflow-auto border-t px-3 py-2 font-mono text-[11px] leading-snug"
          style={{
            "border-color": "var(--agent-line)",
            color: "var(--agent-ink-muted)"
          }}
        >
          {JSON.stringify(p().payload, null, 2)}
        </pre>
      </Show>
    </div>
  );
};

export default ProposalCard;
