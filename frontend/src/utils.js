import {
  create,
  parseCreationOptionsFromJSON
} from "@github/webauthn-json/browser-ponyfill";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { checkCircle, exclamationCircle } from "solid-heroicons/solid-mini";

import { matchCardColors } from "./colors";
import { membershipStartDate } from "./constants";

export const getCookie = name => {
  const cookies = document.cookie.split(";").reduce((acc, x) => {
    const [key, val] = x.trim().split("=");
    return { ...acc, [key]: val };
  }, {});
  return cookies[name];
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

export const razorpayScriptExists = () => {
  var scripts = document.getElementsByTagName("script");
  for (var i = scripts.length; i--; ) {
    if (scripts[i].src == "https://checkout.razorpay.com/v1/checkout.js")
      return true;
  }
  return false;
};

export const loadRazorpayScript = () => {
  return new Promise(resolve => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => {
      resolve(true);
    };
    script.onerror = () => {
      resolve(false);
    };
    document.body.appendChild(script);
  });
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
  if (
    selectedTeam &&
    !player.teams.map(team => team["id"].toString()).includes(selectedTeam)
  ) {
    return false;
  }
  return (
    player.full_name.toLowerCase().includes(term) ||
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

export const getStatusAndPercent = player => {
  const status = {
    profile: !!player?.id,
    // vaccine: !!player?.vaccination,
    // ucLink: !!player?.ultimate_central_id,
    membership: player?.membership?.is_active,
    waiver: player?.membership?.waiver_valid,
    accreditation: player?.accreditation?.is_valid,
    commentary_info: !!player?.commentary_info,
    college_id:
      player?.occupation === "College-Student" ? player.college_id : true
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

export const assetURL = name =>
  process.env.NODE_ENV === "production"
    ? `/static/assets/${name}`
    : `/assets/${name}`;

export const getMatchCardColor = match => {
  let color = "";
  if (match && match.pool) {
    color = matchCardColors["pool"][match.pool.sequence_number - 1];
  } else if (match && match.cross_pool) {
    color = matchCardColors["cross_pool"][match.sequence_number - 1];
  } else if (match && match.bracket) {
    color =
      matchCardColors["bracket"][match.bracket.sequence_number - 1][
        match.sequence_number - 1
      ];
  } else if (match && match.position_pool) {
    color =
      matchCardColors["position_pool"][match.position_pool.sequence_number - 1];
  }
  return color;
};

export const getTournamentBreadcrumbName = tournamentSlug => {
  let category,
    level = "",
    area = "";

  const slugWords = new Set(tournamentSlug.toLowerCase().split("-"));

  // Category
  if (slugWords.has("ncs")) {
    category = "Mixed";
  } else if (slugWords.has("nocs")) {
    category = "Opens";
  } else if (slugWords.has("nwcs")) {
    category = "Womens";
  } else if (slugWords.has("beach")) {
    category = "Beach";
  } else if (slugWords.has("ncuc") || slugWords.has("college")) {
    category = "College";
  } else if (slugWords.has("nsuc") || slugWords.has("school")) {
    category = "School";
  } else if (slugWords.has("masters")) {
    category = "Masters";
  } else if (slugWords.has("sakkath")) {
    category = "Sakkath";
  } else if (slugWords.has("u24")) {
    category = "U24";
  } else if (slugWords.has("bharat")) {
    category = "States";
  }

  // Level
  if (slugWords.has("sectionals")) {
    level = "Sectionals";
  } else if (slugWords.has("regionals")) {
    level = "Regionals";
  } else if (slugWords.has("nationals") || slugWords.has("ncuc")) {
    level = "Nationals";
  } else if (slugWords.has("qualifiers")) {
    level = "Qualifiers";
  }

  // Area: It can be either north or south not both
  if (slugWords.has("north")) {
    area = "N";
  } else if (slugWords.has("south")) {
    area = "S";
  } else if (slugWords.has("nw")) {
    area = "NW";
  } else if (slugWords.has("ne")) {
    area = "NE";
  } else if (slugWords.has("sw")) {
    area = "SW";
  } else if (slugWords.has("se")) {
    area = "SE";
  }

  // Append west or east to empty or north/south already in area string to accommodate NW / SE etc.
  if (slugWords.has("west")) {
    area += "W";
  }
  if (slugWords.has("east")) {
    area += "E";
  }

  let name = category + " " + level;
  if (area.length > 0) {
    name += ` (${area})`;
  }

  return name;
};

/**
 * @param {Response} response
 * @param {number} delay_ms
 */
export function artificialDelay(response, delay_ms) {
  return new Promise(res =>
    setTimeout(async () => res(await response.json()), delay_ms)
  );
}

export const registerPasskey = async () => {
  // Hit our backend to start register process
  const creationOptions = await fetch("/api/passkey/create/start", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  // Return error if failure
  if (!creationOptions.ok) {
    try {
      const data = await creationOptions.json();
      return { error: `Failed with error: ${data.message}` };
    } catch {
      return {
        error: `Failed with error: ${creationOptions.statusText} (${creationOptions.status})`
      };
    }
  }

  // Get the response data if success
  const creationOptionsData = await creationOptions.json();

  // Open "create passkey" dialog
  const credential = await create(
    parseCreationOptionsFromJSON(
      JSON.parse(creationOptionsData["passkey_response"])
    )
  );

  // Hit our backend to finish registration process
  const creationResponse = await fetch("/api/passkey/create/finish", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify({ passkey_request: JSON.stringify(credential) })
  });

  // Return error if failure
  if (!creationResponse.ok) {
    try {
      const data = await creationResponse.json();
      return { error: `Failed with error: ${data.message}` };
    } catch {
      return {
        error: `Failed with error: ${creationResponse.statusText} (${creationResponse.status})`
      };
    }
  }

  return { success: "Created passkey!" };
};

export const ifTodayInBetweenDates = (start, end) => {
  const currentDate = new Date(Date.now());
  currentDate.setHours(5, 30, 0, 0);

  let startDate = new Date(start);
  let endDate = new Date(end);

  if (currentDate >= startDate && currentDate <= endDate) {
    return true;
  }
  return false;
};
