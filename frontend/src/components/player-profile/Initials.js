const TINTS = [
  "bg-blue-700 dark:bg-blue-800",
  "bg-green-700 dark:bg-green-800",
  "bg-orange-700 dark:bg-orange-800",
  "bg-teal-700 dark:bg-teal-800",
  "bg-indigo-700 dark:bg-indigo-800",
  "bg-pink-700 dark:bg-pink-800"
];

const initialsOf = name =>
  (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(word => word[0].toUpperCase())
    .join("");

const Initials = props => {
  const tint = () =>
    TINTS[
      [...(props.name || "")].reduce((sum, c) => sum + c.charCodeAt(0), 0) %
        TINTS.length
    ];
  return (
    <span
      class={`flex flex-none items-center justify-center font-bold text-white dark:text-gray-100 ${tint()} ${props.class}`}
    >
      {initialsOf(props.name)}
    </span>
  );
};

export default Initials;
