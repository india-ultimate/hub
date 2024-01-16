export const TournamentPageSkeleton = () => {
  return (
    <>
      {/* Tournament title and status badge */}
      <div class="px-1 py-3">
        <div class="mb-4 flex flex-col gap-2">
          <div class="h-6 w-24 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
          <div class="h-7 w-full animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
        </div>
        {/* Tournament location and date */}
        <div class="mb-4 flex flex-col gap-2">
          <div class="h-5 w-52 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
          <div class="h-5 w-52 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
        </div>
      </div>
      {/* Tournament section buttons */}
      <div class="my-4 flex flex-col gap-5">
        <div class="h-20 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
        <div class="h-20 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
        <div class="h-20 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
      </div>

      {/* Overall standings */}
      <div class="mb-2 mt-10 h-6 w-60 animate-pulse rounded-md bg-gray-400 px-1 dark:bg-gray-700/50" />

      {/* Standings tabs */}
      {/* <div class="mb-4">
        <div class="flex flex-wrap justify-start space-x-2 py-4">
          <div class="py-4 pl-1 pr-4">
            <div class="h-6 w-16 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
          </div>
          <div class="py-4 pl-1 pr-4">
            <div class="h-6 w-16 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
          </div>
          <div class="py-4 pl-1 pr-4">
            <div class="h-6 w-16 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
          </div>
        </div>
      </div> */}

      {/* Standings tab content */}
      {/* <div class="rounded-lg py-2">
        <div class="relative overflow-x-auto rounded-lg shadow-md">
          <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
            <tbody>
              <Standings />
            </tbody>
          </table>
        </div>
      </div> */}
    </>
  );
};
