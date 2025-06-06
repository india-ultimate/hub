import { Route, Routes } from "@solidjs/router";
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import { lazy } from "solid-js";

import { useStore } from "../store";
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
const TermsAndConditions = lazy(() => import("./TermsAndConditions"));
const PrivacyPolicy = lazy(() => import("./PrivacyPolicy"));
const ContactUs = lazy(() => import("./ContactUs"));
const Membership = lazy(() => import("./membership"));
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
const EditTeam = lazy(() => import("./teams/Edit"));
const CreateTeam = lazy(() => import("./teams/Create"));
const TournamentManager = lazy(() => import("./TournamentManager"));
const Tournaments = lazy(() => import("./Tournaments"));
const Tournament = lazy(() => import("./Tournament"));
const TeamRegistration = lazy(() => import("./TeamRegistration"));
const Roster = lazy(() => import("./roster/View"));
const TournamentRules = lazy(() => import("./TournamentRules"));
const TournamentSchedule = lazy(() => import("./TournamentSchedule"));
const TournamentStandings = lazy(() => import("./TournamentStandings"));
const TournamentLeaderboard = lazy(() => import("./tournament/Leaderboard"));
const TournamentTeam = lazy(() => import("./TournamentTeam"));
const Error404 = lazy(() => import("./Error404"));
const PhonePeTransaction = lazy(() => import("./PhonePeTransaction"));
const CheckMemberships = lazy(() => import("./CheckMemberships"));
const CollegeID = lazy(() => import("./CollegeID"));
const AllSeries = lazy(() => import("./series/index"));
const Series = lazy(() => import("./series/Series"));
const SeriesRoster = lazy(() => import("./series/SeriesRoster"));
// const EditStats = lazy(() => import("./match/stats/EditStats"));
const EditStatsMin = lazy(() => import("./match/stats/EditMinStats"));
const ViewStats = lazy(() => import("./match/stats/ViewStats"));
const EmailInvitationHandler = lazy(() =>
  import("./series/InvitationViaEmail")
);
// Ticket Pages
const Tickets = lazy(() => import("./ticket/Tickets"));
const CreateTicket = lazy(() => import("./ticket/CreateTicket"));
const TicketDetail = lazy(() => import("./ticket/TicketDetail"));

const filters = {
  id: /^\d+$/ // only allow numbers
};
// Election Pages
const ElectionManager = lazy(() => import("./election/ElectionManager"));
const ElectionsPage = lazy(() => import("./election/ElectionsPage"));
const ElectionPage = lazy(() => import("./election/ElectionPage"));

// Chat Pages
const ChatPage = lazy(() => import("./chat/ChatPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60000, // 1 minute default stale time
      refetchOnWindowFocus: false,
      retry: false
    }
  }
});

export default function App() {
  const [store] = useStore();
  return (
    <QueryClientProvider client={queryClient}>
      <div class={store.theme === "dark" ? "dark" : ""}>
        <div class="flex min-h-screen flex-col bg-white dark:bg-gray-900">
          <Header />
          {/* <AnnouncementBanner
            text="New One-Tap Login Launched!"
            cta={{ text: "more", href: "/help" }}
          /> */}
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
                  {/* Series routes */}
                  <Route path="/series" component={AllSeries} />
                  <Route path="/series/:slug" component={Series} />
                  <Route
                    path="/series/:series_slug/team/:team_slug"
                    component={SeriesRoster}
                  />
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
                    path={"/tournament/:slug/leaderboard"}
                    component={TournamentLeaderboard}
                  />
                  <Route
                    path={"/tournament/:slug/rules"}
                    component={TournamentRules}
                  />
                  <Route
                    path={"/tournament/:tournament_slug/team/:team_slug"}
                    component={TournamentTeam}
                  />
                  <Route
                    path="/tournament/:tournamentSlug/match/:matchId/live"
                    component={ViewStats}
                  />
                  <Route
                    path="/invitation/accept"
                    component={EmailInvitationHandler}
                  />
                  <Route
                    path="/invitation/decline"
                    component={EmailInvitationHandler}
                  />
                  {/* Team Public Routes */}
                  <Route path={"/teams"} component={Teams} />
                  <Route path={"/team/:slug"} component={ViewTeam} />
                  {/* Team Private Routes */}
                  <UserRoute path="/teams/new" component={CreateTeam} />
                  <UserRoute path="/team/:slug/edit" component={EditTeam} />
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
                  <Route
                    path="/terms-and-conditions"
                    component={TermsAndConditions}
                  />
                  <Route path="/privacy-policy" component={PrivacyPolicy} />
                  <Route path="/contact-us" component={ContactUs} />
                  {/* Membership, vaccination, waiver, etc. */}
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
                  {/* <UserRoute
                    path="/tournament/:tournamentSlug/match/:matchId/edit-stats"
                    component={EditStats}
                  /> */}
                  <UserRoute
                    path="/tournament/:tournamentSlug/match/:matchId/edit-stats-min"
                    component={EditStatsMin}
                  />
                  {/* Ticket public routes */}
                  <Route path="/tickets" component={Tickets} />
                  {/* Ticket private routes */}
                  <UserRoute path="/tickets/new" component={CreateTicket} />
                  <UserRoute
                    path="/tickets/:id"
                    component={TicketDetail}
                    matchFilters={filters}
                  />
                  {/* Election public routes */}
                  <Route path="/elections" component={ElectionsPage} />
                  <Route path="/election/:id" component={ElectionPage} />
                  {/* Election private routes */}
                  <UserRoute
                    path="/election-manager"
                    component={ElectionManager}
                    admin={true}
                  />
                  {/* Chat */}
                  <UserRoute path="/chat" component={ChatPage} />
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
