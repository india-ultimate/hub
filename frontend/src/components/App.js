import { lazy } from "solid-js";
import { Routes, Route } from "@solidjs/router";
import Header from "./Header";
import Footer from "./Footer";
import UserRoute from "./UserRoute";
import { useStore } from "../store";
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";

const About = lazy(() => import("./About"));
const Dashboard = lazy(() => import("./Dashboard"));
const EmailLink = lazy(() => import("./EmailLink"));
const Home = lazy(() => import("./Home"));
const Login = lazy(() => import("./Login"));
const Registration = lazy(() => import("./Registration"));
const Help = lazy(() => import("./Help"));
const Membership = lazy(() => import("./Membership"));
const GroupMembership = lazy(() => import("./GroupMembership"));
const Vaccination = lazy(() => import("./Vaccination"));
const Accreditation = lazy(() => import("./Accreditation"));
const Waiver = lazy(() => import("./Waiver"));
const UltimateCentralLogin = lazy(() => import("./UltimateCentralLogin"));
const RegisteredPlayerList = lazy(() => import("./RegisteredPlayerList"));
const ValidateRoster = lazy(() => import("./ValidateRoster"));
const ValidateTransactions = lazy(() => import("./ValidateTransactions"));
const TournamentManager = lazy(() => import("./TournamentManager"));
const Tournaments = lazy(() => import("./Tournaments"));
const Tournament = lazy(() => import("./Tournament"));
const TournamentSchedule = lazy(() => import("./TournamentSchedule"));
const TournamentStandings = lazy(() => import("./TournamentStandings"));
const TournamentTeam = lazy(() => import("./TournamentTeam"));

const filters = {
  id: /^\d+$/ // only allow numbers
};

const queryClient = new QueryClient();

export default function App() {
  const [store] = useStore();
  return (
    <QueryClientProvider client={queryClient}>
      <div class={store.theme === "dark" ? "dark" : ""}>
        <div class="bg-white dark:bg-gray-900 min-h-screen flex flex-col">
          <Header />
          <section class="grow">
            <div class="py-8 px-4 mx-auto max-w-screen-xl lg:py-16 lg:px-6">
              <div class="text-gray-500 sm:text-lg dark:text-gray-400">
                <Routes>
                  {/* Simple pages */}
                  <Route path="/" component={Home} />
                  <Route path="/about" component={About} />
                  <UserRoute path="/dashboard" component={Dashboard} />
                  {/* Login related routes */}
                  <Route path="/login" component={Login} />
                  <Route path="/email-link" component={EmailLink} />
                  {/* Tournament Public Routes */}
                  <Route path={"/tournaments"} component={Tournaments} />
                  <Route path={"/tournament/:slug"} component={Tournament} />
                  <Route
                    path={"/tournament/:slug/schedule"}
                    component={TournamentSchedule}
                  />
                  <Route
                    path={"/tournament/:slug/standings"}
                    component={TournamentStandings}
                  />
                  <Route
                    path={"/tournament/:tournament_slug/team/:team_slug"}
                    component={TournamentTeam}
                  />
                  {/* Registration routes */}
                  <UserRoute path="/registration/me" component={Registration} />
                  <UserRoute
                    path="/edit/registration/:playerId"
                    component={Registration}
                    matchFilters={filters}
                  />
                  <UserRoute
                    path="/registration/others"
                    element={<Registration others={true} />}
                  />
                  <UserRoute
                    path="/registration/ward"
                    element={<Registration ward={true} />}
                  />
                  <Route path="/help" component={Help} />
                  {/* Membership, vaccination, waiver, etc. */}
                  <UserRoute
                    path="/membership/group"
                    component={GroupMembership}
                  />
                  <UserRoute
                    path="/membership/:playerId"
                    component={Membership}
                    matchFilters={filters}
                  />
                  <UserRoute
                    path="/vaccination/:playerId"
                    component={Vaccination}
                    matchFilters={filters}
                  />
                  <UserRoute
                    path="/accreditation/:playerId"
                    component={Accreditation}
                    matchFilters={filters}
                  />
                  <UserRoute
                    path="/waiver/:playerId"
                    component={Waiver}
                    matchFilters={filters}
                  />
                  <UserRoute
                    path="/uc-login/:playerId"
                    component={UltimateCentralLogin}
                    matchFilters={filters}
                  />
                  {/* Admin routes */}
                  <UserRoute path="/players" component={RegisteredPlayerList} />
                  <UserRoute
                    path="/validate-rosters"
                    component={ValidateRoster}
                  />
                  <UserRoute
                    path="/validate-transactions"
                    component={ValidateTransactions}
                  />
                  <UserRoute
                    path="/tournament-manager"
                    component={TournamentManager}
                  />
                </Routes>
              </div>
            </div>
          </section>
          <Footer />
        </div>
      </div>
    </QueryClientProvider>
  );
}
