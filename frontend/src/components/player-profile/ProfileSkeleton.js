const bar = "bg-gray-200 dark:bg-gray-700";

const ProfileSkeleton = () => (
  <div
    class="animate-pulse motion-reduce:animate-none"
    role="status"
    aria-label="Loading player"
  >
    <div class={`h-8 w-48 rounded-full ${bar}`} />
    <div class="mt-4 rounded-2xl border border-gray-200 p-5 dark:border-gray-700 md:flex md:items-center md:gap-8 md:p-6">
      <div
        class={`mx-auto h-24 w-24 flex-none rounded-full md:mx-0 md:h-32 md:w-32 ${bar}`}
      />
      <div class="md:flex-1">
        <div class={`mx-auto mt-4 h-7 w-40 rounded md:mx-0 md:mt-0 ${bar}`} />
        <div class={`mx-auto mt-3 h-4 w-52 rounded md:mx-0 ${bar}`} />
      </div>
    </div>
    <div class="mt-5 grid grid-cols-6 gap-2 md:grid-cols-5 md:gap-4">
      <div
        class={`col-span-2 h-16 rounded-xl md:col-span-1 md:h-[84px] ${bar}`}
      />
      <div
        class={`col-span-2 h-16 rounded-xl md:col-span-1 md:h-[84px] ${bar}`}
      />
      <div
        class={`col-span-2 h-16 rounded-xl md:col-span-1 md:h-[84px] ${bar}`}
      />
      <div
        class={`col-span-3 h-16 rounded-xl md:col-span-1 md:h-[84px] ${bar}`}
      />
      <div
        class={`col-span-3 h-16 rounded-xl md:col-span-1 md:h-[84px] ${bar}`}
      />
    </div>
    <div class="mt-6 grid gap-3 md:grid-cols-2 md:gap-4">
      <div class={`h-28 rounded-xl ${bar}`} />
      <div class={`hidden h-28 rounded-xl md:block ${bar}`} />
    </div>
  </div>
);

export default ProfileSkeleton;
