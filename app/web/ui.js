export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

let toastTimer = null;

export function showToast(message, duration = 4200) {
  const toast = $("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
    toastTimer = null;
  }, duration);
}

export function setMessage(element, message, tone = "error") {
  if (!element) return;
  if (!message) {
    element.hidden = true;
    element.textContent = "";
    return;
  }
  element.textContent = message;
  element.dataset.tone = tone;
  element.hidden = false;
}

export function bandLabel(band) {
  switch (band) {
    case "low":
      return "Low";
    case "moderate":
      return "Moderate";
    case "high":
      return "High";
    default:
      return "Not scored";
  }
}

export function bandClass(band) {
  if (band === "low" || band === "moderate" || band === "high") {
    return `band-${band}`;
  }
  return "band-unavailable";
}

export function bandColor(band) {
  switch (band) {
    case "low":
      return "#2f7a58";
    case "moderate":
      return "#b7791f";
    case "high":
      return "#b3392f";
    default:
      return "#6b7280";
  }
}

export function categoryLabel(category) {
  const labels = {
    pothole: "Pothole",
    debris: "Debris",
    waterlogging: "Waterlogging",
    poor_visibility: "Poor visibility",
    sharp_curve: "Sharp curve",
    road_work: "Road work",
    other: "Other hazard",
  };
  return labels[category] || "Hazard";
}

export function categoryColor(category) {
  const colors = {
    pothole: "#b45309",
    debris: "#6b7280",
    waterlogging: "#1d4ed8",
    poor_visibility: "#7c3aed",
    sharp_curve: "#b91c1c",
    road_work: "#a16207",
    other: "#4b5563",
  };
  return colors[category] || "#4b5563";
}

export function createElement(tag, { className, text, attrs } = {}) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value !== undefined && value !== null && value !== false) {
        element.setAttribute(key, String(value));
      }
    }
  }
  return element;
}

export function clearElement(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

export function setBusy(button, busy, busyLabel) {
  if (!button) return;
  if (busy) {
    button.dataset.idleLabel = button.textContent;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    if (busyLabel) button.textContent = busyLabel;
  } else {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    if (button.dataset.idleLabel) {
      button.textContent = button.dataset.idleLabel;
      delete button.dataset.idleLabel;
    }
  }
}

export function openSheet(element) {
  if (!element) return;
  element._returnFocus = document.activeElement;
  element.hidden = false;
  const focusTarget = element.querySelector("button, [href], input, select, textarea");
  if (focusTarget) focusTarget.focus({ preventScroll: true });
}

export function closeSheet(element) {
  if (!element || element.hidden) return;
  element.hidden = true;
  const target = element._returnFocus;
  if (target && typeof target.focus === "function") {
    target.focus({ preventScroll: true });
  }
}

export function isOnline() {
  return navigator.onLine !== false;
}
