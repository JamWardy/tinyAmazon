// What every page shares: calling the API, the token, and showing errors.

// The gateway. A different origin from the pages, so CORS lets them read
// its replies.
const API = "http://localhost:8000";

export function token() {
  try {
    return localStorage.getItem("token");
  } catch {
    return null;
  }
}

function setToken(value) {
  localStorage.setItem("token", value);
}

export function logOut() {
  localStorage.removeItem("token");
}

// The user's id, from the token's sub, or null. Only for showing; the
// gateway is what checks the token.
export function userId() {
  const value = token();
  if (!value) return null;
  try {
    const payload = value.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payload)).sub;
  } catch {
    return null;
  }
}

export function goToLogin() {
  const next = location.pathname + location.search;
  location.href = "/login?next=" + encodeURIComponent(next);
}

// Calls the API, giving {ok, status, data}, data the JSON body, if any.
// A network failure throws. With auth, the token is sent, and a 401 means
// it's missing or bad, so it's dropped and the user sent to log in.
export async function api(path, { method = "GET", body, headers = {}, auth = false } = {}) {
  const sent = { ...headers };
  if (body !== undefined) sent["Content-Type"] = "application/json";
  if (auth && token()) sent["Authorization"] = "Bearer " + token();
  const response = await fetch(API + path, {
    method,
    headers: sent,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    // No body, or not JSON.
  }
  if (auth && response.status === 401) {
    logOut();
    goToLogin();
  }
  return { ok: response.ok, status: response.status, data };
}

export async function logIn(email, password) {
  const reply = await api("/login", { method: "POST", body: { email, password } });
  if (reply.ok) setToken(reply.data.token);
  return reply;
}

// A Problem Details body as one line, or the status if there's none.
export function problemText(reply) {
  const problem = reply.data;
  if (problem && problem.title) {
    return problem.detail ? `${problem.title}: ${problem.detail}` : problem.title;
  }
  return `Something went wrong (${reply.status}).`;
}

export function pounds(pence) {
  return "£" + (pence / 100).toFixed(2);
}

// Fills the page's <nav> with the links and who's logged in.
export function showNav() {
  const nav = document.querySelector("nav");
  nav.replaceChildren();
  const link = (href, text) => {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    nav.append(a);
    return a;
  };
  link("/", "Search");
  link("/sell", "Sell");
  const id = userId();
  if (id) {
    const who = document.createElement("span");
    who.textContent = `User ${id}`;
    nav.append(who);
    link("/", "Log out").addEventListener("click", () => logOut());
  } else {
    link("/login", "Log in");
  }
}

// Shows text in el, as an error or not.
export function say(el, text, isError = false) {
  el.textContent = text;
  el.classList.toggle("error", isError);
}
