import { A } from "@solidjs/router";

const BlogSection = () => {
  return (
    <div>
      <BlogCard />
      <div class="flex justify-center">
        <span class="me-3 flex h-3 w-3 rounded-full bg-gray-900 dark:bg-gray-700" />
      </div>
    </div>
  );
};

const BlogCard = () => {
  return (
    <div class="rounded-lg bg-gray-100 p-4">
      <img
        src="https://d36m266ykvepgv.cloudfront.net/uploads/media/5Qb87icCfs/o/india-masters.png"
        class="h-32 w-full rounded-lg object-cover"
      />
      <h3 class="mt-2 text-sm font-bold text-gray-600">
        National Team Announcement
      </h3>
      <h2 class="mt-2 text-lg font-extrabold text-gray-700">
        Team India (Mixed Masters) for WMUC 2024
      </h2>
      <p class="mt-2 line-clamp-3 text-sm">
        India Ultimate's National Teams Committee is happy to announce the Head
        Coach and final list of athletes selected to represent Team India in the
        Mixed division at the WFDF 2024 World Masters Ultimate Championships
        from&nbsp;9th-16th November, 2024 |&nbsp;Irvine, California, USA.
      </p>
      <A
        href="/"
        class="mt-2 block w-fit rounded-md bg-yellow-300 px-4 py-1 font-bold text-gray-700"
      >
        View
      </A>
    </div>
  );
};

export default BlogSection;
