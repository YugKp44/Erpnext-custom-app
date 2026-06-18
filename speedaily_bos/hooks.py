app_name = "speedaily_bos"
app_title = "Speedaily BOS"
app_publisher = "Speedaily"
app_description = "Business Operating System for growing Indian businesses"
app_email = "support@speedaily.com"
app_license = "Proprietary"
app_logo_url = "/assets/speedaily_bos/images/logo.png"
app_home = "/app/speedaily-bos"

required_apps = ["erpnext", "india_compliance"]

app_include_css = ["/assets/speedaily_bos/css/speedaily.css"]
app_include_js = ["/assets/speedaily_bos/js/speedaily.js"]
web_include_css = ["/assets/speedaily_bos/css/speedaily.css"]
web_include_js = ["/assets/speedaily_bos/js/speedaily.js"]

website_context = {
	"favicon": "/assets/speedaily_bos/images/logo.png",
	"splash_image": "/assets/speedaily_bos/images/logo.png",
}

after_install = "speedaily_bos.install.after_install"
after_migrate = "speedaily_bos.install.after_migrate"

fixtures = [
	{
		"dt": "Role",
		"filters": [
			[
				"role_name",
				"in",
				[
					"Speedaily Owner",
					"Speedaily Accountant",
					"Speedaily Sales User",
					"Speedaily Purchase User",
					"Speedaily Inventory User",
					"Speedaily Viewer",
				],
			]
		],
	}
]

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": app_home,
	}
]
