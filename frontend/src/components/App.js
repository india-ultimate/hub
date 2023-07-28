import { lazy } from "solid-js";
import { Routes, Route } from "@solidjs/router";
import Header from "./Header";
import Footer from "./Footer";

const EmailLink = lazy(() => import("./EmailLink"));
const Home = lazy(() => import("./Home"));
const Login = lazy(() => import("./Login"));
const Registration = lazy(() => import("./Registration"));
const Membership = lazy(() => import("./Membership"));
const GroupMembership = lazy(() => import("./GroupMembership"));

const filters = {
  id: /^\d+$/ // only allow numbers
};

export default function App() {
  return (
    <div>
      <Header />
      <section class="bg-white dark:bg-gray-900">
        <div class="py-8 px-4 mx-auto max-w-screen-xl lg:py-16 lg:px-6">
          <div class="max-w-screen-lg text-gray-500 sm:text-lg dark:text-gray-400">
            <Routes>
              <Route path="/login" component={Login} />
              <Route path="/registration/me" component={Registration} />
              <Route
                path="/registration/others"
                element={<Registration others={true} />}
              />
              <Route
                path="/registration/ward"
                element={<Registration ward={true} />}
              />
              <Route path="/" component={Home} />
              <Route path="/email-link" component={EmailLink} />
              <Route path="/membership/group" component={GroupMembership} />
              <Route
                path="/membership/:playerId"
                component={Membership}
                matchFilters={filters}
              />
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
