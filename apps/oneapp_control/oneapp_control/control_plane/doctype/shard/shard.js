frappe.ui.form.on("Shard", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.press_release_group) return;

		frm.add_custom_button(__("Push Bench Config"), () => {
			frappe.confirm(
				__("Push shared config from OneSpace Control Settings to {0}? Every tenant site on this bench inherits it.",
					[frm.doc.press_release_group]),
				() => {
					frappe.call({
						method: "oneapp_control.provisioning.bench_config.push_to_shard",
						args: { shard: frm.doc.name },
						freeze: true,
						freeze_message: __("Pushing to bench group..."),
						callback: (r) => {
							if (!r.message) return;
							frappe.msgprint({
								title: __("Pushed"),
								indicator: "green",
								message: __("{0} keys pushed to {1}.", [
									r.message.keys.length,
									r.message.release_group,
								]),
							});
						},
					});
				},
			);
		});
	},
});
