import { createSignal, createContext, useContext } from "solid-js";
import { createStore } from "solid-js/store";

const StoreContext = createContext();

export const StoreProvider = props => {
  const [store, setStore] = createStore({ loggedIn: false, data: {} });
  const setLoggedIn = flag => setStore("loggedIn", flag);
  const setData = data => setStore("data", data);
  const data = [store, { setStore, setLoggedIn, setData }];

  return (
    <StoreContext.Provider value={data}>{props.children}</StoreContext.Provider>
  );
};

export const useStore = () => {
  return useContext(StoreContext);
};
