/**
 * Contrôleur pour l'upload et la prévisualisation d'images produit.
 */
class ImageUploadController {
  constructor(root) {
    this.root = root;
    this.dropzone = root.querySelector('[data-role="dropzone"]');
    this.fileInput = root.querySelector('input[type="file"]');
    this.previewGrid = root.querySelector('[data-role="preview-grid"]');
    this.mainImageIndexInput = root.querySelector('input[name$="main_image_index"]');

    this.filesList = [];
    this.init();
  }

  init() {
    if (!this.fileInput || !this.previewGrid) {
      console.warn("ImageUpload: Éléments introuvables.");
      return;
    }

    this.bindEvents();
  }

  bindEvents() {
    // Sélection de fichiers via le champ input
    this.fileInput.addEventListener("change", () => this.handleFileSelect());

    // Support Drag and Drop
    if (this.dropzone) {
      ["dragenter", "dragover"].forEach((eventName) => {
        this.dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.dropzone.classList.add("border-green-500", "bg-green-50/80");
        });
      });

      ["dragleave", "drop"].forEach((eventName) => {
        this.dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.dropzone.classList.remove("border-green-500", "bg-green-50/80");
        });
      });

      this.dropzone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        if (dt.files && dt.files.length > 0) {
          this.fileInput.files = dt.files;
          this.handleFileSelect();
        }
      });
    }
  }

  handleFileSelect() {
    const files = Array.from(this.fileInput.files);
    if (!files.length) return;

    this.previewGrid.innerHTML = "";
    this.filesList = files;

    files.forEach((file, index) => {
      if (!file.type.startsWith("image/")) return;

      const reader = new FileReader();
      reader.onload = (e) => {
        const card = this.createPreviewCard(e.target.result, file.name, index);
        this.previewGrid.appendChild(card);
      };
      reader.readAsDataURL(file);
    });

    // Définir la première image comme principale par défaut
    if (this.mainImageIndexInput && (!this.mainImageIndexInput.value || this.mainImageIndexInput.value === "0")) {
      this.setMainImage(0);
    }
  }

  createPreviewCard(imageSrc, fileName, index) {
    const card = document.createElement("div");
    card.className = "group relative rounded-xl overflow-hidden bg-gray-100 border-2 border-gray-200 aspect-square";
    card.dataset.index = index;

    const isMain = this.mainImageIndexInput && parseInt(this.mainImageIndexInput.value, 10) === index;

    if (isMain) {
      card.classList.add("border-green-600");
    }

    card.innerHTML = `
      <img src="${imageSrc}" alt="${fileName}" class="w-full h-full object-cover">
      <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-between p-2">
        <button type="button" class="btn-main-image self-start text-[10px] px-2 py-1 rounded-md ${
          isMain ? "bg-green-600 text-white" : "bg-white text-gray-800"
        } font-semibold shadow">
          ${isMain ? "Principale" : "Définir principale"}
        </button>
        <button type="button" class="btn-remove-image self-end w-7 h-7 rounded-lg bg-red-600 text-white flex items-center justify-center shadow">
          <i class="fa-solid fa-trash text-xs"></i>
        </button>
      </div>
    `;

    // Événements
    const btnMain = card.querySelector(".btn-main-image");
    btnMain.addEventListener("click", () => this.setMainImage(index));

    const btnRemove = card.querySelector(".btn-remove-image");
    btnRemove.addEventListener("click", () => this.removeFile(index));

    return card;
  }

  setMainImage(index) {
    if (this.mainImageIndexInput) {
      this.mainImageIndexInput.value = index;
    }

    const cards = this.previewGrid.querySelectorAll("[data-index]");
    cards.forEach((card) => {
      const cardIndex = parseInt(card.dataset.index, 10);
      const btnMain = card.querySelector(".btn-main-image");
      if (cardIndex === index) {
        card.classList.add("border-green-600");
        card.classList.remove("border-gray-200");
        if (btnMain) {
          btnMain.className = "btn-main-image self-start text-[10px] px-2 py-1 rounded-md bg-green-600 text-white font-semibold shadow";
          btnMain.textContent = "Principale";
        }
      } else {
        card.classList.remove("border-green-600");
        card.classList.add("border-gray-200");
        if (btnMain) {
          btnMain.className = "btn-main-image self-start text-[10px] px-2 py-1 rounded-md bg-white text-gray-800 font-semibold shadow";
          btnMain.textContent = "Définir principale";
        }
      }
    });
  }

  removeFile(index) {
    const dt = new DataTransfer();
    const files = Array.from(this.fileInput.files);

    files.forEach((file, i) => {
      if (i !== index) dt.items.add(file);
    });

    this.fileInput.files = dt.files;
    this.handleFileSelect();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const uploadElements = document.querySelectorAll('[data-controller="image-upload"]');
  uploadElements.forEach((el) => new ImageUploadController(el));
});