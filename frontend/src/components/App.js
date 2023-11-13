import { lazy } from "solid-js";
import { Routes, Route } from "@solidjs/router";
import Header from "./Header";
import Footer from "./Footer";
import UserRoute from "./UserRoute";
import { useStore } from "../store";
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";

const About = lazy(() => import("./About"));
const Dashboard = lazy(() => import("./Dashboard"));
const Home = lazy(() => import("./Home"));
const Login = lazy(() => import("./Login"));
const Registration = lazy(() => import("./Registration"));
const Help = lazy(() => import("./Help"));
const Legal = lazy(() => import("./Legal"));
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
const Error404 = lazy(() => import("./Error404"));
const PhonePeTransaction = lazy(() => import("./PhonePeTransaction"));
const CheckMemberships = lazy(() => import("./CheckMemberships"));

const filters = {
  id: /^\d+$/ // only allow numbers
};

const queryClient = new QueryClient();

export default function App() {
  const [store] = useStore();
  return (
    <QueryClientProvider client={queryClient}>
      <div class={store.theme === "dark" ? "dark" : ""}>
        <div class="flex min-h-screen flex-col bg-white dark:bg-gray-900">
          <Header />
          <section class="grow">
            <div class="mx-auto max-w-screen-xl px-4 py-8 lg:px-6 lg:py-16">
              <div class="text-gray-500 dark:text-gray-400 sm:text-lg">
                <Routes>
                  {/* Simple pages */}
                  <Route path="/" component={Home} />
                  <Route path="/about" component={About} />
                  <UserRoute path="/dashboard" component={Dashboard} />
                  {/* Login related routes */}
                  <Route path="/login" component={Login} />
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
                  <Route path="/legal" component={Legal} />
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
                  {/* Transaction */}
                  <UserRoute
                    path="/phonepe-transaction/:transactionId"
                    component={PhonePeTransaction}
                  />
                  <UserRoute
                    path="/validate-rosters"
                    component={ValidateRoster}
                  />
                  {/* Admin routes */}
                  <UserRoute
                    path="/players"
                    component={RegisteredPlayerList}
                    admin={true}
                  />
                  <UserRoute
                    path="/validate-transactions"
                    component={ValidateTransactions}
                    admin={true}
                  />
                  <UserRoute
                    path="/check-memberships"
                    component={CheckMemberships}
                    admin={true}
                  />
                  <UserRoute
                    path="/tournament-manager"
                    component={TournamentManager}
                    admin={true}
                  />
                  <Route path="*" component={Error404} />
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
