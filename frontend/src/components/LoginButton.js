const getCookie = name => {
  const cookies = document.cookie.split(";").reduce((acc, x) => {
    const [key, val] = x.split("=");
    return { ...acc, [key]: val };
  }, {});
  return cookies[name];
};

const LoginButton = () => {
  const csrftoken = getCookie("csrftoken");
  const login = async () => {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken },
      body: JSON.stringify({
        username: "user@gmail.com",
        password: "password"
      })
    });

    if (response.ok) {
      console.log("Login success");
      // Login successful
    } else {
      // Login failed
      console.log("Login fail");
    }
  };

  return (
    <button type="button" onClick={login}>
      Login
    </button>
  );
};

export default LoginButton;
