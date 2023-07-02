import { createSignal } from "solid-js";

const App = () => {
  const [count, setCount] = createSignal(0);

  return (
    <div>
      <h1>Welcome to India Ultimate Hub!</h1>
    </div>
  );
};

export default App;
