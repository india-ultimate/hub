import { createSignal, createContext, useContext } from "solid-js";
import { createStore } from "solid-js/store";

const StoreContext = createContext();

export const StoreProvider = props => {
  const [store, setStore] = createStore({ loggedIn: false, data: {} });
  const setLoggedIn = flag => setStore("loggedIn", flag);
  const setData = data => setStore("data", data);
  const setPlayer = player => {
    setStore("data", "player", player);
  };
  const setPlayerById = player => {
    if (store.data.player?.id === player.id) {
      setStore("data", "player", player);
    } else {
      const wardIndex = store.data.wards?.findIndex(w => w.id === player.id);
      if (wardIndex > -1) {
        setStore("data", "wards", wardIndex, player);
      } else {
        console.log("Could not find ward");
      }
    }
  };
  const data = [
    store,
    { setStore, setLoggedIn, setData, setPlayer, setPlayerById }
  ];

  return (
    <StoreContext.Provider value={data}>{props.children}</StoreContext.Provider>
  );
};

export const useStore = () => {
  return useContext(StoreContext);
};
