"""Building blocks shared by the TV and mobile phone manual builders."""

from __future__ import annotations

from data_generation.models import Bullets, Notice, Paragraph, Section, Subheading, Table


def years(n: int) -> str:
    return f"{n} year" if n == 1 else f"{n} years"


def yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def full_name(product: dict) -> str:
    return f"{product['brand']} {product['model']}"


def cover_fields(product: dict, brand: dict, product_line: str, doc_version: str, published: str) -> dict[str, str]:
    return {
        "brand": brand["name"],
        "product": full_name(product),
        "product_line": product_line,
        "model_number": f"Model number: {product['model_number']}",
        "doc_kind": "USER MANUAL",
        "edition": f"Manual version {doc_version} | Published {published}",
        "publisher": f"{brand['legal_name']}, {brand['address']}",
        "note": "Read this manual carefully before using the product and keep it for future reference.",
    }


def about_section(product: dict, brand: dict, product_noun: str, siblings: list[str]) -> Section:
    name = full_name(product)
    others = ", ".join(siblings) if siblings else "none"
    return Section(
        id="about",
        title="About This Manual",
        facts={"product": name, "model_number": product["model_number"], "brand": brand["name"]},
        blocks=[
            Paragraph(f"Thank you for choosing the {name} {product_noun}. This manual explains how to install, set up, use "
                      f"and care for your {product_noun} safely, and what to do if something does not work as expected.",
                      enrich=True),
            Notice(f"This manual applies only to model number {product['model_number']} ({name}). Specifications, "
                   f"features and warranty terms differ for other {brand['name']} models ({others}). Always check the "
                   f"model number printed on the rating label before following any instruction.", kind="note"),
            Paragraph("Menu names and screens shown in the text may differ slightly after software updates. The latest "
                      f"version of this manual is available at {brand['website']}."),
            Subheading("Conventions used in this manual"),
            Bullets([
                "**Warning** indicates a hazard that could cause serious injury or death.",
                "**Caution** indicates a hazard that could cause minor injury or damage to the product.",
                "**Note** gives useful tips and additional information.",
                "Menu paths are written as Settings > Picture > Picture Mode.",
            ]),
        ],
    )


def warranty_section(product: dict, brand: dict, rows: list[list[str]], registration_days: int, exclusions: list[str]) -> Section:
    name = full_name(product)
    return Section(
        id="warranty",
        title="Warranty and Service",
        facts={"product": name, "warranty_table": rows, "registration_days": registration_days},
        blocks=[
            Paragraph(f"{brand['legal_name']} warrants the {name} against manufacturing defects in material and "
                      "workmanship under normal domestic use for the periods listed below, starting from the date of "
                      "purchase shown on the original invoice.", enrich=True),
            Table(header=["Component", "Warranty period"], rows=rows, col_widths=[0.55, 0.45],
                  caption=f"Warranty periods for the {name} ({product['model_number']})"),
            Paragraph(f"Register your product within {registration_days} days of purchase in the {brand['app']} or at "
                      f"{brand['website']} to activate the warranty and receive software update notifications. Keep the "
                      "original invoice; it is required for every warranty claim."),
            Subheading("The warranty does not cover"),
            Bullets(exclusions),
            Paragraph("Repairs under warranty are carried out only by authorised service centres. Out-of-warranty repairs "
                      "are chargeable, and replaced parts carry a 90-day service warranty."),
        ],
    )


def regulatory_section(product: dict, brand: dict, bis_standard: str, extra: list | None = None) -> Section:
    blocks = [
        Paragraph(f"The {full_name(product)} is registered under the Compulsory Registration Scheme of the Bureau of "
                  f"Indian Standards (BIS) and complies with {bis_standard}. The registration number is printed on the "
                  "rating label.", enrich=True),
        *(extra or []),
        Subheading("E-waste disposal"),
        Paragraph("This product is covered by the E-Waste (Management) Rules, 2022. Do not dispose of the product, its "
                  "battery or accessories with household waste. Hand them over to an authorised e-waste collection "
                  f"centre or use the free take-back programme by calling {brand['toll_free']}. Improper disposal can "
                  "release hazardous substances such as lead, mercury and cadmium into the environment."),
        Paragraph("The product complies with the Restriction of Hazardous Substances (RoHS) provisions of the E-Waste "
                  "(Management) Rules, 2022."),
    ]
    return Section(id="regulatory", title="Regulatory and Environmental Information",
                   facts={"bis_standard": bis_standard}, blocks=blocks)


def support_section(product: dict, brand: dict) -> Section:
    return Section(
        id="support",
        title="Customer Support",
        facts={"toll_free": brand["toll_free"], "email": brand["email"], "hours": brand["service_hours"]},
        blocks=[
            Paragraph(f"For help with your {full_name(product)}, contact {brand['name']} customer care. Keep the model "
                      f"number ({product['model_number']}), serial number and invoice ready when you call.", enrich=True),
            Table(rows=[
                ["Toll-free helpline", brand["toll_free"]],
                ["Service hours", brand["service_hours"]],
                ["WhatsApp support", brand["whatsapp"]],
                ["Email", brand["email"]],
                ["Website", brand["website"]],
                ["Registered office", f"{brand['legal_name']}, {brand['address']}"],
            ], col_widths=[0.3, 0.7], caption="Contact details"),
        ],
    )
