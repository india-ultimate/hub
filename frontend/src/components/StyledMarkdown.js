import remarkGfm from "remark-gfm";
import slug from "slug";
import { onMount } from "solid-js";
import SolidMarkdown from "solid-markdown";

const TailwindMarkdown = props => {
  let divRef;

  const classMap = {
    a: "font-medium text-blue-600 underline dark:text-blue-500 hover:no-underline",
    p: "mb-2",
    h1: "text-2xl font-bold mb-4 text-blue-500 text-center",
    h2: "text-xl font-bold mb-4 text-blue-500 text-center",
    h3: "text-lg font-bold mb-4 underline",
    ol: "m-4 text-gray-500 list-decimal list-outside dark:text-gray-400",
    ul: "m-4 text-gray-500 list-disc list-outside dark:text-gray-400",
    table:
      "w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400 mb-5",
    thead:
      "text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400",
    th: "px-6 py-3",
    "tbody tr": "bg-white border-b dark:bg-gray-800 dark:border-gray-700",
    "tbody td": "px-6 py-4 font-medium"
  };

  onMount(() => {
    // Add CSS classes
    for (let tag in classMap) {
      divRef.querySelectorAll(tag).forEach(el => {
        el.setAttribute("class", classMap[tag]);
      });
    }

    // Add ids to h1 tags
    divRef.querySelectorAll("h1").forEach(el => {
      el.setAttribute("id", slug(el.innerText));
    });
  });

  return (
    <div ref={divRef}>
      <SolidMarkdown remarkPlugins={[remarkGfm]} children={props.markdown} />
    </div>
  );
};

export default TailwindMarkdown;
