"""Builds a mobile phone user manual Document from a catalog entry."""

from __future__ import annotations

from data_generation.builders._manual_common import (
    about_section,
    cover_fields,
    full_name,
    regulatory_section,
    support_section,
    warranty_section,
    yes_no,
)
from data_generation.catalog import BRANDS, PHONES, siblings
from data_generation.models import Bullets, DocMeta, Document, Notice, Paragraph, Section, Subheading, Table

MANUAL_VERSION = "1.1"
PUBLISHED = "February 2026"


def wireless_text(p: dict) -> str:
    if not p["wireless_w"]:
        return "Not supported"
    text = f"{p['wireless_w']} W"
    if p.get("reverse_wireless_w"):
        text += f"; {p['reverse_wireless_w']} W reverse wireless charging"
    return text


def software_support_text(p: dict) -> str:
    upgrades = "1 Android OS upgrade" if p["os_upgrades"] == 1 else f"{p['os_upgrades']} Android OS upgrades"
    return f"{upgrades} and {p['security_years']} years of security updates"


def memory_variants_text(p: dict) -> str:
    return "; ".join(f"{ram} RAM + {rom} storage" for ram, rom, _ in p["variants"])


def mrp_text(p: dict) -> str:
    return "; ".join(f"Rs. {price} ({ram} + {rom})" for ram, rom, price in p["variants"])


def spec_rows(p: dict) -> list[list[str]]:
    """Technical specification rows. Golden Q&A uses the same labels as evidence."""
    brand = BRANDS[p["brand"]]
    return [
        ["Model name", full_name(p)],
        ["Model number", p["model_number"]],
        ["Display", p["display"]],
        ["Resolution", p["resolution"]],
        ["Refresh rate", p["refresh_hz"]],
        ["Peak brightness", f"{p['peak_brightness_nits']} nits"],
        ["Chipset", p["chipset"]],
        ["Memory variants", memory_variants_text(p)],
        ["Rear cameras", "; ".join(p["rear_cameras"])],
        ["Front camera", p["front_camera"]],
        ["Video recording", p["video"]],
        ["Battery capacity", f"{p['battery_mah']} mAh (typical)"],
        ["Wired charging", f"{p['wired_w']} W"],
        ["Wireless charging", wireless_text(p)],
        ["Charger in the box", f"{p['charger_in_box_w']} W"],
        ["Water and dust resistance", p["ip_rating"]],
        ["Network", p["network"]],
        ["SIM", p["sim"]],
        ["Memory card", p["memory_card"]],
        ["3.5 mm headphone jack", yes_no(p["headphone_jack"])],
        ["NFC", yes_no(p["nfc"])],
        ["USB", p["usb"]],
        ["Wi-Fi", p["wifi"]],
        ["Bluetooth", p["bluetooth"]],
        ["Biometrics", f"{p['fingerprint']}; face unlock"],
        ["Operating system", brand["os"]],
        ["Software support", software_support_text(p)],
        ["SAR (head)", f"{p['sar_head']} W/kg (limit 1.6 W/kg)"],
        ["SAR (body)", f"{p['sar_body']} W/kg (limit 1.6 W/kg)"],
        ["Dimensions", f"{p['dims_mm']} mm"],
        ["Weight", f"{p['weight_g']} g"],
        ["Maximum retail price (MRP)", mrp_text(p)],
    ]


