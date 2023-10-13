import SolidMarkdown from "solid-markdown";
import { onMount, createEffect } from "solid-js";

const TailwindMarkdown = props => {
  let divRef;

  const classMap = {
    a: "font-medium text-blue-600 underline dark:text-blue-500 hover:no-underline",
    p: "mb-2"
  };

  onMount(() => {
    for (let tag in classMap) {
      divRef.querySelectorAll(tag).forEach(el => {
        el.setAttribute("class", classMap[tag]);
      });
    }
  });

  return (
    <div ref={divRef}>
      <SolidMarkdown children={props.markdown} />
    </div>
  );
};

export default TailwindMarkdown;
