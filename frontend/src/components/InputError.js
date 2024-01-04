/**
 * Input error that tells the user what to do to fix the problem.
 */
const InputError = props => {
  return (
    <div
      class="pt-4 text-sm text-red-500 md:text-base lg:pt-5 lg:text-lg dark:text-red-400"
      id={`${props.name}-error`}
    >
      {props.error}
    </div>
  );
};
export default InputError;
