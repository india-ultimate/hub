import { useNavigate } from "@solidjs/router";
import { createSignal, createEffect } from "solid-js";

const Home = () => {
  // FIXME: store this information in a solidjs store, instead!
  const [loggedIn, setLoggedIn] = createSignal(true);
  const [data, setData] = createSignal({});

  createEffect(() => {
    if (!loggedIn()) {
      const navigate = useNavigate();
      navigate("/login", { replace: true });
    }
  });

  const response = fetch("/api/user", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  })
    .then(response => {
      if (response.status == 200) {
        setLoggedIn(true);
        response.json().then(data => {
          console.log(data);
          setData(data);
        });
      } else {
        setLoggedIn(false);
      }
    })
    .catch(error => {
      console.log(error);
      setLoggedIn(false);
    });
  return (
    <div>
      <h1 class="text-4xl font-bold mb-4 text-red-500">
        Welcome, {data().username}!
      </h1>
    </div>
  );
};

export default Home;
