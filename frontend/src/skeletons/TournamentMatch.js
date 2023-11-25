const TournamentMatch = () => {
  return (
    <div class="mb-5 block w-full rounded-lg border border-gray-400 bg-white px-1 py-2 shadow dark:border-gray-400 dark:bg-gray-800">
      {/* Match card */}
      <div class="mb-4">
        <div class="flex w-full flex-wrap justify-center rounded bg-gray-100 px-2.5 py-3.5 dark:bg-gray-900 ">
          <div
            role="status"
            class="h-2 w-32 animate-pulse rounded-full bg-gray-200 dark:bg-gray-700"
          />
        </div>
      </div>

      {/* Team names, seeds, images */}
      <div class="flex animate-pulse justify-center">
        <div class="mr-1 h-6 w-6 rounded-full p-1 ring-2 ring-gray-500 dark:ring-gray-400" />
        <div class="flex w-1/3 justify-center">
          <div class="h-2.5 w-24 self-center rounded-full bg-gray-300 dark:bg-gray-700" />
        </div>

        <div class="mx-2 self-center text-center text-sm">VS</div>

        <div class="flex w-1/3 justify-center ">
          <div class="h-2.5 w-24 self-center rounded-full bg-gray-300 dark:bg-gray-700" />
        </div>
        <div class="mr-1 h-6 w-6 rounded-full p-1 ring-2 ring-gray-500 dark:ring-gray-400" />
      </div>

      {/* match scores */}
      <div class="flex justify-center">
        <div class="flex animate-pulse justify-between space-x-2">
          <div class="h-2 w-4 self-center rounded-full bg-gray-200 dark:bg-gray-700" />
          <div class="self-center">{" - "}</div>
          <div class="h-2 w-4 self-center rounded-full bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>

      {/* spirit scores */}
      <div class="flex justify-center">
        <div class="flex animate-pulse justify-between space-x-2">
          <div class="h-2 w-4 self-center rounded-full bg-gray-200 dark:bg-gray-700" />
          <div class="self-center">{" - "}</div>
          <div class="h-2 w-4 self-center rounded-full bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>

      {/* field and duration */}
      <div class="mt-2 flex justify-center">
        <div class="flex animate-pulse justify-between space-x-2">
          <div class="h-2 w-24 self-center rounded-full bg-gray-200 dark:bg-gray-700" />
          <div class="self-center text-sm">|</div>
          <div class="h-2 w-24 self-center rounded-full bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>

      <div class="mb-2 mt-5 flex animate-pulse justify-center">
        <div class="flex h-10 w-44 justify-center rounded-lg bg-gray-200 dark:bg-gray-700 " />
      </div>
    </div>
  );
};

const TournamentMatches = () => {
  console.log("in tournament match skeleton");
  return (
    <div class="mb-10">
      <div class="mb-5 ml-1">
        <h3 class="text-center text-lg font-bold">Day - 1</h3>
      </div>
      <TournamentMatch />
      <TournamentMatch />
      <div class="mb-5 ml-1">
        <h3 class="text-center text-lg font-bold">Day - 2</h3>
      </div>
      <TournamentMatch />
      <TournamentMatch />
      <TournamentMatch />
    </div>
  );
};

export default TournamentMatches;
