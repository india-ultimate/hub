import { displayDate } from "../utils";

const CollegeIDInformation = props => {
  const urls = (
    <>
      <a href={props?.college_id?.card_front} target="_blank">
        View Front
      </a>
      <span> | </span>
      <a href={props?.college_id?.card_back} target="_blank">
        View Back
      </a>
    </>
  );
  return (
    <div class="relative w-full overflow-x-auto">
      <table class="w-full w-full text-left text-sm text-gray-500 dark:text-gray-400">
        <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
          <tr>
            <th scope="col" class="px-6 py-3">
              Field
            </th>
            <th scope="col" class="px-6 py-3">
              Description
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Name
            </th>
            <td class="px-6 py-4">
              {props?.college_id?.ocr_name || "0"}% match
            </td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              College
            </th>
            <td class="px-6 py-4">
              {props?.college_id?.ocr_college || "0"}% match
            </td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Expiry Date
            </th>
            <td class="px-6 py-4">{displayDate(props?.college_id?.expiry)}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              ID Card
            </th>
            <td class="px-6 py-4">{urls}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default CollegeIDInformation;
