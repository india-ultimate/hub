import { WALink } from "../constants";

const HelpImport = () => {
  return (
    <div>
      <h1 class="text-2xl md:text-2xl font-bold mb-4 text-blue-500">
        Import Players from a Spreadsheet
      </h1>
      <p>
        For players creating and managing the profiles of multiple players of
        their team, we provide a way to create user accounts and import player
        profiles from a Spreadsheet.
      </p>
      <ol class="space-y-1 text-gray-500 list-decimal list-inside dark:text-gray-400">
        <li>
          Create a copy of the template{" "}
          <a
            href="https://docs.google.com/spreadsheets/d/1UGSlRHqRA8V_Extze5mh2Y7TzmQlJjqZkwpXb2Osvck"
            class="font-medium text-blue-600 underline dark:text-blue-500 hover:no-underline"
          >
            here
          </a>
        </li>
        <li>Fill up the details of all the players of your team</li>
        <li>
          Reach out to the India Ultimate Tech team via{" "}
          <a
            href={WALink}
            class="font-medium text-blue-600 underline dark:text-blue-500 hover:no-underline"
          >
            WhatsApp
          </a>
        </li>
      </ol>
    </div>
  );
};

export default HelpImport;
