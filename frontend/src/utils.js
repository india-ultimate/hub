export const getCookie = name => {
  const cookies = document.cookie.split(";").reduce((acc, x) => {
    const [key, val] = x.split("=");
    return { ...acc, [key]: val };
  }, {});
  return cookies[name];
};
