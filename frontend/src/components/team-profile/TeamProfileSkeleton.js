import { Bar, Circle, Loading } from "../../skeletons/primitives";

const TeamProfileSkeleton = () => (
  <Loading label="Loading team">
    <Bar class="h-8 w-48 !rounded-full" />
    <div class="mt-4 rounded-2xl border border-gray-200 p-5 dark:border-gray-700 md:flex md:items-center md:gap-8 md:p-6">
      <Circle class="mx-auto h-24 w-24 flex-none md:mx-0 md:h-32 md:w-32" />
      <div class="md:flex-1">
        <Bar class="mx-auto mt-4 h-9 w-48 md:mx-0 md:mt-0" />
        <Bar class="mx-auto mt-3 h-6 w-40 !rounded-full md:mx-0" />
        <Bar class="mx-auto mt-4 h-5 w-44 md:mx-0 md:mt-3" />
      </div>
    </div>
    <div class="mt-5 grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-4">
      <Bar class="h-16 !rounded-xl md:h-[84px]" />
      <Bar class="h-16 !rounded-xl md:h-[84px]" />
      <Bar class="h-16 !rounded-xl md:h-[84px]" />
      <Bar class="h-16 !rounded-xl md:h-[84px]" />
    </div>
    <Bar class="mt-7 h-6 w-32" />
    <Bar class="mt-3 h-[300px] !rounded-xl" />
  </Loading>
);

export default TeamProfileSkeleton;
