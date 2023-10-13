import SolidMarkdown from "solid-markdown";
import { onMount } from "solid-js";
import slug from "slug";

const TailwindMarkdown = props => {
  let divRef;

  const classMap = {
    a: "font-medium text-blue-600 underline dark:text-blue-500 hover:no-underline",
    p: "mb-2",
    h1: "text-2xl font-bold mb-4 text-blue-500",
    ol: "m-4 text-gray-500 list-decimal list-outside dark:text-gray-400"
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
      <SolidMarkdown children={props.markdown} />
    </div>
  );
};

export default TailwindMarkdown;
