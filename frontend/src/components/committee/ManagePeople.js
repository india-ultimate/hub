import { useQueryClient } from "@tanstack/solid-query";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";

import {
  card,
  input,
  NoOneListed,
  primaryButton,
  secondaryButton,
  sinceLabel
} from "../../committees";
import { ChairBadge } from "../../committees";
import { updateCommitteeRole } from "../../queries";
import Modal from "../Modal";
import AddPersonForm from "./AddPersonForm";
import Avatar from "./Avatar";
import EditRoleForm from "./EditRoleForm";
import EndTermForm from "./EndTermForm";
import PostSwitch from "./PostSwitch";

const TITLES = {
  add: "Add person",
  edit: "Edit role",
  end: "End term"
};

// The People tab: one committee's current roles, and the dialogs that change them.
const ManagePeople = props => {
  const queryClient = useQueryClient();
  const [slug, setSlug] = createSignal("");
  // What the dialog is doing: { kind: "add" | "edit" | "end", role? }
  const [action, setAction] = createSignal(null);
  let dialog;

  const committee = () =>
    props.committees.find(c => c.slug === slug()) ?? props.committees[0];

  createEffect(() => {
    if (action() && !dialog.open) dialog.showModal();
    if (!action() && dialog.open) dialog.close();
  });

  const done = () => {
    setAction(null);
    props.onSaved();
    queryClient.invalidateQueries({ queryKey: ["committees"] });
    queryClient.invalidateQueries({ queryKey: ["committee"] });
  };

  const setRoleFlag = async (id, flags) => {
    await updateCommitteeRole({ id, ...flags });
    props.onSaved();
    queryClient.invalidateQueries({ queryKey: ["committee"] });
    await queryClient.invalidateQueries(
      { queryKey: ["committees"] },
      { throwOnError: true }
    );
  };

  return (
    <div>
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="w-full sm:w-72">
          <label
            for="people-committee"
            class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
          >
            Committee
          </label>
          <select
            id="people-committee"
            value={committee()?.slug}
            onChange={e => setSlug(e.currentTarget.value)}
            class={input}
          >
            <For each={props.committees}>
              {c => <option value={c.slug}>{c.name}</option>}
            </For>
          </select>
        </div>
        <button
          type="button"
          class={primaryButton}
          onClick={() => setAction({ kind: "add" })}
        >
          Add person
        </button>
      </div>

      <ul class="mt-4 space-y-3">
        <For each={committee()?.roles} fallback={<NoOneListed />}>
          {role => (
            <li class={`${card} flex flex-wrap items-center gap-3 !p-3`}>
              <Avatar
                src={role.person.profile_pic_url}
                name={role.person.full_name}
              />
              <div class="min-w-0 flex-1 basis-40">
                <p class="break-words font-medium text-gray-900 dark:text-white">
                  {role.person.full_name}
                </p>
                <p class="flex flex-wrap items-center gap-x-2 text-sm text-gray-600 dark:text-gray-400">
                  <Show when={role.is_chair}>
                    <ChairBadge />
                  </Show>
                  {role.title} · {sinceLabel(role)}
                </p>
              </div>
              <PostSwitch
                label={`Can post announcements${
                  committee().can_post_announcements ? " (via committee)" : ""
                }`}
                checked={
                  role.can_post_announcements ||
                  committee().can_post_announcements
                }
                disabled={committee().can_post_announcements}
                onChange={can_post_announcements =>
                  setRoleFlag(role.id, { can_post_announcements })
                }
              />
              <PostSwitch
                label={`Can create forms${
                  committee().can_create_forms ? " (via committee)" : ""
                }`}
                checked={role.can_create_forms || committee().can_create_forms}
                disabled={committee().can_create_forms}
                onChange={can_create_forms =>
                  setRoleFlag(role.id, { can_create_forms })
                }
              />
              <div class="flex gap-2">
                <button
                  type="button"
                  class={secondaryButton}
                  aria-label={`Edit ${role.person.full_name}`}
                  onClick={() => setAction({ kind: "edit", role })}
                >
                  Edit
                </button>
                <button
                  type="button"
                  class={secondaryButton}
                  aria-label={`End term for ${role.person.full_name}`}
                  onClick={() => setAction({ kind: "end", role })}
                >
                  End term
                </button>
              </div>
            </li>
          )}
        </For>
      </ul>

      <Modal
        ref={el => {
          dialog = el;
          el.addEventListener("close", () => setAction(null));
        }}
        title={
          <span class="font-semibold text-gray-900 dark:text-white">
            {TITLES[action()?.kind]}
          </span>
        }
        close={() => setAction(null)}
      >
        <Show when={action()}>
          <Switch>
            <Match when={action().kind === "add"}>
              <AddPersonForm slug={committee().slug} done={done} />
            </Match>
            <Match when={action().kind === "edit"}>
              <EditRoleForm role={action().role} done={done} />
            </Match>
            <Match when={action().kind === "end"}>
              <EndTermForm
                role={action().role}
                done={done}
                cancel={() => setAction(null)}
              />
            </Match>
          </Switch>
        </Show>
      </Modal>
    </div>
  );
};

export default ManagePeople;
