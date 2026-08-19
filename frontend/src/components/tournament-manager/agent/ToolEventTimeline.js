import { createSignal, For, Show } from "solid-js";

/** Tool names are API-shaped; show staff what the call actually does. */
const TOOL_LABELS = {
  get_tournament_overview: "Read tournament overview",
  list_teams_seeding: "Read teams & seeding",
  list_pools: "Read pools",
  list_swiss_rounds: "Read Swiss rounds",
  list_brackets: "Read brackets",
  list_cross_pools: "Read cross pool",
  list_position_pools: "Read position pools",
  list_fields: "Read fields",
  list_matches: "Read matches",
  get_standings: "Read standings",
  get_swiss_standings: "Read Swiss standings",
  list_stages: "Read stage progress",
  list_proposals: "Read pending proposals",
  check_schedule_conflicts: "Check schedule conflicts",
  ask_user: "Ask a question",
  propose_create_pool: "Propose pool",
  propose_create_swiss_round: "Propose Swiss round",
  propose_create_cross_pool: "Propose cross pool",
  propose_create_cross_pool_matches: "Propose cross pool matches",
  propose_create_bracket: "Propose bracket",
  propose_create_position_pool: "Propose position pool",
  propose_create_field: "Propose field",
  propose_update_field: "Propose field update",
  propose_delete_field: "Propose field deletion",
  propose_update_seeding: "Propose seeding change",
  propose_update_match: "Propose match change",
  propose_update_match_seeds: "Propose match seed change",
  propose_delete_match: "Propose match deletion",
  propose_bulk_schedule: "Propose schedule",
  propose_recommended_schedule: "Propose schedule",
  propose_match_score: "Propose match result",
  propose_shift_schedule: "Propose schedule shift",
  propose_delete_stage: "Propose stage deletion",
  propose_full_setup: "Propose full setup",
  propose_start_tournament: "Propose tournament start",
  propose_generate_fixtures: "Propose fixture population"
};

const STATUS_DOT = {
  running: "bg-blue-500",
  ok: "bg-emerald-500",
  proposal: "bg-blue-500",
  question: "bg-amber-500",
  error: "bg-red-500"
};

const labelFor = name => TOOL_LABELS[name] || name;

const formatDuration = ms => {
  if (ms == null) return "";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
};

const prettyArgs = args => {
  if (!args || Object.keys(args).length === 0) return null;
  try {
    return JSON.stringify(args, null, 2);
  } catch (e) {
    return null;
  }
};

const Chevron = props => (
  <svg
    class={`h-3 w-3 shrink-0 transition-transform duration-200 ${
      props.open ? "rotate-180" : ""
    }`}
    style={{ color: "var(--agent-ink-muted)" }}
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 10 6"
  >
    <path
      stroke="currentColor"
      stroke-linecap="round"
      stroke-linejoin="round"
      stroke-width="2"
      d="m1 1 4 4 4-4"
    />
  </svg>
);

const ToolEventRow = props => {
  const [expanded, setExpanded] = createSignal(false);
  const event = () => props.event;
  const status = () => event().status || "ok";
  const running = () => status() === "running";
  const args = () => prettyArgs(event().arguments);

  return (
    <li>
      <button
        type="button"
        class="flex w-full cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-left transition-colors duration-150 hover:bg-black/[0.04] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:hover:bg-white/[0.06]"
        onClick={() => setExpanded(!expanded())}
        aria-expanded={expanded()}
      >
        <Show
          when={!running()}
          fallback={
            <span
              class="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-blue-500"
              aria-hidden="true"
            />
          }
        >
          <span
            class={`h-1.5 w-1.5 shrink-0 rounded-full ${
              STATUS_DOT[status()] || STATUS_DOT.ok
            }`}
            aria-hidden="true"
          />
        </Show>
        <span
          class="shrink-0 text-xs font-medium"
          style={{ color: "var(--agent-ink)" }}
        >
          {labelFor(event().name)}
        </span>
        <span
          class="min-w-0 flex-1 truncate text-xs"
          style={{
            color: status() === "error" ? undefined : "var(--agent-ink-muted)"
          }}
          classList={{ "text-red-600 dark:text-red-400": status() === "error" }}
        >
          {running() ? "Running…" : event().summary}
        </span>
        <Show when={event().duration_ms != null}>
          <span
            class="shrink-0 text-[10px] tabular-nums"
            style={{ color: "var(--agent-ink-muted)" }}
          >
            {formatDuration(event().duration_ms)}
          </span>
        </Show>
        <Chevron open={expanded()} />
      </button>
      <Show when={expanded()}>
        <div
          class="ml-3.5 mt-1 space-y-1 border-l pl-3"
          style={{ "border-color": "var(--agent-line-strong)" }}
        >
          <p
            class="font-mono text-[10px]"
            style={{ color: "var(--agent-ink-muted)" }}
          >
            {event().name}
          </p>
          <Show
            when={args()}
            fallback={
              <p
                class="text-xs italic"
                style={{ color: "var(--agent-ink-muted)" }}
              >
                No arguments
              </p>
            }
          >
            <pre class="max-h-48 overflow-auto rounded bg-gray-900 p-2 font-mono text-[11px] leading-snug text-gray-100">
              {args()}
            </pre>
          </Show>
        </div>
      </Show>
    </li>
  );
};

/**
 * Tool activity for one assistant turn. Collapsed to a single line by default;
 * expands to per-call rows, and each row expands to the exact arguments sent.
 */
const ToolEventTimeline = props => {
  const [open, setOpen] = createSignal(props.defaultOpen ?? false);
  const events = () => props.events || [];
  const errorCount = () => events().filter(e => e.status === "error").length;
  const runningCount = () =>
    events().filter(e => e.status === "running").length;

  const headline = () => {
    const n = events().length;
    if (runningCount() > 0) {
      const current = events().find(e => e.status === "running");
      return current ? labelFor(current.name) + "…" : "Working…";
    }
    return `Used ${n} tool${n === 1 ? "" : "s"}`;
  };

  return (
    <Show when={events().length > 0}>
      <div
        class="mb-2 rounded-lg border px-2 py-1.5"
        style={{
          "border-color": "var(--agent-line)",
          "background-color": "var(--agent-canvas)"
        }}
      >
        <button
          type="button"
          class="flex w-full cursor-pointer items-center gap-2 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          onClick={() => setOpen(!open())}
          aria-expanded={open()}
        >
          <svg
            class="h-3.5 w-3.5 shrink-0"
            style={{ color: "var(--agent-ink-muted)" }}
            classList={{ "animate-spin": runningCount() > 0 }}
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z"
            />
          </svg>
          <span
            class="text-xs font-medium"
            style={{ color: "var(--agent-ink-muted)" }}
          >
            {headline()}
            <Show when={errorCount() > 0}>
              <span class="ml-1 text-red-600 dark:text-red-400">
                ({errorCount()} error{errorCount() === 1 ? "" : "s"})
              </span>
            </Show>
          </span>
          <span class="ml-auto">
            <Chevron open={open()} />
          </span>
        </button>
        <Show when={open()}>
          <ul class="mt-1 space-y-0.5">
            <For each={events()}>{event => <ToolEventRow event={event} />}</For>
          </ul>
        </Show>
      </div>
    </Show>
  );
};

export default ToolEventTimeline;
