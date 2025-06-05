import StyledMarkdown from "../StyledMarkdown";

const ChatMessage = props => {
  const isUser = props.type === "USER";

  if (!isUser) {
    return (
      <div class="mb-4 w-full overflow-auto">
        <StyledMarkdown markdown={props.message} />
      </div>
    );
  }

  return (
    <div class="mb-4 flex items-start justify-end">
      <div class="inline-flex flex-col rounded-full bg-blue-600 p-4 text-base text-white">
        {props.message}
      </div>
    </div>
  );
};

export default ChatMessage;
