// Copyright (c) 2026, VV SYSTEMS DEVELOPER LTD and contributors
// For license information, please see license.txt

// ── Label maps for each entry type ──────────────────────────────────────────
const ACCOUNT_LABELS = {
	Expense:        { account: "Expense Account",    contra: "Paid From (Cash / Bank)" },
	Income:         { account: "Income Account",     contra: "Received Into (Cash / Bank)" },
	"Opening Balance": { account: "Account", contra: null },
};

// ── Helpers ──────────────────────────────────────────────────────────────────
function applyEntryTypeUI(frm) {
	const et = frm.doc.entry_type;
	const labels = ACCOUNT_LABELS[et] || { account: "Account", contra: "Contra Account" };

	// Update field labels to be human-readable
	frm.set_df_property("account", "label", labels.account);
	if (labels.contra) {
		frm.set_df_property("contra_account", "label", labels.contra);
	}

	// Auto-set debit_credit for Opening Balance based on account type
	if (et === "Opening Balance" && frm.doc.account && !frm.doc.debit_credit) {
		frappe.db.get_value("Account", frm.doc.account, "account_type").then((r) => {
			const t = r.message && r.message.account_type;
			const isDebit = ["Asset", "Expense"].includes(t);
			frm.set_value("debit_credit", isDebit ? "Debit" : "Credit");
		});
	}

	// Show a helpful hint in the contra_account description
	if (et === "Expense") {
		frm.set_df_property("contra_account", "description",
			"Which account is paying? e.g. Petty Cash, Main Bank Account");
	} else if (et === "Income") {
		frm.set_df_property("contra_account", "description",
			"Which account received the money? e.g. Main Bank Account");
	}

	frm.refresh_fields();
}

// ── Form events ──────────────────────────────────────────────────────────────
frappe.ui.form.on("Ledger Entry", {
	setup(frm) {
		// Main account filter: leaf-only + type-aware
		frm.set_query("account", function () {
			const filters = { is_group: 0 };
			if (frm.doc.entry_type === "Income")   filters.account_type = "Income";
			if (frm.doc.entry_type === "Expense")  filters.account_type = "Expense";
			return { filters };
		});

		// Contra account: leaf accounts only (any type — bank, cash, payable, etc.)
		frm.set_query("contra_account", function () {
			return { filters: { is_group: 0 } };
		});

		// Trip expense filter
		frm.set_query("reference_trip_expense", function () {
			if (!frm.doc.reference_trip) return { filters: { name: "" } };
			return {
				filters: {
					parenttype: "Trips",
					parent: frm.doc.reference_trip,
					request_status: "Approved",
				},
			};
		});
	},

	refresh(frm) {
		applyEntryTypeUI(frm);

		// Show the double-entry breakdown in a small indicator
		if (frm.doc.docstatus === 1) {
			_showPostingIndicator(frm);
		}
	},

	onload(frm) {
		// Default currency from first enabled currency
		if (!frm.doc.currency) {
			frappe.db.get_value("Currency", { enabled: 1 }, "name").then((r) => {
				if (r.message) frm.set_value("currency", r.message.name);
			});
		}
	},

	entry_type(frm) {
		// Clear accounts when type changes so user selects appropriate ones
		frm.set_value("account", "");
		frm.set_value("contra_account", "");
		frm.set_value("debit_credit", "");
		applyEntryTypeUI(frm);
	},

	account(frm) {
		if (frm.doc.entry_type === "Opening Balance" && frm.doc.account) {
			// Auto-suggest the debit/credit direction
			frappe.db.get_value("Account", frm.doc.account, "account_type").then((r) => {
				const t = r.message && r.message.account_type;
				if (t && !frm.doc.debit_credit) {
					frm.set_value("debit_credit", ["Asset", "Expense"].includes(t) ? "Debit" : "Credit");
				}
			});
		}
	},
});

// ── Private: show DR/CR breakdown on submitted form ─────────────────────────
function _showPostingIndicator(frm) {
	if (!frm.doc.account || !frm.doc.amount) return;

	let debitAcct, creditAcct;
	const et = frm.doc.entry_type;

	if (et === "Expense") {
		debitAcct  = frm.doc.account;
		creditAcct = frm.doc.contra_account;
	} else if (et === "Income") {
		debitAcct  = frm.doc.contra_account;
		creditAcct = frm.doc.account;
	} else if (et === "Opening Balance") {
		if (frm.doc.debit_credit === "Debit") {
			debitAcct  = frm.doc.account;
			creditAcct = "Opening Balance Equity";
		} else {
			debitAcct  = "Opening Balance Equity";
			creditAcct = frm.doc.account;
		}
	}

	if (!debitAcct || !creditAcct) return;

	const fmt = frappe.format(frm.doc.amount,
		{ fieldtype: "Currency", options: frm.doc.currency });

	frm.set_intro(
		`<b>Double Entry:</b>&nbsp; DR <i>${debitAcct}</i> &nbsp;|&nbsp; CR <i>${creditAcct}</i> &nbsp;— ${fmt}`,
		"blue"
	);
}
