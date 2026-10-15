import { createQuery } from "@tanstack/solid-query";
import { createSignal, Match, Show, Switch } from "solid-js";

import { createSaved } from "../../committees";
import { fetchCommittees } from "../../queries";
import PillTabs from "../tabs/PillTabs";
import ManageCommittees from "./ManageCommittees";
import ManagePeople from "./ManagePeople";
import ManageRouting from "./ManageRouting";

const TABS = [
  { id: "people", label: "People" },
  { id: "routing", label: "Ticket routing" },
  { id: "committees", label: "Committees" }
];

// Staff only: who holds which role, where tickets go, and the committees.
const Manage = () => {
  const [tab, setTab] = createSignal("people");
  const [saved, flash] = createSaved();
  const query = createQuery(() => ["committees"], fetchCommittees);

  return (
    <div class="mx-auto max-w-4xl">
      <h1 class="mb-4 text-4xl font-bold text-blue-700 dark:text-white">
        Manage committees
      </h1>
      <PillTabs tabs={TABS} activeTab={tab} onTabChange={setTab} />
      <p
        role="status"
        class="mb-2 h-6 text-sm font-medium text-green-700 dark:text-green-400"
      >
        <Show when={saved()}>Saved</Show>
      </p>
      <Show when={query.data}>
        <Switch>
          <Match when={tab() === "people"}>
            <ManagePeople committees={query.data} onSaved={flash} />
          </Match>
          <Match when={tab() === "routing"}>
            <ManageRouting committees={query.data} onSaved={flash} />
          </Match>
          <Match when={tab() === "committees"}>
            <ManageCommittees committees={query.data} onSaved={flash} />
          </Match>
        </Switch>
      </Show>
    </div>
  );
};

export default Manage;
