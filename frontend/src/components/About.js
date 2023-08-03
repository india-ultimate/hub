import README from "../../../README.md";
import SolidMarkdown from "solid-markdown";

const About = () => {
  const start = "<!-- about:start -->";
  const end = "<!-- about:end -->";
  const markdown = README.split(start)[1].split(end)[0];
  return <SolidMarkdown children={markdown} />;
};

export default About;
