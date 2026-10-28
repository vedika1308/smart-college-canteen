(() => {
  "use strict";

  const CART_KEY = "smart-canteen-cart";
  const body = document.body;
  const cartPanel = document.querySelector("#cart-panel");
  const cartItemsContainer = document.querySelector("#cart-items");
  const cartEmpty = document.querySelector("#cart-empty");
  const cartCounts = document.querySelectorAll(".cart-count");
  const cartTotal = document.querySelector("#cart-total");
  const cartSubtotal = document.querySelector("#cart-subtotal");
  const placeOrderButton = document.querySelector("#place-order");
  const toast = document.querySelector("#toast");
  const catalog = new Map();
  let cart = loadCart();
  let toastTimer;

  document.querySelectorAll(".food-card").forEach((card) => {
    const id = Number(card.dataset.id);
    catalog.set(id, {
      id,
      name: card.dataset.name,
      description: card.dataset.description,
      price: Number(card.dataset.price),
      image: card.dataset.image,
    });
  });

  function loadCart() {
    try {
      const saved = JSON.parse(localStorage.getItem(CART_KEY) || "{}");
      if (!saved || typeof saved !== "object" || Array.isArray(saved)) return {};
      return Object.fromEntries(
         Object.entries(saved)
           .map(([id, quantity]) => [String(Number(id)), Number(quantity)])
           .filter(
              ([id, quantity]) =>
                Number.isInteger(Number(id)) &&
                Number.isInteger(quantity) &&
                quantity > 0 &&
                quantity <= 99,
           ),
      );
    } catch (_error) {
      return {};
    }
  }

  function saveCart() {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
  }

  function formatMoney(value) {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(value);
}

function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function addToCart(id) {
  const key = String(id);
  if (!catalog.has(Number(id))) return;
  if ((cart[key] || 0) >= 99) {
    showToast("You can add up to 99 of each item.");
    return;
  }
  cart[key] = (cart[key] || 0) + 1;
  saveCart();
  renderCart();
  showToast(`${catalog.get(Number(id)).name} added to your cart.`);
}

function adjustQuantity(id, change) {
  const key = String(id);
  const nextQuantity = (cart[key] || 0) + change;
  if (nextQuantity <= 0) {
    delete cart[key];
  } else if (nextQuantity <= 99) {
    cart[key] = nextQuantity;
  }
  saveCart();
  renderCart();
}

function createCartRow(food, quantity) {
  const row = document.createElement("article");
  row.className = "cart-item";

    const image = document.createElement("img");
    image.src = food.image;
    image.alt = "";
    image.loading = "lazy";

    const details = document.createElement("div");
    details.className = "cart-item__details";
    const name = document.createElement("strong");
    name.textContent = food.name;
    const price = document.createElement("span");
    price.textContent = formatMoney(food.price * quantity);
    details.append(name, price);

    const controls = document.createElement("div");
    controls.className = "quantity-control";
    controls.setAttribute("aria-label", `Quantity of ${food.name}`);
    const minus = document.createElement("button");
    minus.type = "button";
    minus.className = "quantity-control__button";
    minus.setAttribute("aria-label", `Remove one ${food.name}`);
    minus.textContent = "−";
    minus.addEventListener("click", () => adjustQuantity(food.id, -1));

    const count = document.createElement("span");
    count.textContent = String(quantity);

    const plus = document.createElement("button");
    plus.type = "button";
    plus.className = "quantity-control__button";
    plus.setAttribute("aria-label", `Add one ${food.name}`);
    plus.textContent = "+";
    plus.addEventListener("click", () => adjustQuantity(food.id, 1));

    controls.append(minus, count, plus);
    row.append(image, details, controls);
    return row;
}

function renderCart() {
  if (!cartItemsContainer) return;
  cartItemsContainer.replaceChildren();

    let itemCount = 0;
    let total = 0;
    Object.entries(cart).forEach(([id, quantity]) => {
      const food = catalog.get(Number(id));
      if (!food) {
        delete cart[id];
        return;
      }
      itemCount += quantity;
      total += food.price * quantity;
      cartItemsContainer.append(createCartRow(food, quantity));
    });

    saveCart();
    cartCounts.forEach((element) => {
      element.textContent = String(itemCount);
    });
    if (cartTotal) cartTotal.textContent = formatMoney(total);
    if (cartSubtotal) cartSubtotal.textContent = formatMoney(total);
    if (cartEmpty) cartEmpty.hidden = itemCount !== 0;
    if (placeOrderButton) placeOrderButton.disabled = itemCount === 0;
    if (cartItemsContainer) cartItemsContainer.hidden = itemCount === 0;
}

function openCart() {
  if (!cartPanel) return;
  cartPanel.inert = false;
  cartPanel.classList.add("is-open");
  cartPanel.setAttribute("aria-hidden", "false");
  body.classList.add("cart-is-open");
  document.querySelector("#cart-close")?.focus();
}

function closeCart() {
  if (!cartPanel) return;
  cartPanel.classList.remove("is-open");
  cartPanel.setAttribute("aria-hidden", "true");
  cartPanel.inert = true;
  body.classList.remove("cart-is-open");
}

document.querySelectorAll("[data-add-to-cart]").forEach((button) => {
  button.addEventListener("click", () => addToCart(Number(button.dataset.addToCart)));
});

document.querySelectorAll("[data-open-cart]").forEach((button) => {
  button.addEventListener("click", openCart);
});
document.querySelector("#cart-close")?.addEventListener("click", closeCart);
document.querySelector("#cart-backdrop")?.addEventListener("click", closeCart);
document.querySelectorAll("[data-close-cart]").forEach((link) => {
  link.addEventListener("click", closeCart);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeCart();
});

document.querySelectorAll("[data-category-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    const category = button.dataset.categoryFilter;
    document.querySelectorAll("[data-category-filter]").forEach((filter) => {
      const selected = filter === button;
      filter.classList.toggle("is-active", selected);
      filter.setAttribute("aria-pressed", String(selected));
    });
    document.querySelectorAll(".food-card").forEach((card) => {
      card.hidden = category !== "All" && card.dataset.category !== category;
    });
  });
});

placeOrderButton?.addEventListener("click", async () => {
  if (body.dataset.authenticated !== "true") {
    window.location.href = body.dataset.loginUrl || "/login";
    return;
  }

    const items = Object.entries(cart).map(([foodId, quantity]) => ({
      food_id: Number(foodId),
      quantity,
    }));
    if (!items.length) {
      showToast("Your cart is empty.");
      return;
    }

    placeOrderButton.disabled = true;
    placeOrderButton.textContent = "Placing order…";
    try {
      const response = await fetch(body.dataset.placeOrderUrl || "/place_order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ items }),
      });
      const result = await response.json();
      if (response.status === 401 && result.login_url) {
        window.location.href = result.login_url;
        return;
      }
      if (!response.ok) throw new Error(result.error || "Could not place your order.");
      localStorage.removeItem(CART_KEY);
      cart = {};
      window.location.href = result.redirect_url;
    } catch (error) {
      showToast(error.message || "Something went wrong. Please try again.");
      placeOrderButton.disabled = false;
      placeOrderButton.textContent = "Place order";
    }
  });

  document.querySelector("#mobile-menu-toggle")?.addEventListener("click", () => {
    const nav = document.querySelector("#primary-navigation");
    const isOpen = nav.classList.toggle("is-open");
    document.querySelector("#mobile-menu-toggle").setAttribute("aria-expanded", String(isOpen));
  });

  renderCart();
})();
