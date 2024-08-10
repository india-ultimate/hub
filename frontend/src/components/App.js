import { Route, Routes } from "@solidjs/router";
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import { lazy } from "solid-js";

import { useStore } from "../store";
import AnnouncementBanner from "./AnnouncementBanner";
import Footer from "./Footer";
import Header from "./Header";
import HelpButton from "./HelpButton";
import ScrollUpButton from "./ScrollUpButton";
import UserRoute from "./UserRoute";

const About = lazy(() => import("./About"));
const Dashboard = lazy(() => import("./Dashboard"));
const Home = lazy(() => import("./Home"));
const Login = lazy(() => import("./Login"));
const Registration = lazy(() => import("./Registration"));
const Help = lazy(() => import("./Help"));
const Legal = lazy(() => import("./Legal"));
const Membership = lazy(() => import("./membership"));
const GroupMembership = lazy(() => import("./membership/GroupMembership"));
const Vaccination = lazy(() => import("./Vaccination"));
const Accreditation = lazy(() => import("./Accreditation"));
const CommentaryInfo = lazy(() => import("./CommentaryInfo"));
const Waiver = lazy(() => import("./Waiver"));
const UltimateCentralLogin = lazy(() => import("./UltimateCentralLogin"));
const RegisteredPlayerList = lazy(() => import("./RegisteredPlayerList"));
const ValidateRoster = lazy(() => import("./ValidateRoster"));
const ValidateTransactions = lazy(() => import("./ValidateTransactions"));
const Teams = lazy(() => import("./Teams"));
const ViewTeam = lazy(() => import("./teams/View"));
const CreateTeam = lazy(() => import("./teams/Create"));
const TournamentManager = lazy(() => import("./TournamentManager"));
const Tournaments = lazy(() => import("./Tournaments"));
const Tournament = lazy(() => import("./Tournament"));
const TeamRegistration = lazy(() => import("./TeamRegistration"));
const Roster = lazy(() => import("./roster/View"));
const TournamentRules = lazy(() => import("./TournamentRules"));
const TournamentSchedule = lazy(() => import("./TournamentSchedule"));
const TournamentStandings = lazy(() => import("./TournamentStandings"));
const TournamentTeam = lazy(() => import("./TournamentTeam"));
const Error404 = lazy(() => import("./Error404"));
const PhonePeTransaction = lazy(() => import("./PhonePeTransaction"));
const CheckMemberships = lazy(() => import("./CheckMemberships"));
const CollegeID = lazy(() => import("./CollegeID"));

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
          <AnnouncementBanner
            text="New One-Tap Login Launched!"
            cta={{ text: "more", href: "/help" }}
          />
          <section class="grow">
            <div class="mx-auto max-w-screen-xl px-4 py-4 lg:px-6 lg:py-16">
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
                    path={"/tournament/:slug/register/"}
                    component={TeamRegistration}
                  />
                  <Route
                    path={"/tournament/:slug/schedule"}
                    component={TournamentSchedule}
                  />
                  <Route
                    path={"/tournament/:slug/standings"}
                    component={TournamentStandings}
                  />
                  <Route
                    path={"/tournament/:slug/rules"}
                    component={TournamentRules}
                  />
                  <Route
                    path={"/tournament/:tournament_slug/team/:team_slug"}
                    component={TournamentTeam}
                  />
                  {/* Team Public Routes */}
                  <Route path={"/teams"} component={Teams} />
                  <Route path={"/team/:slug"} component={ViewTeam} />
                  {/* Team Private Routes */}
                  <UserRoute path="/teams/new" component={CreateTeam} />
                  {/* Roster Public Route */}
                  <Route
                    path={"/tournament/:tournament_slug/team/:team_slug/roster"}
                    component={Roster}
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
                    path="/college-id/:playerId"
                    component={CollegeID}
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
                  <UserRoute
                    path="/commentary-info/:playerId"
                    component={CommentaryInfo}
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
          <ScrollUpButton />
          <HelpButton />
          <Footer />
        </div>
      </div>
    </QueryClientProvider>
  );
}
