import { A } from "@solidjs/router";
import clsx from "clsx";
import { createSignal, For } from "solid-js";

import { ChevronLeft, ChevronRight } from "../../icons";

const BlogSection = () => {
  const [current, setCurrent] = createSignal(0);
  const step = by => setCurrent(i => (i + by + data.length) % data.length);

  return (
    <section aria-roledescription="carousel" aria-label="Announcements">
      <div class="relative h-96 overflow-hidden rounded-lg md:h-96">
        <For each={data}>
          {(a, i) => (
            <div
              role="group"
              aria-roledescription="slide"
              aria-label={`${i() + 1} of ${data.length}`}
              class={clsx("h-full", current() !== i() && "hidden")}
            >
              <BlogCard
                title={a.title}
                category={a.category}
                img={a.img}
                link={a.link}
                body={a.body}
              />
            </div>
          )}
        </For>
      </div>

      <div class="flex justify-center gap-2 md:mt-4">
        <button
          type="button"
          aria-label="Previous announcement"
          class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-gray-700 hover:bg-gray-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 dark:text-gray-200 dark:hover:bg-gray-700 dark:focus-visible:ring-blue-800"
          onClick={() => step(-1)}
        >
          <ChevronLeft height={20} width={20} />
        </button>
        <button
          type="button"
          aria-label="Next announcement"
          class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-gray-700 hover:bg-gray-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 dark:text-gray-200 dark:hover:bg-gray-700 dark:focus-visible:ring-blue-800"
          onClick={() => step(1)}
        >
          <ChevronRight height={20} width={20} />
        </button>
      </div>
    </section>
  );
};

const BlogCard = props => {
  return (
    <div class="h-full">
      <div class="rounded-lg bg-gray-100 p-4 md:hidden">
        <img src={props.img} class="h-32 w-full rounded-lg object-cover" />
        <h3 class="mt-2 text-sm font-bold text-gray-600">{props.category}</h3>
        <h2 class="mt-2 text-lg font-extrabold text-gray-700">{props.title}</h2>
        <p class="mt-2 line-clamp-4 text-sm">{props.body}</p>
        <A
          href={props.link || ""}
          target="_blank"
          class="mt-2 block w-fit rounded-md bg-yellow-300 px-4 py-1 font-bold text-gray-700"
        >
          View
        </A>
      </div>
      <div
        style={{
          "background-image": "url(" + props.img + ")",
          "background-position": "center",
          "background-size": "cover",
          "background-repeat": "no-repeat"
        }}
        class="relative z-10 hidden h-full items-center p-20 before:absolute before:inset-0 before:z-[-5] before:block before:bg-black before:opacity-50 before:content-[''] md:flex"
      >
        <div class="w-1/2">
          <h3 class="text-md mt-2 text-white">{props.category}</h3>
          <h2 class="mt-2 text-3xl font-bold text-white">{props.title}</h2>
          <p class="mt-2 line-clamp-3 text-sm text-gray-200">{props.body}</p>
          <A
            href={props.link || ""}
            target="_blank"
            class="mt-2 block w-fit rounded-md bg-yellow-300 px-4 py-1 font-bold text-gray-700"
          >
            View
          </A>
        </div>
      </div>
    </div>
  );
};

const data = [
  {
    title: "Team India (Mixed) for AOBUC 2024",
    category: "National Team Announcement",
    img: "https://d36m266ykvepgv.cloudfront.net/uploads/media/f0u5SOK1cg/o/aoubc-2024-jpg-2-3714-3-2049.jpg",
    link: "https://indiaultimate.org/en_in/p/national-team-announcement-team-india-mixed-for-aobuc-2024",
    body: "India Ultimate's National Teams Committee is happy to announce the Head Coach, Manager and final list of athletes selected to represent Team India in the Mixed division at the WFDF 2024 Asia Oceanic Beach Ultimate Championships from 12-16 June, 2024 in Shirahama, Japan."
  },
  {
    title: "Team India (Mixed) for WUC 2024",
    category: "National Team Announcement",
    img: "https://d36m266ykvepgv.cloudfront.net/uploads/media/WWrQgHecGp/o/img-1459.jpg",
    link: "https://indiaultimate.org/en_in/p/national-team-announcement-team-india-mixed-for-wuc-2024",
    body: "India Ultimate's National Teams Committee is happy to announce the Head Coach, Manager and final list of athletes selected to represent Team India in the Mixed division at the WFDF 2024 World Ultimate Championships from 31 August - 7 September, 2024"
  },
  {
    title: "Immediate Coaching Opportunity in Meghalaya",
    category: "Coaching Opportunity",
    img: "https://d36m266ykvepgv.cloudfront.net/uploads/media/S6JmCXc1zn/s-1170-780/dsc-3469-4.jpg",
    link: "https://indiaultimate.org/en_in/p/immediate-coaching-opportunity-in-meghalaya-may-2024",
    body: "India Ultimate has partnered with Sauramandala Foundation (SMF), an NGO that works with community engagement in rural areas - to introduce Ultimate Frisbee in Meghalaya."
  }
];

export default BlogSection;
