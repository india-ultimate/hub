import { Navigate, Route } from "@solidjs/router";
import { initFlowbite } from "flowbite";
import {
  children,
  createEffect,
  createResource,
  Match,
  Suspense,
  Switch
} from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import { fetchUserData } from "../utils";

const WithUserData = props => {
  const [store, { userFetchSuccess, userFetchFailure }] = useStore();
  const c = children(() => props.children);
  const [fetch] = createResource(!store.userFetched, () =>
    fetchUserData(userFetchSuccess, userFetchFailure)
  );
  createEffect(() => {
    if (!fetch.loading) {
      // HACK: to ensure initflowbite is actually initialized!!!
      setTimeout(() => initFlowbite(), 100);
      setTimeout(() => initFlowbite(), 500);
      setTimeout(() => initFlowbite(), 1000);
      setTimeout(() => initFlowbite(), 3000);
      setTimeout(() => initFlowbite(), 5000);
      setTimeout(() => initFlowbite(), 8000);
    }
  });

  const canView = () => {
    if (!props.admin) {
      console.log(props.admin);
      return true;
    } else {
      return store.userFetched && store?.data?.is_staff;
    }
  };

  return (
    <Suspense fallback={<Spinner />}>
      {/* NOTE: fetch() doesn't have any real data, but we "read" it to be able to use the Suspense functionality */}
      <Switch>
        <Match
          when={
            fetch() || (store.userFetched && store?.data?.username && canView())
          }
        >
          <>{c()}</>
        </Match>
        <Match
          when={
            fetch() ||
            (store.userFetched && store?.data?.username && !canView())
          }
        >
          <p class="my-12 text-lg text-gray-500 md:text-xl lg:text-2xl">
            Sorry, the page you want to view is only available to admins
          </p>
        </Match>
        <Match when={fetch() || (store.userFetched && !store?.data?.username)}>
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
          <WithUserData admin={props.admin}>{props.element}</WithUserData>
        }
      />
    );
  } else if (props.component) {
    return (
      <Route
        {...props}
        component={null}
        element={
          <WithUserData admin={props.admin}>
            <props.component />
          </WithUserData>
        }
      />
    );
  }
};

export default UserRoute;
