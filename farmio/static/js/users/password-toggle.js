// farmio/static/js/users/password-toggle.js
class PasswordToggleController {
  constructor(root) {
    this.fields = Array.from(root.querySelectorAll("input[type='password']"));
    this.fields.forEach((field) => this.wrapField(field));
  }

  wrapField(field) {
    const wrapper = document.createElement("div");
    wrapper.className = "relative";
    field.parentNode.insertBefore(wrapper, field);
    wrapper.appendChild(field);
    field.classList.add("pr-10");

    const toggleButton = document.createElement("button");
    toggleButton.type = "button";
    toggleButton.setAttribute("aria-label", "Afficher / masquer le mot de passe");
    toggleButton.className = "absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600";
    toggleButton.textContent = "👁";
    wrapper.appendChild(toggleButton);
    toggleButton.addEventListener("click", () => this.toggle(field, toggleButton));
  }

  toggle(field, button) {
    const isHidden = field.type === "password";
    field.type = isHidden ? "text" : "password";
    button.textContent = isHidden ? "🙈" : "👁";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-controller='password-toggle']").forEach((el) => new PasswordToggleController(el));
});