def _safety_section(p: dict) -> Section:
    return Section(
        id="safety", title="Safety Information",
        facts={"charger_in_box_w": p["charger_in_box_w"]},
        blocks=[
            Paragraph("Read this safety information before using the phone. Incorrect use can cause fire, electric "
                      "shock, injury or damage to the phone.", enrich=True),
            Notice("Warning: Do not use a phone or charger that is swollen, leaking, damaged or overheating. Stop using it "
                   "immediately and contact an authorised service centre.", kind="warning"),
            Subheading("Battery and charging"),
            Bullets([
                "Use only the supplied charger and cable or certified accessories of the same brand.",
                "Do not charge the phone on a bed, pillow or sofa, or under a blanket; heat cannot escape.",
                "Charge the phone between 5 and 35 degrees Celsius. Charging stops automatically if the battery is too hot.",
                "Do not puncture, crush, bend or heat the battery or expose it to temperatures above 45 degrees Celsius.",
                "The battery is not user-replaceable. Battery replacement must be done at an authorised service centre.",
            ]),
            Subheading("General use"),
            Bullets([
                "Do not use the phone while driving. Use a hands-free kit only where permitted by law.",
                "Keep the phone at least 15 cm away from implanted medical devices such as pacemakers.",
                "Switch off the phone where instructed, such as in aircraft, hospitals and fuel stations.",
                "Listening at high volume for long periods can permanently damage your hearing.",
                "Small parts such as the SIM tray and ejector tool can be a choking hazard for young children.",
                "If the screen glass breaks, stop using the phone until it is repaired to avoid cuts.",
            ]),
        ],
    )


def _box_section(p: dict) -> Section:
    items = [
        f"{full_name(p)} phone (model {p['model_number']})",
        f"{p['charger_in_box_w']} W power adapter",
        "USB Type-C to Type-C cable (1 m)" if p["wired_w"] >= 45 else "USB Type-A to Type-C cable (1 m)",
        "SIM ejector tool",
        "Protective clear case",
        "Quick start guide and warranty card",
    ]
    notes = [Notice(f"Note: The supplied {p['charger_in_box_w']} W adapter charges the phone at up to "
                    f"{p['charger_in_box_w']} W. The phone supports wired charging at up to {p['wired_w']} W with a "
                    "compatible adapter sold separately.", kind="note")] if p["charger_in_box_w"] < p["wired_w"] else []
    return Section(
        id="box", title="What Is in the Box", facts={"items": items},
        blocks=[Paragraph("Check that the following items are present. Contact customer care within 7 days of purchase "
                          "if anything is missing.", enrich=True), Bullets(items), *notes],
    )


def _overview_section(p: dict) -> Section:
    rows = [
        ["Power / Lock key", "Right side", "Press to lock or wake the screen. Press and hold for the power menu."],
        ["Volume keys", "Right side", "Adjust volume. Press Volume down and Power together to take a screenshot."],
        ["SIM tray", "Bottom edge" if "Zentrix" in p["brand"] else "Left side", f"Holds the SIM cards ({p['sim']})."],
        ["USB Type-C port", "Bottom edge", "Charging, data transfer and wired audio adapters."],
        ["Microphones", "Top and bottom edges", "Calls, voice recording and noise cancellation."],
        ["Fingerprint sensor", "Power key" if "Side" in p["fingerprint"] else "Under the screen", p["fingerprint"] + "."],
    ]
    if p["headphone_jack"]:
        rows.append(["3.5 mm headphone jack", "Top edge", "Wired headphones and earphones."])
    return Section(
        id="overview", title="Phone Overview",
        facts={"display": p["display"], "sim": p["sim"], "fingerprint": p["fingerprint"],
               "headphone_jack": p["headphone_jack"]},
        blocks=[
            Paragraph(f"The {full_name(p)} has a {p['display']} display with a front camera in a small punch-hole at "
                      "the top centre. The rear camera module is in the top-left corner of the back panel.", enrich=True),
            Table(header=["Part", "Location", "Function"], rows=rows, col_widths=[0.24, 0.2, 0.56],
                  caption=f"Physical controls and ports of the {full_name(p)}"),
        ],
    )


