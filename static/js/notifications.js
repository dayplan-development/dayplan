(() => {
  const stack = document.querySelector("[data-flash-stack]");
  const polite = document.querySelector("[data-flash-polite]");
  const assertive = document.querySelector("[data-flash-assertive]");
  const announce = [];
  const successDuration = 4000;
  stack.classList.add("is-enhanced");

  for (const notification of stack.querySelectorAll("[data-flash-category]")) {
    const category = notification.dataset.flashCategory;
    const isError = category === "error" || category === "danger";
    const announcement = document.createElement("span");
    announcement.textContent = notification.querySelector(".flash-message").textContent.trim() + " ";
    announce.push(() => {
      if (!notification.classList.contains("is-dismissing")) {
        (isError ? assertive : polite).append(announcement);
      }
    });

    const close = notification.querySelector(".flash-close");
    let timer;
    let started;
    let remaining = successDuration;
    let hovered = notification.matches(":hover");

    function pause() {
      if (timer === undefined) return;
      clearTimeout(timer);
      timer = undefined;
      remaining = Math.max(0, remaining - (performance.now() - started));
    }

    async function dismiss() {
      if (notification.classList.contains("is-dismissing")) return;
      pause();
      notification.classList.add("is-dismissing");
      if (notification.contains(document.activeElement)) {
        stack.closest("main").focus({ preventScroll: true });
      }
      close.disabled = true;
      await Promise.allSettled(notification.getAnimations().map(animation => animation.finished));
      notification.remove();
      announcement.remove();
      if (!stack.childElementCount) stack.remove();
    }

    function resume() {
      if (timer !== undefined || hovered || notification.matches(":focus-within") ||
          notification.classList.contains("is-dismissing")) return;
      started = performance.now();
      timer = setTimeout(dismiss, remaining);
    }

    close.addEventListener("click", dismiss);
    close.hidden = false;
    if (category !== "success") continue;

    notification.addEventListener("pointerenter", event => {
      if (event.pointerType === "touch") return;
      hovered = true;
      pause();
    });
    notification.addEventListener("pointerleave", event => {
      if (event.pointerType === "touch") return;
      hovered = false;
      resume();
    });
    notification.addEventListener("focusin", pause);
    notification.addEventListener("focusout", event => {
      if (!notification.contains(event.relatedTarget)) queueMicrotask(resume);
    });
    resume();
  }

  // Let assistive technology register the empty regions before announcing messages.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    for (const publish of announce) publish();
  }));
})();
