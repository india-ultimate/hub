import { Navigate, Route } from "@solidjs/router";
import { children, createResource, Match, Suspense, Switch } from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import { canManageTournaments, fetchUserData } from "../utils";

const WithUserData = props => {
  const [store, { userFetchSuccess, userFetchFailure }] = useStore();
  const c = children(() => props.children);
  const [userData] = createResource(!store.userFetched, () =>
    fetchUserData(userFetchSuccess, userFetchFailure)
  );

  const canView = () => {
    if (props.staffOrDirector) {
      return store.userFetched && canManageTournaments(store?.data);
    }
    if (props.poster) {
      return store.userFetched && store?.data?.can_post_announcements;
    }
    if (props.creator) {
      return store.userFetched && store?.data?.can_create_forms;
    }
    if (!props.admin) {
      return true;
    }
    return store.userFetched && store?.data?.is_staff;
  };

  return (
    <Suspense fallback={<Spinner />}>
      {/* NOTE: userData() doesn't have any real data, but we "read" it to be able to use the Suspense functionality */}
      <Switch>
        <Match
          when={
            userData() ||
            (store.userFetched && store?.data?.username && canView())
          }
        >
          <>{c()}</>
        </Match>
        <Match
          when={
            userData() ||
            (store.userFetched && store?.data?.username && !canView())
          }
        >
          <p class="my-12 text-lg text-gray-500 md:text-xl lg:text-2xl">
            Sorry, you do not have access to this page
          </p>
        </Match>
        <Match
          when={userData() || (store.userFetched && !store?.data?.username)}
        >
          <Navigate href="/login" />
        </Match>
      </Switch>
    </Suspense>
  );
};

const UserRoute = props => {
  if (props.element) {
    return (
      <Route
        {...props}
        component={null}
        element={
          <WithUserData
            admin={props.admin}
            staffOrDirector={props.staffOrDirector}
            poster={props.poster}
            creator={props.creator}
          >
            {props.element}
          </WithUserData>
        }
      />
    );
  } else if (props.component) {
    return (
      <Route
        {...props}
        component={null}
        element={
          <WithUserData
            admin={props.admin}
            staffOrDirector={props.staffOrDirector}
            poster={props.poster}
            creator={props.creator}
          >
            <props.component />
          </WithUserData>
        }
      />
    );
  }
};

export default UserRoute;
