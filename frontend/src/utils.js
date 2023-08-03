import {
  membershipStartDate,
  membershipEndDate,
  annualMembershipFee,
  eventMembershipFee
} from "./constants";

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
        setStatus("Payment successfully completed!");
      } else {
        if (response.status === 422) {
          const error = await response.json();
          setStatus(`Error: ${error.message}`);
        } else {
          setStatus(`Error: ${response.statusText} (${response.status})`);
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
          setStatus(`Error: ${response.statusText} (${response.status})`);
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
