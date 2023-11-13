import { For } from "solid-js";
const Contributor = () => {
  return (
    <div class="mt-4 flex items-center space-x-3">
      <div class="mb-2 h-2.5 w-32 rounded-full bg-gray-200 dark:bg-gray-700" />
    </div>
  );
};

const Transactions = () => {
  const array = Array.from({ length: 8 }, (value, index) => index);
  return (
    <tr>
      <For each={array}>
        {() => (
          <td class="px-6 py-4">
            <Contributor />
          </td>
        )}
      </For>
    </tr>
  );
};

export default Transactions;
