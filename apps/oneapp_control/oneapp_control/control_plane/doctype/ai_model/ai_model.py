import frappe
from frappe import _
from frappe.model.document import Document


class AIModel(Document):
	def validate(self):
		self._markup_keeps_the_packs_solvent()

	def _markup_keeps_the_packs_solvent(self):
		"""An override below the global markup reprices every credit pack.

		A customer chooses which model to spend a credit on, so the cheapest
		markup in the catalogue is the one every pack is really priced against
		— see `pricing.lowest_markup`. Overriding one model down to 1.0 is
		therefore not a decision about that model, it is a decision about the
		whole price list, and it should not be possible to make it by accident.
		"""
		override = float(self.markup_override or 0)
		if override <= 0 or self.status not in ("Available", "Preview"):
			return

		from oneapp_control.billing import packs

		broken = packs.underwater(override)
		if broken:
			frappe.throw(
				_(
					"A markup of {0}× on this model would make these packs sell "
					"credits below cost: {1}. A credit can be spent here, so this "
					"model's markup prices every pack."
				).format(override, ", ".join(one["pack_name"] for one in broken))
			)
