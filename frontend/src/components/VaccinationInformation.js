import { Match, Switch } from "solid-js";

import { vaccinationChoices } from "../constants";
import { getLabel } from "../utils";

const VaccinationInformation = props => {
  const url = (
    <a href={props?.vaccination?.certificate} target="_blank">
      View Certificate
    </a>
  );
  return (
    <>
      <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
        <th
          scope="row"
          class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
        >
          Vaccinated?
        </th>
        <td class="px-6 py-4">
          {props?.vaccination?.is_vaccinated ? "Yes" : "No"}
        </td>
      </tr>
      <Switch>
        <Match when={props?.vaccination?.is_vaccinated}>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Vaccination name
            </th>
            <td class="px-6 py-4">
              {getLabel(vaccinationChoices, props?.vaccination?.name)}
            </td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Vaccination certificate
            </th>
            <td class="px-6 py-4">{url}</td>
          </tr>
        </Match>
        <Match when={!props?.vaccination?.is_vaccinated}>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Reason
            </th>
            <td class="px-6 py-4">
              {props?.vaccination?.explain_not_vaccinated}
            </td>
          </tr>
        </Match>
      </Switch>
    </>
  );
};

export default VaccinationInformation;
