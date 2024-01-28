import { For } from "solid-js";
const CreatedFields = props => {
  return (
    <div class="my-4 grid grid-cols-3 gap-4">
      <For each={props.fields}>
        {field => (
          <div>
            <div class="relative overflow-x-auto rounded-md">
              <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                <caption class="bg-gray-300 p-4 text-left text-lg font-semibold text-gray-900 rtl:text-right dark:bg-gray-700 dark:text-white">
                  {field.name}
                </caption>
                <tbody>
                  <tr class="bg-gray-200 dark:border-gray-700 dark:bg-gray-800">
                    <th
                      scope="row"
                      class="px-4 py-4 font-medium text-gray-900 dark:text-white"
                    >
                      Broadcasted ?
                    </th>
                    <td class="px-6 py-4">
                      {field.is_broadcasted ? "Yes" : "No"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </For>
    </div>
  );
};

export default CreatedFields;
