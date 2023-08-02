import { For } from "solid-js";
import { AccordionDownIcon } from "../icons";

const MembershipPlayerList = props => {
  const players = props.players;
  return (
    <div id="accordion-collapse" data-accordion="collapse">
      <h2 id="accordion-collapse-heading-1">
        <button
          type="button"
          class="flex items-center justify-between w-full p-5 font-medium text-left text-gray-500 border border-b-0 border-gray-200 rounded-t-xl focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-800 dark:border-gray-700 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
          data-accordion-target="#accordion-collapse-body-1"
          aria-expanded="true"
          aria-controls="accordion-collapse-body-1"
        >
          <span>
            Paying UPAI membership fee for {props.players.length} players (₹
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
        <div class="p-5 border border-gray-200 dark:border-gray-700 dark:bg-gray-900">
          <div class="relative overflow-x-auto">
            <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
              <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
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
                    <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                      <th
                        scope="row"
                        class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                      >
                        {player.full_name}
                      </th>
                      <td class="px-6 py-4">{player.team_name}</td>
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