def _getting_started_section(p: dict, brand: dict) -> Section:
    esim = "eSIM" in p["sim"]
    blocks = [
        Paragraph("This section explains how to insert SIM cards, charge the phone and complete the setup wizard.",
                  enrich=True),
        Subheading("Inserting SIM cards"),
        Bullets([
            "Insert the SIM ejector tool into the hole next to the SIM tray and push gently until the tray pops out.",
            "Place the nano-SIM cards in the tray with the gold contacts facing down.",
            "Push the tray back into the slot until it clicks." + (
                " If your model has a hybrid slot, the second SIM position can hold either a nano-SIM or a microSD card."
                if "hybrid" in p["sim"] else ""),
        ], ordered=True),
    ]
    if esim:
        blocks += [
            Subheading("Activating an eSIM"),
            Paragraph("Request an eSIM QR code from your mobile operator. Go to Settings > Network > SIM manager > Add eSIM "
                      "and scan the QR code while connected to Wi-Fi. Both a physical SIM and an eSIM can be active at the "
                      "same time."),
        ]
    else:
        blocks.append(Paragraph(f"The {full_name(p)} does not support eSIM. Use physical nano-SIM cards only."))
    blocks += [
        Subheading("Charging the battery"),
        Paragraph(f"The battery is partially charged at the factory. Connect the supplied {p['charger_in_box_w']} W adapter "
                  "and cable, and charge fully before first use. The charging animation shows the estimated time to full."),
        Subheading("Setup wizard"),
        Bullets([
            "Press and hold the Power key for 3 seconds to switch on the phone.",
            "Select your language and region (India) and connect to Wi-Fi.",
            f"Sign in with your {brand['account']} to restore backups from {brand['cloud']}.",
            "Register your fingerprint and face for secure unlocking.",
            "Review the privacy options and complete the setup.",
        ], ordered=True),
    ]
    return Section(id="getting_started", title="Getting Started", facts={"sim": p["sim"], "esim": esim}, blocks=blocks)


def _display_battery_section(p: dict) -> Section:
    wireless = (f"The phone supports wireless charging at up to {p['wireless_w']} W on a compatible charger."
                if p["wireless_w"] else "This model does not support wireless charging.")
    if p.get("reverse_wireless_w"):
        wireless += (f" Reverse wireless charging at {p['reverse_wireless_w']} W lets you charge earbuds or a watch by "
                     "placing them on the back of the phone.")
    return Section(
        id="display_battery", title="Display and Battery",
        facts={"refresh_hz": p["refresh_hz"], "battery_mah": p["battery_mah"], "wired_w": p["wired_w"],
               "wireless_w": p["wireless_w"], "peak_brightness_nits": p["peak_brightness_nits"]},
        blocks=[
            Paragraph(f"The {p['display']} display has a refresh rate of {p['refresh_hz']} and a peak brightness of "
                      f"{p['peak_brightness_nits']} nits for comfortable viewing outdoors.", enrich=True),
            Bullets([
                "Eye comfort mode reduces blue light; schedule it from sunset to sunrise.",
                "Dark mode lowers power consumption on AMOLED displays and reduces glare at night.",
                "Adaptive brightness learns your preferred brightness in different lighting.",
            ]),
            Subheading("Battery and charging"),
            Paragraph(f"The {p['battery_mah']} mAh battery supports wired fast charging at up to {p['wired_w']} W. "
                      f"{wireless}"),
            Bullets([
                "Battery Saver limits background activity when the charge falls below 15%.",
                "Charging Protection stops charging at 80% to extend battery life when the phone is left plugged in overnight.",
                "Battery usage per app is shown in Settings > Battery > Usage.",
            ]),
        ],
    )


def _camera_section(p: dict) -> Section:
    rows = [[f"Rear camera {i + 1}", c] for i, c in enumerate(p["rear_cameras"])]
    rows += [["Front camera", p["front_camera"]], ["Video recording", p["video"]]]
    modes = ["**Photo**: point and shoot with automatic scene detection.",
             "**Night**: combines several exposures for bright, low-noise photos in the dark. Hold the phone steady.",
             "**Portrait**: blurs the background with adjustable bokeh.",
             "**Pro**: manual control of ISO, shutter speed, white balance and focus.",
             "**Video**: records with electronic stabilisation; tap the screen to change focus."]
    if any("telephoto" in c for c in p["rear_cameras"]):
        modes.append("**Telephoto**: optical zoom using the periscope lens; tap the zoom shortcut to switch.")
    return Section(
        id="camera", title="Camera",
        facts={"rear_cameras": p["rear_cameras"], "front_camera": p["front_camera"], "video": p["video"]},
        blocks=[
            Paragraph("Open the Camera app from the home screen or by double-pressing the Power key. Swipe left or right "
                      "to switch between camera modes.", enrich=True),
            Table(header=["Camera", "Details"], rows=rows, col_widths=[0.3, 0.7], caption=f"Cameras of the {full_name(p)}"),
            Subheading("Camera modes"),
            Bullets(modes),
            Paragraph("Keep the lenses clean with a soft cloth. Fingerprints on the lens are the most common cause of "
                      "hazy photos."),
        ],
    )


