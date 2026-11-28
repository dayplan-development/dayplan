(() => {
  const dialog = document.querySelector("#delete-confirmation");
  if (!dialog?.showModal) return;

  const title = dialog.querySelector("#delete-task-title");
  const cancel = dialog.querySelector("[data-delete-cancel]");
  const confirm = dialog.querySelector("[data-delete-confirm]");
  let trigger;

  for (const button of document.querySelectorAll("[data-delete-trigger]")) {
    button.addEventListener("click", () => {
      trigger = button;
      title.textContent = button.dataset.taskTitle;
      confirm.disabled = false;
      dialog.showModal();
      cancel.focus();
    });
    button.disabled = false;
  }

  cancel.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => trigger?.focus({ preventScroll: true }));
  confirm.addEventListener("click", () => {
    if (!dialog.open || !trigger) return;
    confirm.disabled = true;
    trigger.form.requestSubmit();
  });
})();
