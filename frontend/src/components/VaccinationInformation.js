import { Switch, Match } from "solid-js";
import { getCookie, getLabel } from "../utils";
import { vaccinationChoices } from "../constants";
import { useNavigate } from "@solidjs/router";

const VaccinationInformation = props => {
  const csrftoken = getCookie("csrftoken");
  const navigate = useNavigate();

  const navUpdateVaccination = async () => {
    try {
      const response = await fetch(`/api/vaccination/${props.player.id}`, {
        method: "DELETE",
        headers: {
          "X-CSRFToken": csrftoken
        }
      });

      if (response.ok) {
        navigate(`/vaccination/${props.player.id}`);
      } else {
        const data = await response.json();
        console.log(data.message);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const url = (
    <a href={props?.player?.vaccination?.certificate} target="_blank">
      Certificate
    </a>
  );
  return (
    <>
      <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
        <th
          scope="row"
          class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
        >
          Vaccinated?
        </th>
        <td class="px-6 py-4">
          {props?.player?.vaccination?.is_vaccinated ? "Yes" : "No"}
        </td>
      </tr>
      <Switch>
        <Match when={props?.player?.vaccination?.is_vaccinated}>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Vaccination name
            </th>
            <td class="px-6 py-4">
              {getLabel(vaccinationChoices, props?.player?.vaccination?.name)}
            </td>
          </tr>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Vaccination certificate
            </th>
            <td class="px-6 py-4">{url}</td>
            <td>
              <button
                type="submit"
                class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                onClick={navUpdateVaccination}
              >
                Update here
              </button>
            </td>
          </tr>
        </Match>
        <Match when={!props?.player?.vaccination?.is_vaccinated}>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Reason
            </th>
            <td class="px-6 py-4">
              {props?.player?.vaccination?.explain_not_vaccinated}
            </td>
          </tr>
        </Match>
      </Switch>
    </>
  );
};

export default VaccinationInformation;
