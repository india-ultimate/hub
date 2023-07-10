import { render } from "solid-js/web";
import { Router, hashIntegration } from "@solidjs/router";
import App from "./components/App";
import "./index.css";
import "flowbite";
import { StoreProvider } from "./store";

render(
  () => (
    <StoreProvider>
      <Router source={hashIntegration()}>
        <App />
      </Router>
    </StoreProvider>
  ),
  document.getElementById("root")
);
