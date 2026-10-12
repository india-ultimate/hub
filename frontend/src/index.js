import "./index.css";

import { Router } from "@solidjs/router";
import { render } from "solid-js/web";

import App from "./components/App";
import { StoreProvider } from "./store";

render(
  () => (
    <StoreProvider>
      <Router>
        <App />
      </Router>
    </StoreProvider>
  ),
  document.getElementById("root")
);
