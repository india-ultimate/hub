import { lazy } from "solid-js";
import { Routes, Route } from "@solidjs/router";
import Header from "./Header";
import Footer from "./Footer";

const About = lazy(() => import("./About"));
const Home = lazy(() => import("./Home"));
const EmailLink = lazy(() => import("./EmailLink"));
const Login = lazy(() => import("./Login"));
const Registration = lazy(() => import("./Registration"));
const Membership = lazy(() => import("./Membership"));
const GroupMembership = lazy(() => import("./GroupMembership"));
const Vaccination = lazy(() => import("./Vaccination"));
const Waiver = lazy(() => import("./Waiver"));
const UltimateCentralLogin = lazy(() => import("./UltimateCentralLogin"));
const RegisteredPlayerList = lazy(() => import("./RegisteredPlayerList"));

const filters = {
  id: /^\d+$/ // only allow numbers
};

export default function App() {
  return (
    <div class="bg-white dark:bg-gray-900 min-h-screen">
      <Header />
      <section>
        <div class="py-8 px-4 mx-auto max-w-screen-xl lg:py-16 lg:px-6">
          <div class="max-w-screen-lg text-gray-500 sm:text-lg dark:text-gray-400">
            <Routes>
              {/* Simple pages */}
              <Route path="/" component={Home} />
              <Route path="/about" component={About} />
              {/* Login related routes */}
              <Route path="/login" component={Login} />
              <Route path="/email-link" component={EmailLink} />
              {/* Registration routes */}
              <Route path="/registration/me" component={Registration} />
              <Route
                path="/registration/others"
                element={<Registration others={true} />}
              />
              <Route
                path="/registration/ward"
                element={<Registration ward={true} />}
              />
              {/* Membership, vaccination, waiver, etc. */}
              <Route path="/membership/group" component={GroupMembership} />
              <Route
                path="/membership/:playerId"
                component={Membership}
                matchFilters={filters}
              />
              <Route
                path="/vaccination/:playerId"
                component={Vaccination}
                matchFilters={filters}
              />
              <Route
                path="/waiver/:playerId"
                component={Waiver}
                matchFilters={filters}
              />
              <Route
                path="/uc-login/:playerId"
                component={UltimateCentralLogin}
                matchFilters={filters}
              />
              {/* Admin routes */}
              <Route path="/players" component={RegisteredPlayerList} />
            </Routes>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
