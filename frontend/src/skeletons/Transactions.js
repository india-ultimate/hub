import { For } from "solid-js";
const Contributor = () => {
  return (
    <div class="flex items-center mt-4 space-x-3">
      <div class="h-2.5 bg-gray-200 rounded-full dark:bg-gray-700 w-32 mb-2" />
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
