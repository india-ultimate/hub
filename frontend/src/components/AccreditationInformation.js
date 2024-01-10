import { accreditationChoices } from "../constants";
import { displayDate, getLabel } from "../utils";

const AccreditationInformation = props => {
  const url = (
    <a href={props?.accreditation?.certificate} target="_blank">
      View Certificate
    </a>
  );
  return (
    <div class="relative overflow-x-auto">
      <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
        <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
          <tr>
            <th scope="col" class="px-6 py-3">
              Accreditation Level
            </th>
            <th scope="col" class="px-6 py-3">
              {getLabel(accreditationChoices, props?.accreditation?.level)}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Accreditation Valid?
            </th>
            <td class="px-6 py-4">
              {props?.accreditation?.is_valid ? "Yes" : "No"}
            </td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Accreditation Date
            </th>
            <td class="px-6 py-4">{displayDate(props?.accreditation?.date)}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Accreditation Certificate
            </th>
            <td class="px-6 py-4">{url}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default AccreditationInformation;
