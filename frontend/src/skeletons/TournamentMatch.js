import { Bar, Circle, Loading } from "./primitives";

const TournamentMatch = () => (
  <div class="mb-5 block w-full rounded-lg border border-gray-200 bg-white px-1 py-2 shadow dark:border-gray-700 dark:bg-gray-800">
    <div class="mb-4 flex w-full justify-center rounded px-2.5 py-3.5">
      <Bar class="h-2 w-32 !rounded-full" />
    </div>
    <div class="flex items-center justify-center">
      <Circle class="mr-1 h-6 w-6" />
      <div class="flex w-1/3 justify-center">
        <Bar class="h-2.5 w-24 !rounded-full" />
      </div>
      <Bar class="mx-2 h-4 w-6" />
      <div class="flex w-1/3 justify-center">
        <Bar class="h-2.5 w-24 !rounded-full" />
      </div>
      <Circle class="mr-1 h-6 w-6" />
    </div>
    <div class="mt-2 flex justify-center">
      <Bar class="h-2 w-10 !rounded-full" />
    </div>
    <div class="mt-5 flex justify-center">
      <Bar class="h-2 w-24 !rounded-full" />
    </div>
    <div class="mb-3 mt-5 flex justify-center">
      <Bar class="h-7 w-28 !rounded-full" />
    </div>
  </div>
);

const TournamentMatches = () => (
  <Loading label="Loading matches">
    <TournamentMatch />
    <TournamentMatch />
    <TournamentMatch />
    <TournamentMatch />
  </Loading>
);

const TournamentTeamMatches = () => (
  <Loading label="Loading matches" class="mb-10">
    <div class="mb-5 ml-1 flex justify-center">
      <Bar class="h-7 w-20" />
    </div>
    <TournamentMatch />
    <TournamentMatch />
  </Loading>
);

export { TournamentMatches, TournamentTeamMatches };
