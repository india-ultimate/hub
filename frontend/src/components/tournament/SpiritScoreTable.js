const SpiritScoreTable = props => {
  return (
    <div class="relative overflow-x-auto">
      <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
        <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
          <tr>
            <th scope="col" class="px-2 py-3">
              Spirit Criteria
            </th>
            <th scope="col" class="px-2 py-3">
              {props.team_1.name}
            </th>
            <th scope="col" class="px-2 py-3">
              {props.team_2.name}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-700">
            <th
              scope="row"
              class="py-4 pl-2 pr-6 font-medium text-gray-900 dark:text-white sm:pr-20"
            >
              Rules Knowledge & Use
            </th>
            <td class="px-2 py-4">{props.spirit_score_team_1?.rules}</td>
            <td class="px-2 py-4">{props.spirit_score_team_2?.rules}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-700">
            <th
              scope="row"
              class="py-4 pl-2 pr-6 font-medium text-gray-900 dark:text-white sm:pr-20"
            >
              Fouls & Body Contact
            </th>
            <td class="px-2 py-4">{props.spirit_score_team_1?.fouls}</td>
            <td class="px-2 py-4">{props.spirit_score_team_2?.fouls}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-700">
            <th
              scope="row"
              class="py-4 pl-2 pr-6 font-medium text-gray-900 dark:text-white sm:pr-20"
            >
              Fair-Mindedness
            </th>
            <td class="px-2 py-4">{props.spirit_score_team_1?.fair}</td>
            <td class="px-2 py-4">{props.spirit_score_team_2?.fair}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-700">
            <th
              scope="row"
              class="py-4 pl-2 pr-6 font-medium text-gray-900 dark:text-white sm:pr-20"
            >
              Positive Attitude & Self-Control
            </th>
            <td class="px-2 py-4">{props.spirit_score_team_1?.positive}</td>
            <td class="px-2 py-4">{props.spirit_score_team_2?.positive}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-700">
            <th
              scope="row"
              class="py-4 pl-2 pr-6 font-medium text-gray-900 dark:text-white sm:pr-20"
            >
              Communication
            </th>
            <td class="px-2 py-4">
              {props.spirit_score_team_1?.communication}
            </td>
            <td class="px-2 py-4">
              {props.spirit_score_team_2?.communication}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default SpiritScoreTable;
