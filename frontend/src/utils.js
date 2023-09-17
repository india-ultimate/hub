import { membershipStartDate } from "./constants";
import { Icon } from "solid-heroicons";
import { checkCircle, exclamationCircle } from "solid-heroicons/solid-mini";
import clsx from "clsx";

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

export const fetchUserData = (successCallback, failureCallback) => {
  return fetch("/api/me", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  })
    .then(response => {
      if (response.status == 200) {
        response.json().then(data => {
          successCallback(data);
        });
      } else {
        failureCallback();
      }
    })
    .catch(error => {
      console.log(error);
      failureCallback();
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

export const playerMatches = (player, text, selectedTeam) => {
  const term = text.toLowerCase();

  if (selectedTeam) {
    return (
      player.teams.map(team => team["id"].toString()).includes(selectedTeam) &&
      (player.full_name.toLowerCase().includes(term) ||
        player.city.toLowerCase().includes(term))
    );
  } else {
    return (
      player.full_name.toLowerCase().includes(term) ||
      player.city.toLowerCase().includes(term)
    );
  }
};

const today = new Date();

export const getAge = (value, on = today) => {
  const dobDate = new Date(value);
  const yearDiff = on.getFullYear() - dobDate.getFullYear();
  const monthDiff = on.getMonth() - dobDate.getMonth();
  const dayDiff = on.getDate() - dobDate.getDate();
  return yearDiff + monthDiff / 12 + dayDiff / 365;
};

export const getStatusAndPercent = player => {
  const status = {
    profile: !!player?.id,
    vaccine: !!player?.vaccination,
    ucLink: !!player?.ultimate_central_id,
    membership: player?.membership?.is_active,
    waiver: player?.membership?.waiver_valid
  };
  const percent = Math.round(
    (Object.values(status).filter(x => x).length * 100) /
      Object.keys(status).length
  );
  return { status, percent };
};

export const showPlayerStatus = player => {
  const { percent } = getStatusAndPercent(player);
  const incomplete = percent < 100;
  const color = incomplete ? "red" : "green";
  return (
    <span class={clsx(`text-${color}-600 dark:text-${color}-500`)}>
      <Icon
        path={incomplete ? exclamationCircle : checkCircle}
        style={{ width: "24px", display: "inline-block" }}
      />
    </span>
  );
};
