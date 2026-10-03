document.addEventListener('DOMContentLoaded', function () {
  const menuButton = document.getElementById('mobile-menu-button');
  const mobileMenu = document.getElementById('mobile-menu');

  if (menuButton && mobileMenu) {
    menuButton.addEventListener('click', function () {
      const isOpen = !mobileMenu.classList.contains('hidden');
      mobileMenu.classList.toggle('hidden', isOpen);
      menuButton.setAttribute('aria-expanded', String(!isOpen));
    });
  }

  document.querySelectorAll('[data-unit-price]').forEach(function (quantityInput) {
    const form = quantityInput.closest('form');
    if (!form) return;

    const button = form.querySelector('button[type="submit"]');
    const total = document.getElementById('purchase-total');
    const unitPrice = Number(quantityInput.dataset.unitPrice);
    if (!button || !unitPrice) return;

    const updateTotal = function () {
      const quantity = Math.max(1, Number(quantityInput.value) || 1);
      const formattedTotal = new Intl.NumberFormat(undefined, {
        maximumFractionDigits: 2,
      }).format(quantity * unitPrice);
      button.dataset.total = formattedTotal;
      if (total) total.textContent = formattedTotal;
    };

    quantityInput.addEventListener('input', updateTotal);
    updateTotal();
  });
});
