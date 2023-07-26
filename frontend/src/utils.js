export const getCookie = name => {
  const cookies = document.cookie.split(";").reduce((acc, x) => {
    const [key, val] = x.split("=");
    return { ...acc, [key]: val };
  }, {});
  return cookies[name];
};

export const loginWithFirebaseResponse = async (
  firebaseResponse,
  setStatus,
  setLoggedIn,
  setData
) => {
  const {
    user: { uid, accessToken: token }
  } = firebaseResponse;
  const response = await fetch("/api/firebase-login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify({ uid, token })
  });

  if (response.ok) {
    setStatus(`Successfully logged in!`);
    setLoggedIn(true);
    setData(await response.json());
  } else {
    setLoggedIn(false);
    try {
      const data = await response.json();
      setStatus(`Login failed with error: ${data.message}`);
    } catch {
      setStatus(
        `Login failed with error: ${response.statusText} (${response.status})`
      );
    }
  }
};

// Firebase configuration. The configuration is considered public, and hence
// can live in the source code.
export const firebaseConfig = {
  apiKey: "AIzaSyB5iRXnIckzjZMOthOUc3d4tCIaO2blLCA",
  authDomain: "india-ultimate-hub.firebaseapp.com",
  projectId: "india-ultimate-hub",
  storageBucket: "india-ultimate-hub.appspot.com",
  messagingSenderId: "677703680955",
  appId: "1:677703680955:web:9014c1e57b3e04e7873a9e"
};

export const fetchUserData = (setLoggedIn, setData) => {
  fetch("/api/me", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  })
    .then(response => {
      if (response.status == 200) {
        setLoggedIn(true);
        response.json().then(data => {
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
};

export const displayDate = dateString => {
  const date = new Date(dateString).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "long",
    day: "numeric"
  });
  return date;
};

export const fetchEvents = (successHandler, errorHandler) => {
  fetch("/api/events", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  })
    .then(successHandler)
    .catch(errorHandler);
};
