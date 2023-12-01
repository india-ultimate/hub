import { createMutation } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { createEffect, createSignal, Show } from "solid-js";

import { updateTournamentRules } from "../../queries";
import StyledMarkdown from "../StyledMarkdown";

const RulesMarkdownEditor = props => {
  const [rules, setRules] = createSignal("");
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  createEffect(() => setRules(props.tournament.rules || ""));

  const updateRulesMutation = createMutation({
    mutationFn: updateTournamentRules,
    onSuccess: data => {
      setStatus("Updated Rules!");
      setRules(data.rules);
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async () => {
    setStatus("");
    setError("");

    updateRulesMutation.mutate({
      tournament_id: props.tournament.id,
      body: {
        rules: rules()
      }
    });

    setTimeout(() => initFlowbite(), 1000);
  };

  return (
    <div class="grid grid-cols-2 gap-4 divide-x">
      <div>
        <h2 class="text-center font-bold">Markdown Editor</h2>
        <a
          href="https://www.markdownguide.org/cheat-sheet/"
          class="mb-2 block text-center text-sm font-medium text-blue-600 hover:underline dark:text-blue-500"
          target="_blank"
        >
          Click Here for markdown cheat sheet!
        </a>
        <textarea
          id="message"
          rows="40"
          class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          placeholder="Write your rules here..."
          onInput={e => setRules(e.target.value)}
        >
          {rules()}
        </textarea>
        <button
          type="submit"
          onClick={handleSubmit}
          class="mt-2 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
        >
          Update Rules
        </button>
        <Show when={error()}>
          <p class="my-2 text-sm text-red-600 dark:text-red-500">
            <span class="font-medium">Oops!</span> {error()}
          </p>
        </Show>
        <p>{status()}</p>
      </div>
      <div class="px-8">
        <h2 class="text-center font-bold">Preview</h2>
        {StyledMarkdown({
          markdown: rules()
        })}
      </div>
    </div>
  );
};

export default RulesMarkdownEditor;
