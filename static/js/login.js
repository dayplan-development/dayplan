(() => {
  const toggle = document.querySelector("[data-password-toggle]");
  const password = document.getElementById(toggle.getAttribute("aria-controls"));
  toggle.addEventListener("click", () => {
    const reveal = password.type === "password";
    password.type = reveal ? "text" : "password";
    toggle.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
  });
  toggle.hidden = false;
})();
