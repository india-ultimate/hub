import README from "../../../README.md";
import StyledMarkdown from "./StyledMarkdown";

const About = () => {
  const start = "<!-- about:start -->";
  const end = "<!-- about:end -->";
  const markdown = README.split(start)[1].split(end)[0];
  return <StyledMarkdown markdown={markdown} />;
};

export default About;
