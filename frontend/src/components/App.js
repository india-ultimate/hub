import { lazy } from "solid-js";
import { Routes, Route } from "@solidjs/router";
import Header from "./Header";
import Footer from "./Footer";
const Login = lazy(() => import("./Login"));
const Home = lazy(() => import("./Home"));

export default function App() {
  return (
    <div>
      <Header />
      <div>
        <Routes>
          <Route path="/login" component={Login} />
          <Route path="/" component={Home} />
          <Route
            path="/about"
            element={<div>This site was made with Solid</div>}
          />
        </Routes>
      </div>
      <Footer />
    </div>
  );
}
