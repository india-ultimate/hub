import { fetchUserData } from "../utils";
import { useStore } from "../store";
import {
  createEffect,
  Switch,
  Match,
  children,
  Suspense,
  createResource
} from "solid-js";
import { Route, Navigate } from "@solidjs/router";
import { initFlowbite } from "flowbite";
import { Spinner } from "../icons";

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

  return (
    <Suspense fallback={<Spinner />}>
      {/* NOTE: fetch() doesn't have any real data, but we "read" it to be able to use the Suspense functionality */}
      <Switch>
        <Match when={fetch() || (store.userFetched && store?.data?.username)}>
          <>{c()}</>
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
        element={<WithUserData>{props.element}</WithUserData>}
      />
    );
  } else if (props.component) {
    return (
      <Route
        {...props}
        component={null}
        element={
          <WithUserData>
            <props.component />
          </WithUserData>
        }
      />
    );
  }
};

export default UserRoute;
