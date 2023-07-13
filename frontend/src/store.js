import { createSignal, createContext, useContext } from "solid-js";
import { createStore } from "solid-js/store";

const StoreContext = createContext();

export const StoreProvider = props => {
  const [store, setStore] = createStore({ loggedIn: false, data: {} });
  const setLoggedIn = flag => setStore("loggedIn", flag);
  const setData = data => setStore("data", data);
  const setPlayerById = player => {
    const searchPlayer = data => {
      if (data?.player?.id === player.id) {
        return "player";
      } else {
        // FIXME: Implement updating a player in players list.
      }
    };
    setStore("data", "player", player);
  };
  const data = [store, { setStore, setLoggedIn, setData, setPlayerById }];

  return (
    <StoreContext.Provider value={data}>{props.children}</StoreContext.Provider>
  );
};

export const useStore = () => {
  return useContext(StoreContext);
};
