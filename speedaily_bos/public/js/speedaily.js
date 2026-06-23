(() => {
	"use strict";

	const BRAND = "Speedaily BOS";
	const LOGO = "/assets/speedaily_bos/images/logo.png";
	const LOGO_PATH = new URL(LOGO, window.location.origin).pathname;
	const TEAM_URL = "https://speedaily.dev/app/team";
	const SIGN_IN_URL = "https://speedaily.dev/signin";

	const redirectToSpeedailySignIn = () => {
		window.location.replace(SIGN_IN_URL);
	};

	const redirectLoggedOutUsers = () => {
		if (
			window.location.pathname === "/login" &&
			new URLSearchParams(window.location.search).has("redirect-to")
		) {
			redirectToSpeedailySignIn();
			return;
		}

		if (window.frappe?.app) {
			window.frappe.app.redirect_to_login = redirectToSpeedailySignIn;
		}

		if (window.frappe) {
			window.frappe.logout = () => {
				window.frappe.call({
					method: "logout",
					callback: (response) => {
						if (!response.exc) {
							redirectToSpeedailySignIn();
						}
					},
				});
			};
		}
	};

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
			if (
				image instanceof HTMLImageElement &&
				!image.closest(".speedaily-brand-lockup") &&
				new URL(image.src, window.location.origin).pathname !== LOGO_PATH
			) {
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

	const addTeamAccess = () => {
		const roles = Array.isArray(window.frappe?.user_roles)
			? window.frappe.user_roles
			: [];
		if (
			!roles.includes("Speedaily Owner") ||
			document.querySelector(".speedaily-team-link")
		) {
			return;
		}

		const navbar = document.querySelector(".navbar .navbar-nav");
		if (!navbar) {
			return;
		}

		const item = document.createElement("li");
		item.className = "nav-item speedaily-team-link";
		const link = document.createElement("a");
		link.className = "nav-link";
		link.href = TEAM_URL;
		link.textContent = "Team";
		link.title = "Manage teammates and access";
		item.append(link);
		navbar.prepend(item);
	};

	const applyBranding = () => {
		redirectLoggedOutUsers();
		updateTitle();
		updateLogo();
		addBrandLockup();
		addTeamAccess();
	};

	const start = () => {
		applyBranding();

		let scheduled = false;
		const scheduleBranding = () => {
			if (scheduled) {
				return;
			}
			scheduled = true;
			window.requestAnimationFrame(() => {
				scheduled = false;
				applyBranding();
			});
		};

		const observer = new MutationObserver(scheduleBranding);
		observer.observe(document.documentElement, {
			childList: true,
			subtree: true,
		});
		window.setTimeout(() => observer.disconnect(), 8000);
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start, { once: true });
	} else {
		start();
	}
})();
