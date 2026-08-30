frappe.ui.form.on("OneSpace Control Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Push Bench Config to All Shards"), () => {
			frappe.confirm(
				__("Push these values to every shard's bench group? Use this after rotating a credential."),
				() => {
					frappe.call({
						method: "oneapp_control.provisioning.bench_config.push_to_all_shards",
						freeze: true,
						freeze_message: __("Pushing to all bench groups..."),
						callback: (r) => {
							if (!r.message) return;
							const { pushed = [], failed = [] } = r.message;
							frappe.msgprint({
								title: failed.length ? __("Pushed with errors") : __("Pushed"),
								indicator: failed.length ? "orange" : "green",
								message: [
									__("{0} shard(s) updated.", [pushed.length]),
									...failed.map((f) => `${f.shard}: ${f.error}`),
								].join("<br>"),
							});
						},
					});
				},
			);
		});
	},
});
