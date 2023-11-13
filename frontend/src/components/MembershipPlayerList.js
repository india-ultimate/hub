import { For } from "solid-js";
import { AccordionDownIcon } from "../icons";

const MembershipPlayerList = props => {
  return (
    <div id="accordion-collapse" data-accordion="collapse">
      <h2 id="accordion-collapse-heading-1">
        <button
          type="button"
          class="flex w-full items-center justify-between rounded-t-xl border border-b-0 border-gray-200 p-5 text-left font-medium text-gray-500 hover:bg-gray-100 focus:ring-4 focus:ring-gray-200 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:focus:ring-gray-800"
          data-accordion-target="#accordion-collapse-body-1"
          aria-expanded="true"
          aria-controls="accordion-collapse-body-1"
        >
          <span>
            Paying India Ultimate membership fee for {props.players.length}{" "}
            players (₹
            {props.fee}) valid for the period from {props.startDate} to{" "}
            {props.endDate}
          </span>
          <AccordionDownIcon />
        </button>
      </h2>
      <div
        id="accordion-collapse-body-1"
        class="hidden"
        aria-labelledby="accordion-collapse-heading-1"
      >
        <div class="border border-gray-200 p-5 dark:border-gray-700 dark:bg-gray-900">
          <div class="relative overflow-x-auto">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" class="px-6 py-3">
                    Player
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Team
                  </th>
                  <th scope="col" class="px-6 py-3">
                    City
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={props.players}>
                  {player => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <th
                        scope="row"
                        class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
                      >
                        {player.full_name} {player.is_minor ? "*" : ""}
                      </th>
                      <td class="px-6 py-4">
                        {player.teams.map(team => team["name"]).join(", ")}
                      </td>
                      <td class="px-6 py-4">{player.city}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
export default MembershipPlayerList;
