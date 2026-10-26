const bar = "bg-gray-200 dark:bg-gray-700";

const TeamProfileSkeleton = () => (
  <div class="animate-pulse motion-reduce:animate-none" role="status">
    <span class="sr-only">Loading team</span>
    <div class={`h-8 w-48 rounded-full ${bar}`} />
    <div class="mt-4 rounded-2xl border border-gray-200 p-5 dark:border-gray-700 md:flex md:items-center md:gap-8 md:p-6">
      <div
        class={`mx-auto h-24 w-24 flex-none rounded-full md:mx-0 md:h-32 md:w-32 ${bar}`}
      />
      <div class="md:flex-1">
        <div class={`mx-auto mt-4 h-9 w-48 rounded md:mx-0 md:mt-0 ${bar}`} />
        <div class={`mx-auto mt-3 h-6 w-40 rounded-full md:mx-0 ${bar}`} />
        <div class={`mx-auto mt-4 h-5 w-44 rounded md:mx-0 md:mt-3 ${bar}`} />
      </div>
    </div>
    <div class="mt-5 grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-4">
      <div class={`h-16 rounded-xl md:h-[84px] ${bar}`} />
      <div class={`h-16 rounded-xl md:h-[84px] ${bar}`} />
      <div class={`h-16 rounded-xl md:h-[84px] ${bar}`} />
      <div class={`h-16 rounded-xl md:h-[84px] ${bar}`} />
    </div>
    <div class={`mt-7 h-6 w-32 rounded ${bar}`} />
    <div class={`mt-3 h-[300px] rounded-xl ${bar}`} />
  </div>
);

export default TeamProfileSkeleton;