def _security_section(p: dict, brand: dict) -> Section:
    return Section(
        id="security", title="Security and Privacy",
        facts={"fingerprint": p["fingerprint"], "security_years": p["security_years"]},
        blocks=[
            Paragraph("Protect your phone and personal data with a screen lock, biometrics and regular security updates.",
                      enrich=True),
            Bullets([
                f"**Fingerprint**: {p['fingerprint']}. Register up to 5 fingerprints in Settings > Security > Fingerprint.",
                "**Face unlock**: uses the front camera; it is less secure than a fingerprint or PIN and cannot be used for "
                "payments.",
                f"**Find My Device**: locate, ring, lock or erase a lost phone from {brand['cloud']} on the web.",
                "**Emergency SOS**: press the Power key 5 times quickly to call 112 and share your location with emergency contacts.",
                "**App permissions**: review which apps can use your location, camera and microphone in Settings > Privacy.",
            ]),
        ],
    )


def _connectivity_section(p: dict) -> Section:
    items = [f"**Mobile network**: {p['network']}.", f"**Wi-Fi**: {p['wifi']}.", f"**Bluetooth**: version {p['bluetooth']}.",
             f"**USB**: {p['usb']}.", "**Mobile hotspot**: share your mobile data with up to 10 devices."]
    items.append("**NFC**: tap-to-pay with UPI and card wallets, and quick pairing with accessories." if p["nfc"]
                 else "**NFC**: not available on this model.")
    return Section(
        id="connectivity", title="Connectivity",
        facts={"network": p["network"], "wifi": p["wifi"], "bluetooth": p["bluetooth"], "nfc": p["nfc"]},
        blocks=[Paragraph("Stay connected with mobile data, Wi-Fi and short-range wireless technologies.", enrich=True),
                Bullets(items)],
    )


def _settings_section(p: dict) -> Section:
    max_refresh = p["refresh_hz"].removesuffix(" adaptive").split(" to ")[-1]
    rows = [
        ["Settings > Display > Refresh rate", f"Adaptive (up to {max_refresh}), Standard (60 Hz)"],
        ["Settings > Display > Eye comfort", "On, Off, Scheduled"],
        ["Settings > Battery > Battery Saver", "On, Off, Turn on automatically at 15%"],
        ["Settings > Battery > Charging Protection", "Stop charging at 80%"],
        ["Settings > Network > SIM manager", "Preferred SIM for calls, SMS and data"],
        ["Settings > Network > Mobile hotspot", "Name, password, connected devices"],
        ["Settings > Security > Fingerprint", "Add, delete or rename fingerprints"],
        ["Settings > Privacy > Permission manager", "Location, camera, microphone and other permissions"],
        ["Settings > Sound > Do Not Disturb", "Schedules and exceptions for calls and alarms"],
        ["Settings > System > Software update", "Check for updates, auto download over Wi-Fi"],
        ["Settings > System > Backup", "Back up apps, contacts and photos to the cloud"],
        ["Settings > System > Reset", "Reset network settings or erase all data"],
    ]
    return Section(
        id="settings", title="Settings Reference", facts={},
        blocks=[Paragraph("The table lists commonly used settings. Use the search bar at the top of Settings to find any "
                          "option quickly.", enrich=True),
                Table(header=["Menu path", "Options"], rows=rows, col_widths=[0.5, 0.5], caption="Frequently used settings")],
    )


def _water_section(p: dict) -> Section:
    blocks = [
        Paragraph(f"The {full_name(p)} is rated {p['ip_rating']} under IEC standard 60529, which means it is "
                  f"{p['ip_detail']}.", enrich=True),
        Bullets([
            "Water resistance is not permanent and may decrease over time due to normal wear.",
            "Do not expose the phone to salt water, chlorinated pool water, soap, shampoo or hot water.",
            "Do not charge the phone when the USB port is wet. Dry it for at least 30 minutes first.",
            "Liquid damage is not covered by the warranty, regardless of the IP rating.",
        ]),
    ]
    return Section(id="water_dust", title="Water and Dust Resistance", facts={"ip_rating": p["ip_rating"]}, blocks=blocks)


