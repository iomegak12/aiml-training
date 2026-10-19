---
name: customer-support
description: Identify customers and summarise their CRM profile (contact details, credit limit, active status, remarks, products owned) using the read-only CRM MCP tools get_customer_profile and search_customer_profiles. Use when a question mentions a customer by name, email, phone or customer ID, or needs a customer 360 view.
---

# Customer support (CRM profiles, read-only)

Tools (CRM & Support MCP server):
- `get_customer_profile(customer_id)` - exact lookup by ID such as `CUST-0001`.
- `search_customer_profiles(name, email, phone, address, active_status, min_credit, max_credit, limit)` -
  case-insensitive **partial** matching, so `name="iyer"` finds "Ananya Iyer".

You cannot create, update or delete customers. Never invent profile data.

## Identity resolution
1. ID given -> `get_customer_profile`.
2. Name/email/phone given -> `search_customer_profiles` with the most specific field (email > phone > name).
3. Exactly one match -> use it. Several matches -> list them (ID, name, city) and report the ambiguity as a gap;
   do not pick one silently. No match -> say so and suggest checking the spelling.

## What to report
- Customer ID, full name, active status, credit limit and relevant remarks (e.g. products owned, preferences).
- **Inactive customers cannot raise new tickets** - flag this prominently when the question is about a complaint.
- Product models mentioned in remarks are useful for the Product Manuals agent - put them in your findings.
- Personal data: include only the fields the question needs; mask nothing that the user is entitled to, but do not
  dump the full address or phone unless asked.

Cite CRM evidence with kind `crm` and the customer ID.
