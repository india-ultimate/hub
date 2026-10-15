import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import {
  createEffect,
  createSignal,
  createUniqueId,
  For,
  Show
} from "solid-js";

import { fetchCommittees } from "../../queries";
import Avatar from "../committee/Avatar";

const matches = (name, text) => name.toLowerCase().includes(text.toLowerCase());

// A searchable list of everyone with a current role, by committee, the ticket's
// routed committees first. A combobox: arrows move, Enter picks, Escape closes.
const AssigneePicker = props => {
  const id = createUniqueId();
  const [text, setText] = createSignal("");
  const [active, setActive] = createSignal(0);
  const query = createQuery(() => ["committees"], fetchCommittees);

  const groups = () =>
    (query.data ?? [])
      .map(committee => ({
        committee,
        roles: committee.roles.filter(
          role =>
            !props.assigned.includes(role.person.id) &&
            matches(role.person.full_name, text())
        )
      }))
      .filter(group => group.roles.length)
      .sort(
        (a, b) =>
          props.routed.includes(b.committee.slug) -
          props.routed.includes(a.committee.slug)
      );
  const options = () => groups().flatMap(group => group.roles);
  const optionId = role => `${id}-${role.id}`;

  createEffect(() => {
    const role = options()[active()];
    if (role)
      document
        .getElementById(optionId(role))
        ?.scrollIntoView({ block: "nearest" });
  });

  const choose = role => role && props.onPick(role.person);
  const onKeyDown = e => {
    const last = options().length - 1;
    if (e.key === "ArrowDown") setActive(Math.min(active() + 1, last));
    else if (e.key === "ArrowUp") setActive(Math.max(active() - 1, 0));
    else if (e.key === "Enter") choose(options()[active()]);
    else if (e.key === "Escape") props.onClose();
    else return;
    e.preventDefault();
  };

  return (
    <div class="mt-3 rounded-lg border border-gray-300 bg-white p-2 dark:border-gray-600 dark:bg-gray-700">
      <input
        id="assignee-search"
        type="text"
        role="combobox"
        aria-label="Search people to assign"
        aria-expanded="true"
        aria-controls={`${id}-list`}
        aria-activedescendant={
          options()[active()] ? optionId(options()[active()]) : undefined
        }
        autocomplete="off"
        placeholder="Search people"
        ref={el => queueMicrotask(() => el.focus())}
        value={text()}
        onInput={e => {
          setText(e.currentTarget.value);
          setActive(0);
        }}
        onKeyDown={onKeyDown}
        class="block min-h-[44px] w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
      />
      <ul
        id={`${id}-list`}
        role="listbox"
        aria-label="People with a committee role"
        class="mt-2 max-h-64 overflow-y-auto"
      >
        <For each={groups()}>
          {group => (
            <li role="presentation">
              <p class="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
                {group.committee.name}
              </p>
              <ul role="group" aria-label={group.committee.name}>
                <For each={group.roles}>
                  {role => (
                    <li
                      id={optionId(role)}
                      role="option"
                      aria-selected={options()[active()] === role}
                      onMouseDown={e => e.preventDefault()}
                      onClick={() => choose(role)}
                      class={clsx(
                        "flex min-h-[44px] cursor-pointer items-center gap-2 rounded-lg px-2 text-sm text-gray-900 dark:text-white",
                        options()[active()] === role
                          ? "bg-blue-100 dark:bg-blue-900"
                          : "hover:bg-gray-100 dark:hover:bg-gray-600"
                      )}
                    >
                      <Avatar
                        src={role.person.profile_pic_url}
                        name={role.person.full_name}
                        class="h-7 w-7 text-xs"
                      />
                      {role.person.full_name}
                      <Show when={role.is_chair}>
                        <span class="text-xs text-gray-600 dark:text-gray-300">
                          Chair
                        </span>
                      </Show>
                    </li>
                  )}
                </For>
              </ul>
            </li>
          )}
        </For>
      </ul>
      <Show when={!options().length}>
        <p class="px-2 py-2 text-sm text-gray-600 dark:text-gray-300">
          {query.isLoading ? "Loading…" : "No one with a role matches."}
        </p>
      </Show>
    </div>
  );
};

export default AssigneePicker;
