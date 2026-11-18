import { createQuery } from "@tanstack/solid-query";
import { createSignal, Match, Show, Switch } from "solid-js";

import { createSaved } from "../../committees";
import { fetchCommittees } from "../../queries";
import { Bar, Loading } from "../../skeletons/primitives";
import Error from "../alerts/Error";
import PillTabs from "../tabs/PillTabs";
import ManageCommittees from "./ManageCommittees";
import ManagePeople from "./ManagePeople";

const TABS = [
  { id: "people", label: "People" },
  { id: "committees", label: "Committees" }
];

// Staff only: who holds which role, and the committees.
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
      <Show
        when={query.data}
        fallback={
          <Show
            when={!query.isError}
            fallback={
              <Error text="The committees could not be loaded. Please try again." />
            }
          >
            <Show when={query.isLoading}>
              <Loading label="Loading committees">
                <Bar class="h-48 w-full !rounded-lg" />
              </Loading>
            </Show>
          </Show>
        }
      >
        <Switch>
          <Match when={tab() === "people"}>
            <ManagePeople committees={query.data} onSaved={flash} />
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