def _care_section(p: dict, brand: dict) -> Section:
    return Section(
        id="care", title="Care and Software Updates",
        facts={"os_upgrades": p["os_upgrades"], "security_years": p["security_years"]},
        blocks=[
            Paragraph("Looking after the phone and keeping its software current extends its life and protects your data.",
                      enrich=True),
            Bullets([
                "Clean the screen with a dry microfibre cloth; avoid alcohol-based cleaners on the anti-fingerprint coating.",
                "Use a case and screen protector to reduce the risk of damage from drops.",
                "Keep at least 10% of storage free for smooth performance.",
                "Restart the phone at least once a week.",
            ]),
            Paragraph(f"{brand['name']} commits to providing {software_support_text(p)} for the {full_name(p)} from the "
                      "date of launch in India. Updates are delivered over the air; keep the phone charged above 30% and "
                      "connected to Wi-Fi when installing them."),
        ],
    )


def _troubleshooting_section(p: dict) -> Section:
    rows = [
        ["Phone does not switch on", "Battery fully drained", "Charge for at least 30 minutes, then press and hold the Power key."],
        ["Phone is frozen", "App or system not responding", "Press and hold Power and Volume down for 10 seconds to force restart."],
        ["Charging is slow", "Non-original charger or damaged cable",
         f"Use the supplied {p['charger_in_box_w']} W adapter and cable, and clean the USB port."],
        ["Battery drains quickly", "Apps running in the background or high refresh rate",
         "Check Settings > Battery > Usage and enable Battery Saver."],
        ["No network signal", "SIM not inserted properly or network mode wrong",
         "Reinsert the SIM and select the correct preferred network type."],
        ["Mobile data does not work", "Data disabled or wrong APN",
         "Turn on mobile data and reset APN settings to default in SIM manager."],
        ["Wi-Fi keeps disconnecting", "Router distance or power saving", "Move closer to the router and forget and rejoin the network."],
        ["Fingerprint not recognised", "Wet or dirty finger or sensor", "Clean and dry the sensor and finger, or re-register the fingerprint."],
        ["Phone becomes warm", "Gaming, fast charging or direct sunlight",
         "Close heavy apps, remove the case while charging and keep the phone out of the sun."],
        ["Storage full warning", "Large photos, videos or app caches",
         "Use the Files app to clear junk files or back up photos to the cloud."],
        ["Bluetooth device does not connect", "Device not in pairing mode", "Put the accessory in pairing mode and remove old pairings."],
        ["Camera photos are blurry", "Dirty lens or camera shake", "Clean the lens and hold the phone steady or use a tripod."],
        ["Calls drop frequently", "Weak signal or VoLTE disabled", "Enable VoLTE in SIM manager and update the software."],
        ["Apps crash repeatedly", "Outdated app or corrupted cache", "Update the app and clear its cache in Settings > Apps."],
    ]
    if "eSIM" in p["sim"]:
        rows.append(["eSIM activation fails", "QR code expired or no internet",
                     "Connect to Wi-Fi and request a new QR code from the operator."])
    return Section(
        id="troubleshooting", title="Troubleshooting",
        facts={"rows": len(rows)},
        blocks=[Paragraph("Try the solutions below before visiting a service centre. Back up your data before resetting the "
                          "phone.", enrich=True),
                Table(header=["Problem", "Possible cause", "Solution"], rows=rows, col_widths=[0.26, 0.3, 0.44],
                      caption=f"Troubleshooting guide for the {full_name(p)}")],
    )


