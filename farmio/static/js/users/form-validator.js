// farmio/static/js/users/form-validator.js
class SignupFormValidator {
  constructor(form) {
    this.form = form;
    this.password1 = form.querySelector("input[name='password1']");
    this.password2 = form.querySelector("input[name='password2']");
    if (this.password1 && this.password2) {
      this.injectStrengthHint();
      this.bindEvents();
    }
  }

  bindEvents() {
    this.password1.addEventListener("input", () => this.updateStrengthHint());
    this.password2.addEventListener("input", () => this.checkMatch());
    this.form.addEventListener("submit", (event) => this.handleSubmit(event));
  }

  injectStrengthHint() {
    this.hintEl = document.createElement("p");
    this.hintEl.className = "text-xs mt-1";
    this.password1.parentNode.appendChild(this.hintEl);
  }

  scorePassword(value) {
    let score = 0;
    if (value.length >= 8) score += 1;
    if (/[A-Z]/.test(value)) score += 1;
    if (/[0-9]/.test(value)) score += 1;
    if (/[^A-Za-z0-9]/.test(value)) score += 1;
    return score;
  }

  updateStrengthHint() {
    const score = this.scorePassword(this.password1.value);
    const levels = [
      { label: "Très faible", color: "text-red-600" },
      { label: "Faible", color: "text-orange-500" },
      { label: "Moyen", color: "text-yellow-600" },
      { label: "Bon", color: "text-lime-600" },
      { label: "Excellent", color: "text-green-700" },
    ];
    const level = levels[score];
    this.hintEl.textContent = this.password1.value ? `Force du mot de passe : ${level.label}` : "";
    this.hintEl.className = `text-xs mt-1 ${level.color}`;
  }

  checkMatch() {
    const matches = this.password1.value === this.password2.value;
    this.password2.setCustomValidity(matches ? "" : "Les mots de passe ne correspondent pas.");
  }

  handleSubmit(event) {
    this.checkMatch();
    if (!this.password2.checkValidity()) {
      event.preventDefault();
      this.password2.reportValidity();
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-controller='signup-form']").forEach((form) => new SignupFormValidator(form));
});