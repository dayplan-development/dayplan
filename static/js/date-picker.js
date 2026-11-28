(() => {
  if (typeof HTMLDialogElement === "undefined" || !HTMLDialogElement.prototype.showModal) return;

  const projectDate = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit"
  });
  const monthLabel = new Intl.DateTimeFormat("en", {
    timeZone: "UTC", month: "long", year: "numeric"
  });
  const dayLabel = new Intl.DateTimeFormat("en", {
    timeZone: "UTC", dateStyle: "full"
  });

  // Calendar dates stay in UTC so browser timezone and daylight saving do not shift them.
  function makeDate(year, month, day) {
    const date = new Date(0);
    date.setUTCFullYear(year, month, day);
    return date;
  }

  function iso(date) {
    return date.toISOString().slice(0, 10);
  }

  function parse(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000")) return null;
    const [year, month, day] = value.split("-").map(Number);
    const date = makeDate(year, month - 1, day);
    return iso(date) === value ? date : null;
  }

  function todayInProject() {
    const parts = Object.fromEntries(projectDate.formatToParts().map(({ type, value }) => [type, value]));
    return makeDate(Number(parts.year), Number(parts.month) - 1, Number(parts.day));
  }

  for (const picker of document.querySelectorAll("[data-date-picker]")) {
    const input = picker.querySelector("input");
    const trigger = picker.querySelector(".date-picker-trigger");
    const dialog = picker.querySelector("dialog");
    const heading = dialog.querySelector("h4");
    const grid = dialog.querySelector("tbody");
    const previous = dialog.querySelector("[data-calendar-prev]");
    const next = dialog.querySelector("[data-calendar-next]");
    let selected;
    let today;
    let cursor;

    function render() {
      const year = cursor.getUTCFullYear();
      const month = cursor.getUTCMonth();
      const label = monthLabel.format(cursor);
      if (heading.textContent !== label) heading.textContent = label;
      previous.disabled = year === 1 && month === 0;
      next.disabled = year === 9999 && month === 11;
      const leading = (makeDate(year, month, 1).getUTCDay() + 6) % 7;
      grid.replaceChildren();
      for (let index = 0; index < 42; index++) {
        if (index % 7 === 0) grid.insertRow();
        const cell = grid.rows[grid.rows.length - 1].insertCell();
        const date = makeDate(year, month, index - leading + 1);
        const day = document.createElement("button");
        day.type = "button";
        day.textContent = date.getUTCDate();
        day.setAttribute("aria-label", dayLabel.format(date));
        day.tabIndex = date.getTime() === cursor.getTime() ? 0 : -1;
        if (date.getUTCMonth() !== month) day.classList.add("is-adjacent");
        if (date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) {
          day.disabled = true;
        } else {
          const value = iso(date);
          day.dataset.date = value;
          cell.setAttribute("aria-selected", String(value === selected));
          if (value === today) day.setAttribute("aria-current", "date");
        }
        cell.append(day);
      }
    }

    function focusDay() {
      grid.querySelector('[tabindex="0"]').focus();
    }

    function browse(delta, control) {
      const month = makeDate(cursor.getUTCFullYear(), cursor.getUTCMonth() + delta, 1);
      cursor = makeDate(month.getUTCFullYear(), month.getUTCMonth(), Math.min(
        cursor.getUTCDate(), makeDate(month.getUTCFullYear(), month.getUTCMonth() + 1, 0).getUTCDate()
      ));
      render();
      if (control.disabled) focusDay();
    }

    function select(value) {
      input.value = value;
      dialog.close();
    }

    trigger.addEventListener("click", () => {
      const current = parse(input.value);
      const projectToday = todayInProject();
      today = iso(projectToday);
      selected = current ? iso(current) : null;
      cursor = current || projectToday;
      render();
      dialog.showModal();
      focusDay();
    });
    previous.addEventListener("click", () => browse(-1, previous));
    next.addEventListener("click", () => browse(1, next));
    dialog.querySelector("[data-calendar-today]").addEventListener("click", () => select(iso(todayInProject())));
    dialog.querySelector("[data-calendar-clear]").addEventListener("click", () => select(""));
    dialog.querySelector("[data-calendar-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => trigger.focus({ preventScroll: true }));
    dialog.addEventListener("click", event => {
      if (event.target !== dialog) return;
      const { left, right, top, bottom } = dialog.getBoundingClientRect();
      if (event.clientX < left || event.clientX > right || event.clientY < top || event.clientY > bottom) {
        dialog.close();
      }
    });
    grid.addEventListener("click", event => {
      if (event.target.dataset.date) select(event.target.dataset.date);
    });
    const offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    grid.addEventListener("keydown", event => {
      const delta = offsets[event.key];
      if (!event.target.dataset.date || delta === undefined) return;
      event.preventDefault();
      const date = parse(event.target.dataset.date);
      date.setUTCDate(date.getUTCDate() + delta);
      if (date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) return;
      cursor = date;
      render();
      focusDay();
    });
    trigger.hidden = false;
  }
})();