def _status_section(p: dict) -> Section:
    rows = [
        ["Charging paused: battery temperature high", "Battery is above the safe charging temperature",
         "Unplug the charger and let the phone cool down."],
        ["Moisture detected in USB port", "Liquid or sweat in the charging port", "Disconnect the cable and let the port dry fully."],
        ["Accessory not supported", "Uncertified cable or adapter", "Use an original or certified accessory."],
        ["No SIM card", "SIM tray not seated correctly", "Remove and reinsert the SIM tray."],
        ["Emergency calls only", "No registered network", "Move to an area with coverage or check the SIM with your operator."],
        ["Storage almost full", "Less than 10% storage free", "Delete unused files or move them to the cloud."],
        ["Slow charging", f"Adapter below {p['charger_in_box_w']} W or damaged cable",
         "Use the supplied adapter and an undamaged cable."],
    ]
    return Section(
        id="status_messages", title="Status Messages",
        facts={},
        blocks=[Paragraph("The phone displays the following notifications when it detects a condition that needs your "
                          "attention.", enrich=True),
                Table(header=["Message", "Meaning", "What to do"], rows=rows, col_widths=[0.32, 0.33, 0.35],
                      caption="Common status messages")],
    )


def build(p: dict) -> Document:
    brand = BRANDS[p["brand"]]
    name = full_name(p)
    sibs = siblings(p, PHONES)
    battery_months = p["battery_warranty_months"]
    warranty_rows = [
        ["Phone (handset)", "12 months"],
        ["Battery", f"{battery_months} months"],
        ["Charger and USB cable", "6 months"],
        ["Protective case and SIM ejector tool", "Not covered"],
    ]
    exclusions = [
        "Physical damage, including cracked screens, dents and bent frames.",
        "Liquid damage, regardless of the IP rating.",
        "Damage caused by unauthorised software, rooting or unlocking the bootloader.",
        "Normal wear of the battery, defined as capacity remaining above 80% of the rated capacity.",
        "Repairs carried out by persons other than authorised service centres.",
    ]
    sar = [Subheading("Specific Absorption Rate (SAR)"),
           Paragraph(f"This phone meets the Indian SAR limit of 1.6 W/kg averaged over 1 gram of tissue. The highest SAR "
                     f"values for this model are {p['sar_head']} W/kg at the head and {p['sar_body']} W/kg on the body at a "
                     "separation of 5 mm. Dial *#07# to view SAR information on the phone. Use a hands-free kit to reduce "
                     "exposure.")]
    sections = [
        about_section(p, brand, "smartphone", sibs),
        _safety_section(p),
        _box_section(p),
        _overview_section(p),
        _getting_started_section(p, brand),
        _display_battery_section(p),
        _camera_section(p),
        _security_section(p, brand),
        _connectivity_section(p),
        _settings_section(p),
        _water_section(p),
        _care_section(p, brand),
        _troubleshooting_section(p),
        _status_section(p),
        Section(id="specs", title="Technical Specifications", facts={},
                blocks=[Table(header=["Specification", name], rows=spec_rows(p), col_widths=[0.35, 0.65],
                              caption=f"Specifications of the {name} ({p['model_number']})")]),
        warranty_section(p, brand, warranty_rows, registration_days=15, exclusions=exclusions),
        regulatory_section(p, brand, "IS 13252 (Part 1):2010 (Information technology equipment - Safety)", extra=sar),
        support_section(p, brand),
    ]
    product_line = f"{p['display']} {'5G' if '5G' in p['network'] else '4G'} smartphone"
    meta = DocMeta(
        doc_id=p["doc_id"],
        title=f"{name} User Manual",
        subtitle=product_line,
        category="product_manual",
        subcategory="mobile",
        publisher=brand["legal_name"],
        version=MANUAL_VERSION,
        effective_date=PUBLISHED,
        filename=f"{p['doc_id']}_{name.replace(' ', '_')}_User_Manual.pdf",
        relative_dir="product_manuals/mobile",
        page_range=(5, 10),
        brand=p["brand"],
        model=p["model"],
        model_number=p["model_number"],
        family=p["family"],
        keywords=["smartphone", "user manual", p["brand"], p["model"], p["model_number"]],
        sibling_models=sibs,
    )
    return Document(meta=meta, sections=sections, facts=p,
                    cover=cover_fields(p, brand, product_line, MANUAL_VERSION, PUBLISHED))
