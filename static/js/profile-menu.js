(() => {
  const menu = document.querySelector("[data-profile-menu]");
  if (!menu) return;

  const trigger = menu.querySelector("[data-profile-toggle]");
  const panel = menu.querySelector("#profile-menu-panel");
  const mobileLayout = matchMedia("(max-width: 860px)");

  function positionPanel() {
    if (!mobileLayout.matches) {
      panel.style.top = "";
      panel.style.right = "";
      panel.style.maxHeight = "";
      return;
    }

    const navigation = document.querySelector(".site-nav");
    const navBottom = navigation?.getBoundingClientRect().bottom ?? trigger.getBoundingClientRect().bottom;
    const returnControl = document.querySelector(".summaries-return");
    const returnBottom = returnControl?.getBoundingClientRect().bottom ?? 0;
    const top = Math.ceil(Math.max(navBottom, returnBottom) + 8);
    const right = Math.max(16, Math.round(window.innerWidth - trigger.getBoundingClientRect().right));
    panel.style.top = `${top}px`;
    panel.style.right = `${right}px`;
    panel.style.maxHeight = `${Math.max(0, window.innerHeight - top - 16)}px`;
  }

  function setOpen(open, { focusTrigger = false } = {}) {
    if (open) positionPanel();
    panel.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (focusTrigger) trigger.focus({ preventScroll: true });
  }

  trigger.addEventListener("click", () => setOpen(panel.hidden));

  document.addEventListener("pointerdown", event => {
    if (!panel.hidden && !menu.contains(event.target)) setOpen(false);
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !panel.hidden) {
      event.preventDefault();
      setOpen(false, { focusTrigger: true });
    }
  });

  window.addEventListener("resize", () => {
    if (!panel.hidden) positionPanel();
  });
})();
