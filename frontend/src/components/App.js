import { createSignal } from "solid-js";

import LoginButton from "./LoginButton";

const App = () => {
  const [count, setCount] = createSignal(0);

  return (
    <div>
      <h1>Welcome to India Ultimate Hub!</h1>
      <LoginButton />
    </div>
  );
};

export default App;
