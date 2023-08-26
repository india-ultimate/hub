import { membershipStartDate } from "./constants";

export const getCookie = name => {
  const cookies = document.cookie.split(";").reduce((acc, x) => {
    const [key, val] = x.trim().split("=");
    return { ...acc, [key]: val };
  }, {});
  return cookies[name];
};

export const clearCookie = name => {
  const cookie = document.cookie
    .split(";")
    .find(x => x.trim().split("=")[0] === name);

  if (cookie) {
    const [key, val] = cookie.split("=");
    document.cookie = `${key}=${val}; max-age=0`;
  } else {
    console.log("Could not find cookie");
  }
};

export const loginWithFirebaseResponse = async (
  firebaseResponse,
  onSuccess,
  onFailure
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
    body: JSON.stringify({ uid, token, login: true })
  });

  if (response.ok) {
    onSuccess(response);
  } else {
    onFailure(response);
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

export const fetchUrl = (url, successHandler, errorHandler) => {
  fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  })
    .then(successHandler)
    .catch(errorHandler);
};

export const membershipYearOptions = () => {
  // Get the current date
  const currentDate = new Date();
  const currentMonth = currentDate.getMonth() + 1;
  const year = currentDate.getFullYear();
  const [_, membershipEndMonth] = membershipStartDate;

  let renewalOptions = [];

  if (currentMonth <= membershipEndMonth) {
    renewalOptions.push(year - 1);
    if (currentMonth == membershipEndMonth) {
      renewalOptions.push(year);
    }
  } else if (currentMonth >= membershipEndMonth) {
    renewalOptions.push(year);
  }

  return renewalOptions;
};

export const findPlayerById = (data, id) => {
  if (data.player?.id === id) {
    return data.player;
  } else {
    return data.wards?.filter(p => p.id === id)?.[0];
  }
};

const handlePaymentSuccess = (
  data,
  setStatus,
  setPlayerById,
  successCallback
) => {
  fetch("/api/payment-success", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify(data),
    credentials: "same-origin"
  })
    .then(async response => {
      if (response.ok) {
        const players = await response.json();
        players.forEach(player => {
          setPlayerById(player);
        });
        if (successCallback) {
          successCallback();
        }
        setStatus(
          <span class="text-green-500 dark:text-green-400">
            Payment successfully completed! 🎉
          </span>
        );
      } else {
        if (response.status === 422) {
          const error = await response.json();
          setStatus(`Error: ${error.message}`);
        } else {
          const body = await response.text();
          setStatus(
            `Error: ${response.statusText} (${response.status}) — ${body}`
          );
        }
      }
    })
    .catch(error => setStatus(`Error: ${error}`));
};

const openRazorpayUI = (data, setStatus, setPlayerById, successCallback) => {
  const options = {
    ...data,
    handler: e =>
      handlePaymentSuccess(e, setStatus, setPlayerById, successCallback)
  };
  const rzp = window.Razorpay(options);
  rzp.open();
};

export const purchaseMembership = (
  data,
  setStatus,
  setPlayerById,
  successCallback
) => {
  const type = data?.year ? "annual" : "event";
  console.log(`Paying for ${type} membership for ${data?.player_id}`, data);
  fetch("/api/create-order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify(data),
    credentials: "same-origin"
  })
    .then(async response => {
      if (response.ok) {
        const data = await response.json();
        setStatus("");
        openRazorpayUI(data, setStatus, setPlayerById, successCallback);
      } else {
        if (response.status === 422) {
          const errors = await response.json();
          const errorMsgs = errors.detail.map(
            err => `${err.msg}: ${err.loc[2]}`
          );
          setStatus(`Validation errors: ${errorMsgs.join(", ")}`);
        } else if (response.status === 400) {
          const errors = await response.json();
          setStatus(`Validation errors: ${errors.message}`);
        } else {
          const body = await response.text();
          setStatus(
            `Error: ${response.statusText} (${response.status}) — ${body}`
          );
        }
      }
    })
    .catch(error => setStatus(`Error: ${error}`));
};

export const getPlayer = (data, id) => {
  if (data.player?.id === id) {
    return data.player;
  } else {
    return data.wards?.filter(p => p.id === id)?.[0];
  }
};

export const getLabel = (choices, value) => {
  const choice = choices.find(item => item.value === value);
  return choice?.label;
};

export const playerMatches = (player, text) => {
  const term = text.toLowerCase();
  return (
    player.full_name.toLowerCase().includes(term) ||
    player.team_name.toLowerCase().includes(term) ||
    player.city.toLowerCase().includes(term)
  );
};

const today = new Date();

export const getAge = (value, on = today) => {
  const dobDate = new Date(value);
  const yearDiff = on.getFullYear() - dobDate.getFullYear();
  const monthDiff = on.getMonth() - dobDate.getMonth();
  const dayDiff = on.getDate() - dobDate.getDate();
  return yearDiff + monthDiff / 12 + dayDiff / 365;
};
