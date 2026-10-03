/**
 * Contrôleur de saisie OTP.
 *
 * Gère :
 * - la saisie des chiffres ;
 * - le déplacement automatique entre les cases ;
 * - Backspace ;
 * - les flèches gauche/droite ;
 * - le collage d'un code complet ;
 * - la synchronisation avec le champ Django ;
 * - la soumission du formulaire.
 */
class OtpInputController {
  constructor(root) {
    this.root = root;

    this.form = root.closest("form");

    this.inputs = Array.from(
      root.querySelectorAll(".otp-digit")
    );

    this.hiddenInput = root.querySelector(
      "input[name='code']"
    );

    this.expectedLength = this.inputs.length;

    this.init();
  }

  /**
   * Initialise le contrôleur.
   */
  init() {
    if (!this.isValid()) {
      console.error(
        "OTP : éléments nécessaires introuvables."
      );
      return;
    }

    this.bindEvents();
    this.syncHiddenInput();
  }

  /**
   * Vérifie que la structure HTML est correcte.
   */
  isValid() {
    return (
      this.form !== null &&
      this.hiddenInput !== null &&
      this.inputs.length === 6
    );
  }

  /**
   * Enregistre les événements.
   */
  bindEvents() {
    this.inputs.forEach((input, index) => {
      input.addEventListener(
        "input",
        (event) => {
          this.handleInput(event, index);
        }
      );

      input.addEventListener(
        "keydown",
        (event) => {
          this.handleKeydown(event, index);
        }
      );

      input.addEventListener(
        "paste",
        (event) => {
          this.handlePaste(event);
        }
      );
    });

    /*
     * Très important :
     * juste avant l'envoi du formulaire,
     * on reconstruit toujours le code.
     */
    this.form.addEventListener(
      "submit",
      () => {
        this.syncHiddenInput();
      }
    );
  }

  /**
   * Gère la saisie dans une case.
   */
  handleInput(event, index) {
    const input = event.target;

    const value = input.value
      .replace(/\D/g, "");

    /*
     * Si plusieurs chiffres sont présents,
     * on les répartit dans les cases.
     */
    if (value.length > 1) {
      this.fillInputs(value, index);
      return;
    }

    input.value = value;

    this.syncHiddenInput();

    /*
     * Passer automatiquement à la case suivante.
     */
    if (
      value !== "" &&
      index < this.inputs.length - 1
    ) {
      this.focusInput(index + 1);
    }
  }

  /**
   * Gère les touches du clavier.
   */
  handleKeydown(event, index) {
    switch (event.key) {
      case "Backspace":
        this.handleBackspace(event, index);
        break;

      case "ArrowLeft":
        this.handleArrowLeft(event, index);
        break;

      case "ArrowRight":
        this.handleArrowRight(event, index);
        break;

      default:
        this.handleCharacter(event);
    }
  }

  /**
   * Gère Backspace.
   */
  handleBackspace(event, index) {
    const input = this.inputs[index];

    /*
     * Si la case contient un chiffre,
     * on le supprime.
     */
    if (input.value !== "") {
      input.value = "";

      this.syncHiddenInput();

      return;
    }

    /*
     * Si la case est vide,
     * revenir à la précédente.
     */
    if (index > 0) {
      event.preventDefault();

      this.inputs[index - 1].value = "";

      this.focusInput(index - 1);

      this.syncHiddenInput();
    }
  }

  /**
   * Gère la flèche gauche.
   */
  handleArrowLeft(event, index) {
    if (index === 0) {
      return;
    }

    event.preventDefault();

    this.focusInput(index - 1);
  }

  /**
   * Gère la flèche droite.
   */
  handleArrowRight(event, index) {
    if (
      index >= this.inputs.length - 1
    ) {
      return;
    }

    event.preventDefault();

    this.focusInput(index + 1);
  }

  /**
   * Empêche les caractères non numériques.
   */
  handleCharacter(event) {
    /*
     * Autoriser les raccourcis :
     * Ctrl + A
     * Ctrl + C
     * Ctrl + V
     * Ctrl + X
     */
    if (
      event.ctrlKey ||
      event.metaKey
    ) {
      return;
    }

    /*
     * Touches de contrôle autorisées.
     */
    const controlKeys = [
      "Tab",
      "Delete",
      "Enter",
      "Escape",
      "Home",
      "End",
    ];

    if (controlKeys.includes(event.key)) {
      return;
    }

    /*
     * Bloquer tout ce qui n'est pas un chiffre.
     */
    if (
      event.key.length === 1 &&
      !/[0-9]/.test(event.key)
    ) {
      event.preventDefault();
    }
  }

