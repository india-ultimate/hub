import { lazy } from "solid-js";
import { Routes, Route } from "@solidjs/router";
const Login = lazy(() => import("./Login"));
const Home = lazy(() => import("./Home"));

export default function App() {
  return (
    <div>
      <h1>Welcome to India Ultimate Hub!</h1>
      <Routes>
        <Route path="/login" component={Login} />
        <Route path="/" component={Home} />
        <Route
          path="/about"
          element={<div>This site was made with Solid</div>}
        />
      </Routes>
    </div>
  );
}
