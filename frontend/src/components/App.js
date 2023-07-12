import { lazy } from "solid-js";
import { Routes, Route } from "@solidjs/router";
import Header from "./Header";
import Footer from "./Footer";

const EmailLink = lazy(() => import("./EmailLink"));
const Home = lazy(() => import("./Home"));
const Login = lazy(() => import("./Login"));
const Registration = lazy(() => import("./Registration"));

export default function App() {
  return (
    <div>
      <Header />
      <section class="bg-white dark:bg-gray-900">
        <div class="py-8 px-4 mx-auto max-w-screen-xl lg:py-16 lg:px-6">
          <div class="max-w-screen-lg text-gray-500 sm:text-lg dark:text-gray-400">
            <Routes>
              <Route path="/login" component={Login} />
              <Route path="/registration" component={Registration} />
              <Route path="/" component={Home} />
              <Route path="/email-link" component={EmailLink} />
              <Route
                path="/about"
                element={<div>This site was made with Django and Solid</div>}
              />
            </Routes>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
