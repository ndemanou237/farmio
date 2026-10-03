/**
 * ThumbnailSwapController
 * -------------------------
 * Sur la fiche produit, permet de changer l'image principale affichée
 * en cliquant sur une vignette, sans rechargement de page.
 */
class ThumbnailSwapController {
  constructor(button) {
    this.button = button;
    this.imageUrl = button.dataset.imageUrl;
    this.mainPreview = document.getElementById("main-preview");
    this.button.addEventListener("click", () => this.swap());
  }

  swap() {
    if (this.mainPreview) {
      this.mainPreview.src = this.imageUrl;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document
    .querySelectorAll("[data-controller='thumbnail-swap']")
    .forEach((el) => new ThumbnailSwapController(el));
});