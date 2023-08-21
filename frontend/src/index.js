import { render } from "solid-js/web";
import { Router } from "@solidjs/router";
import App from "./components/App";
import "./index.css";
import "flowbite";
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
