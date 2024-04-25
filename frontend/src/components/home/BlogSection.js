import { A } from "@solidjs/router";
import { For } from "solid-js";

import { ChevronLeft, ChevronRight } from "../../icons";

const BlogSection = () => {
  return (
    <div>
      <div
        id="controls-carousel"
        class="relative w-full"
        data-carousel="static"
      >
        <div class="relative h-96 overflow-hidden rounded-lg md:h-96">
          <For each={data}>
            {a => (
              <div
                id={a.title}
                class="hidden duration-200 ease-in-out"
                data-carousel-item
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

        <div class="flex justify-center md:mt-4">
          <button type="button" class="mr-5" data-carousel-prev>
            <ChevronLeft height={20} width={20} />
          </button>
          <button type="button" class="ml-5" data-carousel-next>
            <ChevronRight height={20} width={20} />
          </button>
        </div>
      </div>
    </div>
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
        class="relative z-10 hidden h-full items-center p-20 before:absolute before:inset-0
            before:z-[-5]
            before:block
            before:bg-black
            before:opacity-50
            before:content-['']
            md:flex"
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
    img: "https://d36m266ykvepgv.cloudfront.net/uploads/media/5Qb87icCfs/o/india-masters.png",
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
