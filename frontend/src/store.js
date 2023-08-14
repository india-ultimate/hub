import { createContext, useContext } from "solid-js";
import { createStore } from "solid-js/store";

const StoreContext = createContext();

export const StoreProvider = props => {
  const [store, setStore] = createStore({ loggedIn: false, data: {}, theme: getDefaultTheme() });
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
  const addWard = player => {
    setStore("data", "wards", w => [...w, player]);
  };
  const setTheme = theme => {
    setStore("theme", theme);
    localStorage.setItem("theme", theme);
  }
  const data = [
    store,
    { setStore, setLoggedIn, setData, setPlayer, setPlayerById, addWard, setTheme }
  ];

  return (
    <StoreContext.Provider value={data}>{props.children}</StoreContext.Provider>
  );
};

export const useStore = () => {
  return useContext(StoreContext);
};

const getDefaultTheme = () => {
  let theme;
  if (localStorage.getItem("theme")) {
    theme = localStorage.getItem("theme");
  } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    theme = "dark";
    localStorage.setItem("theme", "dark");
  } else {
    theme = "light";
    localStorage.setItem("theme", "light");
  }
  return theme;
}
