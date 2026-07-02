(() => {
	"use strict";

	const BRAND = "Speedaily BOS";
	const LOGO = "/assets/speedaily_bos/images/logo.png";
	const LOGO_PATH = new URL(LOGO, window.location.origin).pathname;
	const IS_STAGING_WORKSPACE =
		window.location.hostname === "speedaily.dev" ||
		window.location.hostname.endsWith(".speedaily.dev");
	const PLATFORM_ORIGIN = IS_STAGING_WORKSPACE
		? "https://speedaily.dev"
		: "https://speedaily.com";
	const TEAM_URL = `${PLATFORM_ORIGIN}/app/team`;
	const SIGN_IN_URL = `${PLATFORM_ORIGIN}/signin`;
	const UPSTREAM_APP_NAMES = new Set(["erpnext", "frappe"]);
	const UPSTREAM_BRAND_PATTERN = /\b(?:ERPNext|Frappe(?: Framework)?)\b/gi;
	const BRANDING_SURFACES = [
		".body-sidebar-container",
		".navbar",
		".desk-navbar",
		".sidebar-header-menu",
		".page-card-head",
		".modal-dialog",
		".web-footer",
	];

	const replaceUpstreamBrand = (value) => {
		if (!value || !UPSTREAM_BRAND_PATTERN.test(value)) {
			UPSTREAM_BRAND_PATTERN.lastIndex = 0;
			return value;
		}
		UPSTREAM_BRAND_PATTERN.lastIndex = 0;
		return value.replace(UPSTREAM_BRAND_PATTERN, BRAND);
	};

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
			document.title = replaceUpstreamBrand(document.title) || BRAND;
			return;
		}
	};

	const updateBootBranding = () => {
		const boot = window.frappe?.boot;
		if (!boot) {
			return;
		}

		for (const app of boot.app_data ?? []) {
			if (UPSTREAM_APP_NAMES.has(String(app.app_name ?? "").toLowerCase())) {
				app.app_title = BRAND;
				app.app_logo_url = LOGO;
			}
		}

		for (const app of boot.apps_data?.apps ?? []) {
			if (UPSTREAM_APP_NAMES.has(String(app.name ?? app.app_name ?? "").toLowerCase())) {
				if ("title" in app) app.title = BRAND;
				if ("app_title" in app) app.app_title = BRAND;
				if ("logo" in app) app.logo = LOGO;
				if ("app_logo_url" in app) app.app_logo_url = LOGO;
			}
		}

		const sidebar = window.frappe?.app?.sidebar;
		if (sidebar && /frappe|erpnext/i.test(sidebar.header_subtitle ?? "")) {
			sidebar.header_subtitle = BRAND;
		}
	};

	const updateVisibleBranding = () => {
		const surfaces = document.querySelectorAll(BRANDING_SURFACES.join(","));
		for (const surface of surfaces) {
			const walker = document.createTreeWalker(surface, NodeFilter.SHOW_TEXT);
			let textNode = walker.nextNode();
			while (textNode) {
				const updated = replaceUpstreamBrand(textNode.nodeValue);
				if (updated !== textNode.nodeValue) {
					textNode.nodeValue = updated;
				}
				textNode = walker.nextNode();
			}

			for (const element of surface.querySelectorAll(
				"[title], [aria-label], [alt], [data-original-title]"
			)) {
				for (const attribute of ["title", "aria-label", "alt", "data-original-title"]) {
					if (!element.hasAttribute(attribute)) continue;
					const current = element.getAttribute(attribute);
					const updated = replaceUpstreamBrand(current);
					if (updated !== current) {
						element.setAttribute(attribute, updated);
					}
				}
			}
		}

		document.querySelectorAll(".body-sidebar .header-subtitle").forEach((subtitle) => {
			if (/frappe|erpnext/i.test(subtitle.textContent ?? "")) {
				subtitle.textContent = BRAND;
			}
		});
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
		updateBootBranding();
		updateTitle();
		updateLogo();
		updateVisibleBranding();
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
			attributes: true,
			attributeFilter: ["title", "aria-label", "alt", "data-original-title"],
			characterData: true,
			childList: true,
			subtree: true,
		});

		if (window.frappe?.router?.on) {
			window.frappe.router.on("change", scheduleBranding);
		}
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start, { once: true });
	} else {
		start();
	}
})();
