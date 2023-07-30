import { vaccinationChoices } from "../constants";
import { getLabel } from "../utils";

const VaccinationInformation = props => {
  const url = (
    <a href={props?.vaccination?.certificate} target="_blank">
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
          {props?.vaccination?.is_vaccinated ? "Yes" : "No"}
        </td>
      </tr>
      <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
        <th
          scope="row"
          class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
        >
          Vaccination name
        </th>
        <td class="px-6 py-4">{props?.vaccination?.name === "OTHER" ? props?.vaccination?.other_name : getLabel(vaccinationChoices, props?.vaccination?.name)}</td>
      </tr>
      <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
        <th
          scope="row"
          class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
        >
          Vaccination certificate
        </th>
        <td class="px-6 py-4">{url}</td>
      </tr>
    </>
  );
};

export default VaccinationInformation;