  /**
   * Gère le collage d'un code OTP.
   */
  handlePaste(event) {
    event.preventDefault();

    const pastedText =
      event.clipboardData.getData("text");

    const code = pastedText
      .replace(/\D/g, "")
      .slice(0, this.expectedLength);

    if (code === "") {
      return;
    }

    /*
     * Toujours commencer à la première case
     * lorsqu'on colle un code complet.
     */
    this.fillInputs(code, 0);
  }

  /**
   * Répartit les chiffres dans les cases.
   */
  fillInputs(value, startIndex = 0) {
    const digits = value
      .replace(/\D/g, "")
      .slice(0, this.expectedLength);

    /*
     * Si on colle un nouveau code depuis la
     * première case, on nettoie toutes les cases.
     */
    if (startIndex === 0) {
      this.inputs.forEach((input) => {
        input.value = "";
      });
    }

    digits.split("").forEach(
      (digit, offset) => {
        const index =
          startIndex + offset;

        if (this.inputs[index]) {
          this.inputs[index].value = digit;
        }
      }
    );

    this.syncHiddenInput();

    this.focusNextEmptyInput();
  }

  /**
   * Place le focus sur la prochaine case vide.
   */
  focusNextEmptyInput() {
    const index = this.inputs.findIndex(
      (input) => input.value === ""
    );

    if (index !== -1) {
      this.focusInput(index);
      return;
    }

    /*
     * Toutes les cases sont remplies.
     * On laisse le focus sur la dernière.
     */
    this.focusInput(
      this.inputs.length - 1
    );
  }

  /**
   * Place le focus sur une case.
   */
  focusInput(index) {
    const input = this.inputs[index];

    if (!input) {
      return;
    }

    input.focus();
    input.select();
  }

  /**
   * Récupère le code des six cases.
   */
  getCode() {
    return this.inputs
      .map((input) => input.value)
      .join("");
  }

  /**
   * Synchronise le champ Django caché.
   */
  syncHiddenInput() {
    const code = this.getCode();

    this.hiddenInput.value = code;
  }
}


/**
 * Contrôleur du bouton de renvoi OTP.
 */
class OtpResendController {
  constructor(button) {
    this.button = button;

    this.label = button.querySelector(
      "[data-role='cooldown-label']"
    );

    this.remaining =
      Number(button.dataset.cooldown) || 0;

    this.timer = null;

    this.init();
  }

  /**
   * Initialise le contrôleur.
   */
  init() {
    if (this.remaining > 0) {
      this.startCountdown();
    }
  }

  /**
   * Démarre le compte à rebours.
   */
  startCountdown() {
    this.setDisabled(true);

    this.updateLabel();

    this.timer = window.setInterval(
      () => {
        this.tick();
      },
      1000
    );
  }

  /**
   * Exécute une seconde du compte à rebours.
   */
  tick() {
    this.remaining -= 1;

    if (this.remaining <= 0) {
      this.stopCountdown();
      return;
    }

    this.updateLabel();
  }

  /**
   * Arrête le compte à rebours.
   */
  stopCountdown() {
    if (this.timer !== null) {
      window.clearInterval(this.timer);

      this.timer = null;
    }

    this.setDisabled(false);

    this.clearLabel();
  }

  /**
   * Active ou désactive le bouton.
   */
  setDisabled(disabled) {
    this.button.disabled = disabled;
  }

  /**
   * Met à jour le texte du compteur.
   */
  updateLabel() {
    if (!this.label) {
      return;
    }

    this.label.textContent =
      ` (${this.remaining}s)`;
  }

  /**
   * Efface le compteur.
   */
  clearLabel() {
    if (!this.label) {
      return;
    }

    this.label.textContent = "";
  }
}


/**
 * Application OTP.
 */
class OtpApplication {
  /**
   * Initialise l'application.
   */
  init() {
    this.initOtpInputs();
    this.initOtpResend();
  }

  /**
   * Initialise les champs OTP.
   */
  initOtpInputs() {
    const elements =
      document.querySelectorAll(
        "[data-controller='otp-input']"
      );

    elements.forEach((element) => {
      new OtpInputController(element);
    });
  }

  /**
   * Initialise le bouton de renvoi.
   */
  initOtpResend() {
    const elements =
      document.querySelectorAll(
        "[data-controller='otp-resend']"
      );

    elements.forEach((element) => {
      new OtpResendController(element);
    });
  }
}


/**
 * Point d'entrée.
 */
document.addEventListener(
  "DOMContentLoaded",
  () => {
    const application =
      new OtpApplication();

    application.init();
  }
);