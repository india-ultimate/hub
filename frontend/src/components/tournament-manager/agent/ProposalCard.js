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
  propose_shift_schedule: "Shift schedule",
  propose_match_score: "Record match result",
  propose_spirit_scores: "Record spirit scores",
  propose_delete_stage: "Delete stage",
  propose_full_setup: null,
  propose_start_tournament: "Start tournament"
};

/** Destructive/irreversible proposals get a heavier confirm treatment. */
const HIGH_IMPACT = new Set([
  "propose_delete_match",
  "propose_delete_stage",
  "propose_match_score",
  "propose_start_tournament",
  "propose_update_seeding"
]);

/**
 * The agent only ever handles player ids. The server resolves them on the way out
 * and sends the names alongside the proposal, so this is a lookup, not a fetch.
 */
const PlayerName = props => (
  <span>{props.names?.[String(props.id)] || `Player ${props.id}`}</span>
);

const Field = props => (
  <div class="flex gap-2 text-xs">
    <span class="w-20 shrink-0" style={{ color: "var(--agent-ink-muted)" }}>
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
  const playerNames = () => props.proposal.player_names || {};

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

      <Show when={tool() === "propose_match_score"}>
        <Field label="Match">{p().match_id}</Field>
        <Field label="Score">
          {p().score_team_1} - {p().score_team_2}
          {p().forfeit ? " (forfeit)" : ""}
        </Field>
        <p class="mt-1 text-[11px]" style={{ color: "var(--agent-ink-muted)" }}>
          Completes the match, recomputes standings and seeding, and fills the
          next stage. Results cannot be edited afterwards.
        </p>
      </Show>

      <Show when={tool() === "propose_spirit_scores"}>
        <Field label="Match">{p().match_id}</Field>
        <For
          each={[
            ["team_1_received", "Team 1 received"],
            ["team_2_received", "Team 2 received"],
            ["team_1_self", "Team 1 self"],
            ["team_2_self", "Team 2 self"]
          ].filter(([key]) => p()[key])}
        >
          {([key, label]) => (
            <Field label={label}>
              {p()[key].rules}/{p()[key].fouls}/{p()[key].fair}/
              {p()[key].positive}/{p()[key].communication}
              <Show when={p()[key].mvp_id}>
                {" · MVP "}
                <PlayerName id={p()[key].mvp_id} names={playerNames()} />
              </Show>
              <Show when={p()[key].msp_id}>
                {" · MSP "}
                <PlayerName id={p()[key].msp_id} names={playerNames()} />
              </Show>
            </Field>
          )}
        </For>
      </Show>

      <Show when={tool() === "propose_delete_stage"}>
        <Field label="Stage">
          {p().stage} #{p().stage_id}
        </Field>
        <p class="mt-1 text-[11px]" style={{ color: "var(--agent-ink-muted)" }}>
          Deletes the stage and every match in it.
        </p>
      </Show>

      <Show
        when={
          tool() === "propose_bulk_schedule" ||
          tool() === "propose_recommended_schedule" ||
          tool() === "propose_shift_schedule"
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
                    <td class="px-2 py-1">
                      {props.fieldName?.(a.field_id) || a.field_id}
                    </td>
                    <td class="px-2 py-1 tabular-nums">
                      {String(a.time || "")
                        .replace("T", " ")
                        .slice(0, 16)}
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

      <Show when={tool() === "propose_full_setup"}>
        <Show when={p().pool_defs?.length}>
          <For each={p().pool_defs}>
            {def_ => (
              <div
                class="rounded border p-2"
                style={{ "border-color": "var(--agent-line)" }}
              >
                <Field label="Pool">{def_.name}</Field>
                <Field label="Seeds">
                  <SeedList seeds={def_.seeding} teamName={teamName} />
                </Field>
              </div>
            )}
          </For>
        </Show>
        <Show when={p().swiss_defs?.length}>
          <For each={p().swiss_defs}>
            {def_ => (
              <div
                class="rounded border p-2"
                style={{ "border-color": "var(--agent-line)" }}
              >
                <Field label="Swiss">{def_.name}</Field>
                <Field label="Rounds">{def_.num_rounds}</Field>
                <Field label="Seeds">
                  <SeedList seeds={def_.seeding} teamName={teamName} />
                </Field>
              </div>
            )}
          </For>
        </Show>
        <Show when={p().bracket_names?.length}>
          <Field label="Brackets">{p().bracket_names.join(", ")}</Field>
        </Show>
        <Show when={p().format}>
          <Field label="Format">{p().format}</Field>
        </Show>
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
  const title = () => {
    if (p().tool_name === "propose_full_setup") {
      const payload = p().payload || {};
      const parts = [];
      if (payload.pool_defs?.length)
        parts.push(
          `${payload.pool_defs.length} pool${payload.pool_defs.length > 1 ? "s" : ""}`
        );
      if (payload.swiss_defs?.length)
        parts.push(
          `${payload.swiss_defs.length} Swiss group${payload.swiss_defs.length > 1 ? "s" : ""}`
        );
      if (payload.bracket_names?.length)
        parts.push(
          `${payload.bracket_names.length} bracket${payload.bracket_names.length > 1 ? "s" : ""}`
        );
      return parts.length ? `Create ${parts.join(" + ")}` : "Full tournament setup";
    }
    return TOOL_TITLES[p().tool_name] || p().tool_name;
  };
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
