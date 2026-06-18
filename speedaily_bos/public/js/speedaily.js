(() => {
	"use strict";

	const BRAND = "Speedaily BOS";
	const LOGO = "/assets/speedaily_bos/images/logo.png";

	const updateTitle = () => {
		if (!document.title || /frappe|erpnext/i.test(document.title)) {
			document.title = BRAND;
			return;
		}
		document.title = document.title
			.replace(/ERPNext/gi, BRAND)
			.replace(/Frappe/gi, BRAND);
	};

	const updateLogo = () => {
		const selectors = [
			".navbar-brand .app-logo",
			".navbar-home img",
			".page-card-head img",
			"img.app-logo",
		];

		document.querySelectorAll(selectors.join(",")).forEach((image) => {
			if (image instanceof HTMLImageElement && image.src !== LOGO) {
				image.src = LOGO;
				image.alt = BRAND;
			}
		});
	};

	const addBrandLockup = () => {
		const home = document.querySelector(".navbar-home");
		if (!home || home.querySelector(".speedaily-brand-lockup")) {
			return;
		}

		const lockup = document.createElement("span");
		lockup.className = "speedaily-brand-lockup";
		lockup.innerHTML = `<img src="${LOGO}" alt="${BRAND}"><span>${BRAND}</span>`;
		home.replaceChildren(lockup);
	};

	const applyBranding = () => {
		updateTitle();
		updateLogo();
		addBrandLockup();
	};

	const start = () => {
		applyBranding();
		const observer = new MutationObserver(applyBranding);
		observer.observe(document.documentElement, {
			childList: true,
			subtree: true,
		});
		window.setTimeout(() => observer.disconnect(), 15000);
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start, { once: true });
	} else {
		start();
	}
})();

