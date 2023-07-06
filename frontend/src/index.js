import { render } from "solid-js/web";
import { Router, hashIntegration } from "@solidjs/router";
import App from "./components/App";
import "./index.css";
import "flowbite";

render(
  () => (
    <Router source={hashIntegration()}>
      <App />
    </Router>
  ),
  document.getElementById("root")
);
