"""Builds a TV user manual Document from a catalog entry."""

from __future__ import annotations

from data_generation.builders._manual_common import (
    about_section,
    cover_fields,
    full_name,
    regulatory_section,
    support_section,
    warranty_section,
    years,
    yes_no,
)
from data_generation.catalog import BRANDS, TVS, siblings
from data_generation.models import Bullets, DocMeta, Document, Notice, Paragraph, Section, Subheading, Table

MANUAL_VERSION = "1.2"
PUBLISHED = "March 2026"

PICTURE_MODE_HELP = {
    "Standard": "balanced picture suitable for most content and lighting conditions",
    "Vivid": "boosted brightness and colour for brightly lit rooms",
    "Dynamic": "maximum brightness and contrast for very bright rooms",
    "Cinema": "warmer colours and smoother gradation for films in a dim room",
    "Movie": "warmer colours and smoother gradation for films in a dim room",
    "Sport": "enhanced motion clarity and greener grass tones for live sport",
    "Game": "lowest input lag; most picture processing is switched off",
    "Filmmaker": "the creator's intended picture with motion smoothing disabled",
    "Filmmaker Mode": "the creator's intended picture with motion smoothing disabled",
    "Eco": "reduced backlight to lower power consumption",
    "Expert (Bright Room)": "calibrated picture for a bright room",
    "Expert (Dark Room)": "calibrated picture for a dark room",
}


def spec_rows(tv: dict) -> list[list[str]]:
    """Technical specification rows. Golden Q&A uses the same labels as evidence."""
    brand = BRANDS[tv["brand"]]
    return [
        ["Model name", full_name(tv)],
        ["Model number", tv["model_number"]],
        ["Screen size", f"{tv['screen_size_in']} inches ({tv['screen_size_cm']} cm) diagonal"],
        ["Panel type", tv["panel"]],
        ["Resolution", tv["resolution"]],
        ["Native refresh rate", f"{tv['refresh_hz']} Hz"],
        ["HDR formats", ", ".join(tv["hdr"])],
        ["Processor", tv["processor"]],
        ["Memory", f"{tv['ram_gb']} GB RAM, {tv['storage_gb']} GB storage"],
        ["Operating system", brand["os"]],
        ["Audio output", f"{tv['speaker_w']} W, {tv['speaker_channels']}"],
        ["Dolby Atmos", yes_no(tv["dolby_atmos"])],
        ["HDMI ports", str(tv["hdmi_ports"])],
        ["HDMI 2.1 ports", str(tv["hdmi21_ports"]) if tv["hdmi21_ports"] else "None (all HDMI ports are HDMI 2.0)"],
        ["ARC / eARC", tv["earc_port"]],
        ["USB ports", str(tv["usb_ports"])],
        ["Ethernet (LAN)", "1 port"],
        ["Optical audio out", "1 port"],
        ["Wi-Fi", tv["wifi"]],
        ["Bluetooth", tv["bluetooth"]],
        ["Variable Refresh Rate (VRR)", yes_no(tv["vrr"])],
        ["Auto Low Latency Mode (ALLM)", yes_no(tv["allm"])],
        ["Power supply", "AC 100-240 V, 50/60 Hz"],
        ["Power consumption (typical)", f"{tv['power_typical_w']} W"],
        ["Power consumption (maximum)", f"{tv['power_max_w']} W"],
        ["Standby power", f"Less than {tv['standby_w']} W"],
        ["VESA wall-mount pattern", tv["vesa"]],
        ["Wall-mount screws", tv["wall_screw"]],
        ["Dimensions without stand (W x H x D)", f"{tv['dims_no_stand_mm']} mm"],
        ["Weight without stand", f"{tv['weight_no_stand_kg']} kg"],
        ["Weight with stand", f"{tv['weight_with_stand_kg']} kg"],
        ["Warranty", f"{years(tv['warranty_years'])} comprehensive; display panel {years(tv['panel_warranty_years'])}"],
        ["Maximum retail price (MRP)", f"Rs. {tv['mrp_inr']} (inclusive of all taxes)"],
    ]


def _settings_root(tv: dict) -> str:
    return "Settings" if tv["brand"] == "Voltara" else "Menu"


def _safety_section(tv: dict) -> Section:
    heavy = tv["screen_size_in"] >= 55
    return Section(
        id="safety",
        title="Important Safety Instructions",
        facts={"screen_size_in": tv["screen_size_in"], "power_supply": "AC 100-240 V, 50/60 Hz"},
        blocks=[
            Paragraph("Please read these safety instructions before installing or operating the TV. Following them "
                      "protects you, your family and the product from harm.", enrich=True),
            Notice("Warning: To reduce the risk of fire or electric shock, do not expose the TV to rain or moisture, and "
                   "never place containers of liquid, such as vases, on or near it.", kind="warning"),
            Bullets([
                "Connect the TV only to a grounded power outlet supplying AC 100-240 V, 50/60 Hz.",
                "Use a surge protector or voltage stabiliser in areas with frequent power fluctuations.",
                "Do not overload wall outlets, extension cords or multi-plug adapters.",
                "Unplug the TV during lightning storms or when it will not be used for a long period.",
                "Keep the power cord away from heat sources and do not place heavy objects on it.",
                "Do not open the back cover. There are no user-serviceable parts inside and high voltages are present.",
                "Leave at least 10 cm of clearance around the TV for ventilation. Do not block the ventilation slots.",
                "Do not install the TV in direct sunlight, near a stove, or in a bathroom or other humid place.",
                "Place the TV on a stable, level surface that can support its weight, or mount it on a wall that can.",
                f"{'Two or more people are required to lift and carry this TV.' if heavy else 'Lift the TV with both hands, holding the frame, not the screen.'}",
                "Never let children climb on or hang from the TV or its furniture. Secure the TV to the wall with an "
                "anti-tip strap if it is not wall mounted.",
                "Keep the remote control batteries away from children. If a battery is swallowed, seek medical help immediately.",
                "Listening at high volume for long periods with headphones can damage your hearing.",
                "If the TV emits smoke, a burning smell or unusual noise, unplug it immediately and contact customer care.",
            ]),
        ],
    )


def _box_section(tv: dict, brand: dict) -> Section:
    items = [
        f"{full_name(tv)} television (model {tv['model_number']})",
        f"{brand['remote']} with 2 x AAA batteries",
        "Table-top stand (2 feet) with 4 stand screws",
        "Power cord (1.5 m)",
        "Quick start guide and warranty card",
    ]
    if tv["screen_size_in"] >= 65:
        items.append("Wall-mount bracket with screws (included free with 65-inch models)")
    return Section(
        id="box", title="What Is in the Box", facts={"items": items},
        blocks=[
            Paragraph("Check that all of the items below are present when you unpack the TV. If anything is missing or "
                      "damaged, contact customer care within 7 days of delivery.", enrich=True),
            Bullets(items),
            Notice("Note: Keep the original packaging for at least the warranty period. It provides the best protection "
                   "if the TV ever needs to be transported for service.", kind="note"),
        ],
    )


def _overview_section(tv: dict, brand: dict) -> Section:
    hdmi_note = (f"{tv['hdmi21_ports']} of the {tv['hdmi_ports']} HDMI ports support HDMI 2.1 (4K at "
                 f"{tv['refresh_hz']} Hz)" if tv["hdmi21_ports"] else "All HDMI ports are HDMI 2.0 (4K at 60 Hz)")
    ports = [
        ["HDMI", str(tv["hdmi_ports"]), f"{hdmi_note}. {tv['earc_port']} connects a soundbar or AV receiver."],
        ["USB", str(tv["usb_ports"]), "For USB drives (FAT32, exFAT or NTFS read-only) and keyboards."],
        ["LAN (Ethernet)", "1", "Wired internet connection; recommended for 4K streaming."],
        ["Optical audio out", "1", "Digital audio output for older soundbars and amplifiers."],
        ["RF / Antenna in", "1", "For a set-top box RF output or terrestrial antenna."],
        ["Headphone out (3.5 mm)", "1", "Wired headphones; TV speakers mute when connected."],
    ]
    remote = [
        ["Power", "Turns the TV on or puts it into standby."],
        ["Microphone", f"Press and hold to talk to {brand['assistant']}."],
        ["Home", f"Opens the {brand['os']} home screen."],
        ["Input / Source", "Switches between HDMI, USB and other inputs."],
        ["Navigation ring and OK", "Moves the selection and confirms choices."],
        ["Back", "Returns to the previous screen."],
        ["Settings (gear)", "Opens the quick settings menu."],
        ["Volume and Channel", "Adjusts volume and changes channels on the connected set-top box."],
        ["App shortcut keys", "Open preinstalled streaming apps directly."],
    ]
    return Section(
        id="overview", title="Product Overview",
        facts={"hdmi_ports": tv["hdmi_ports"], "hdmi21_ports": tv["hdmi21_ports"], "earc_port": tv["earc_port"],
               "usb_ports": tv["usb_ports"], "remote": brand["remote"]},
        blocks=[
            Paragraph(f"The {full_name(tv)} has a slim bezel design with the power button and status light located under "
                      "the centre of the bottom bezel. The status light glows red in standby and switches off when the TV "
                      "is on.", enrich=True),
            Subheading("Rear and side panel connections"),
            Table(header=["Port", "Quantity", "Description"], rows=ports, col_widths=[0.22, 0.12, 0.66],
                  caption=f"Connection ports on the {full_name(tv)}"),
            Subheading(f"{brand['remote']}"),
            Paragraph(f"The {brand['remote']} uses Bluetooth, so it does not need to be pointed at the TV. Pair it the "
                      "first time you switch on the TV by following the on-screen instruction."),
            Table(header=["Button", "Function"], rows=remote, col_widths=[0.3, 0.7], caption="Remote control buttons"),
        ],
    )


def _installation_section(tv: dict) -> Section:
    return Section(
        id="installation", title="Installation",
        facts={"vesa": tv["vesa"], "wall_screw": tv["wall_screw"], "weight_no_stand_kg": tv["weight_no_stand_kg"]},
        blocks=[
            Paragraph("You can place the TV on a table using the supplied stand or mount it on a wall. Free installation "
                      "and demonstration is provided by an authorised technician; book it by calling customer care after "
                      "delivery.", enrich=True),
            Subheading("Attaching the table-top stand"),
            Bullets([
                "Spread a soft cloth on a flat table and lay the TV screen-side down.",
                "Insert the two stand feet into the slots at the bottom of the TV, marked L and R.",
                "Fasten each foot with the supplied stand screws using a Phillips screwdriver. Do not over-tighten.",
                "Lift the TV upright and place it on a surface wider than the distance between the feet.",
            ], ordered=True),
            Subheading("Wall mounting"),
            Paragraph(f"This TV uses a VESA {tv['vesa']} mounting pattern with {tv['wall_screw']} screws. The TV weighs "
                      f"{tv['weight_no_stand_kg']} kg without the stand; make sure the wall and bracket can support at least "
                      "four times this weight. Using screws longer than specified can damage internal components."),
            Notice("Caution: Wall mounting must be done by a qualified installer. The manufacturer is not liable for "
                   "damage or injury caused by incorrect mounting or by a bracket that is not suitable for the TV.",
                   kind="caution"),
            Subheading("Viewing distance"),
            Paragraph(f"For a {tv['screen_size_in']}-inch 4K TV, the recommended viewing distance is between 1 and 1.5 "
                      "times the screen diagonal. Place the centre of the screen at eye level when seated."),
        ],
    )


def _setup_section(tv: dict, brand: dict) -> Section:
    return Section(
        id="setup", title="First-Time Setup",
        facts={"os": brand["os"], "app": brand["app"]},
        blocks=[
            Paragraph(f"When you switch on the TV for the first time, the {brand['os']} setup assistant guides you through "
                      "the initial configuration. Keep your Wi-Fi password ready.", enrich=True),
            Bullets([
                "Insert the batteries into the remote and press the Power button.",
                "Follow the on-screen prompt to pair the remote by pressing the Home and Back buttons together.",
                "Select your language and country (India). The country selection sets the time zone and app store region.",
                "Connect to the internet using Wi-Fi or an Ethernet cable.",
                f"Sign in with your account or scan the QR code with the {brand['app']} to set up quickly.",
                "Accept the terms of use and privacy notice. You can change privacy choices later in the settings.",
                "Select the inputs you use, such as a set-top box on HDMI 1 or a game console on HDMI 2.",
                "Allow the TV to download and install any available software update before first use.",
            ], ordered=True),
            Paragraph(f"You can rerun the setup assistant at any time from {_settings_root(tv)} > General > Reset, which "
                      "restores factory settings. The default parental control PIN is 0000."),
        ],
    )


def _picture_sound_section(tv: dict) -> Section:
    modes = [f"**{m}**: {PICTURE_MODE_HELP.get(m, 'a preset picture mode')}." for m in tv["picture_modes"]]
    atmos = (f"This model supports Dolby Atmos through its {tv['speaker_w']} W {tv['speaker_channels']} speaker system and "
             "can pass Dolby Atmos to a compatible soundbar." if tv["dolby_atmos"] else
             f"This model has a {tv['speaker_w']} W {tv['speaker_channels']} speaker system. Dolby Atmos is not supported "
             "on the built-in speakers.")
    return Section(
        id="picture_sound", title="Picture and Sound",
        facts={"picture_modes": tv["picture_modes"], "hdr": tv["hdr"], "speaker_w": tv["speaker_w"],
               "dolby_atmos": tv["dolby_atmos"]},
        blocks=[
            Paragraph("The TV analyses each scene and adjusts contrast, colour and sharpness automatically. You can "
                      "choose a picture mode to suit the content and the room.", enrich=True),
            Subheading("Picture modes"),
            Bullets(modes),
            Subheading("HDR"),
            Paragraph(f"The TV supports the following HDR formats: {', '.join(tv['hdr'])}. HDR mode switches on "
                      "automatically when HDR content is detected, and an HDR badge appears briefly in the top corner."),
            Subheading("Sound"),
            Paragraph(atmos),
            Paragraph(f"To use a soundbar, connect it to {tv['earc_port']} and turn on HDMI-CEC so that the TV remote "
                      "controls the soundbar volume."),
        ],
    )


def _gaming_section(tv: dict) -> Section:
    if tv["vrr"]:
        text = (f"The {full_name(tv)} supports Variable Refresh Rate (VRR) and Auto Low Latency Mode (ALLM) at up to "
                f"{tv['refresh_hz']} Hz on its HDMI 2.1 ports. Connect your console to an HDMI 2.1 port using an Ultra "
                "High Speed HDMI cable and enable Game Mode for the lowest input lag.")
    else:
        text = (f"The {full_name(tv)} supports Auto Low Latency Mode (ALLM), which switches the TV to Game mode "
                f"automatically when a console is detected. This model does not support Variable Refresh Rate (VRR), and "
                f"the maximum refresh rate is {tv['refresh_hz']} Hz. Set your console output to 4K at 60 Hz.")
    return Section(
        id="gaming", title="Gaming Features",
        facts={"vrr": tv["vrr"], "allm": tv["allm"], "refresh_hz": tv["refresh_hz"], "hdmi21_ports": tv["hdmi21_ports"]},
        blocks=[
            Paragraph("Game Mode reduces input lag by bypassing most picture processing, so that your actions on the "
                      "controller appear on screen as quickly as possible.", enrich=True),
            Paragraph(text),
            Paragraph(f"Open the Game Bar during play by pressing and holding the Settings button. It shows the current "
                      "frame rate, HDR status and input lag mode."),
        ],
    )


def _smart_section(tv: dict, brand: dict) -> Section:
    return Section(
        id="smart", title="Smart Features and Connectivity",
        facts={"os": brand["os"], "assistant": brand["assistant"], "wifi": tv["wifi"], "bluetooth": tv["bluetooth"],
               "app": brand["app"]},
        blocks=[
            Paragraph(f"{brand['os']} gives you access to thousands of streaming apps, live channels and games, with "
                      "personalised recommendations on the home screen.", enrich=True),
            Bullets([
                f"**Voice control**: press and hold the microphone button to ask {brand['assistant']} to search for "
                "content, open apps or change settings.",
                "**Screen mirroring**: cast photos and videos from a phone connected to the same Wi-Fi network.",
                f"**Bluetooth audio**: connect wireless headphones or speakers (Bluetooth {tv['bluetooth']}).",
                f"**Wi-Fi**: {tv['wifi']}. For 4K streaming, a connection of at least 25 Mbps is recommended.",
                f"**{brand['app']}**: use your phone as a remote and keyboard, and share content to the TV.",
                "**Kids profile**: restrict apps and content by age rating with a PIN.",
            ]),
        ],
    )


def _settings_section(tv: dict) -> Section:
    root = _settings_root(tv)
    light = "OLED Light" if tv.get("oled") else "Backlight"
    rows = [
        [f"{root} > Picture > Picture Mode", ", ".join(tv["picture_modes"])],
        [f"{root} > Picture > {light}", "0 to 100"],
        [f"{root} > Picture > Motion Smoothing", "Off, Low, Medium, High"],
        [f"{root} > Sound > Sound Mode", "Standard, Movie, Music, Dialogue Clarity"],
        [f"{root} > Sound > Sound Output", "TV Speaker, HDMI ARC/eARC, Optical, Bluetooth"],
        [f"{root} > Sound > AV Sync", "Adjusts audio delay to match the picture"],
        [f"{root} > Connection > Network", "Wi-Fi, Ethernet, network status"],
        [f"{root} > Connection > HDMI-CEC", "On, Off"],
        [f"{root} > Connection > HDMI Signal Format", "Standard, Enhanced (per HDMI port)"],
        [f"{root} > General > Power and Energy > Auto Power Off", "Off, after 4 hours without input"],
        [f"{root} > General > Parental Controls", "Content ratings, app locks, PIN change"],
        [f"{root} > Support > Software Update", "Update now, Auto update On or Off"],
        [f"{root} > Support > Self Diagnosis", "Picture test, sound test, signal information"],
        [f"{root} > General > Reset", "Restores factory settings (PIN required)"],
    ]
    if tv["vrr"]:
        rows.insert(9, [f"{root} > Connection > Game Optimiser", "VRR, ALLM, Input Lag Boost"])
    return Section(
        id="settings", title="Settings Menu Reference", facts={"menu_root": root},
        blocks=[
            Paragraph(f"Press the Settings button on the remote and select All Settings to open the full {root} menu. "
                      "The table below lists the most frequently used options.", enrich=True),
            Table(header=["Menu path", "Options"], rows=rows, col_widths=[0.55, 0.45], caption="Frequently used settings"),
        ],
    )


def _care_section(tv: dict) -> Section:
    blocks = [
        Paragraph("Regular, gentle care keeps the TV looking good and working reliably for years.", enrich=True),
        Bullets([
            "Switch off and unplug the TV before cleaning.",
            "Wipe the screen gently with a dry microfibre cloth. Do not spray liquid directly onto the screen.",
            "Never use alcohol, ammonia, thinners or abrasive cleaners on the screen or cabinet.",
            "Dust the ventilation slots every month with a soft brush.",
            "Avoid displaying static images, such as news tickers or paused games, for long periods.",
            "Enable Eco mode or reduce brightness to lower electricity consumption.",
        ]),
    ]
    if tv.get("oled"):
        blocks += [
            Subheading("OLED panel care"),
            Paragraph("OLED pixels emit their own light. To keep brightness uniform, the TV runs a short pixel refresh "
                      "automatically after every 4 hours of cumulative viewing when it is switched to standby. Do not unplug "
                      "the TV immediately after switching it off. A full pixel refresher, which takes about 60 minutes, can "
                      "be run manually from Menu > Support > OLED Care, but should not be run more than once a month."),
            Notice("Caution: Image retention caused by displaying static content for long periods (burn-in) is not "
                   "covered by the warranty.", kind="caution"),
        ]
    return Section(id="care", title="Care and Maintenance", facts={"oled": bool(tv.get("oled"))}, blocks=blocks)


def _troubleshooting_section(tv: dict, brand: dict) -> Section:
    root = _settings_root(tv)
    rows = [
        ["TV does not turn on", "Power cord loose or wall socket switched off",
         "Check both ends of the power cord, switch on the socket and press the power button under the bezel."],
        ["Status light blinks and TV stays off", "Protection mode after a power surge",
         "Unplug the TV for 2 minutes, plug it back in and switch it on."],
        ["Sound but no picture", "Screen Off mode or backlight set to 0",
         f"Press any button to exit Screen Off mode and check {root} > Picture."],
        ["Picture but no sound", "Sound output set to an external device or mute on",
         f"Set {root} > Sound > Sound Output to TV Speaker and press the Volume key."],
        ["Remote does not respond", "Weak batteries or remote not paired",
         "Replace both AAA batteries and pair again by holding Home and Back for 5 seconds."],
        ["No signal message", "Wrong input selected or source device off",
         "Select the correct input with the Input button and switch on the source device."],
        ["Colours look washed out in HDR", "HDMI port set to Standard signal format",
         f"Set {root} > Connection > HDMI Signal Format to Enhanced for that port."],
        ["Wi-Fi disconnects frequently", "Weak signal or congested 2.4 GHz band",
         "Move the router closer, use the 5 GHz band or connect an Ethernet cable."],
        ["Apps are slow or close unexpectedly", "Low free storage",
         "Clear app cache, uninstall unused apps and keep at least 1 GB of storage free."],
        ["Soundbar has no sound over HDMI", "HDMI-CEC disabled or wrong port",
         f"Enable HDMI-CEC and connect the soundbar to {tv['earc_port']}."],
        ["Audio is out of sync with the picture", "Delay in external audio device",
         f"Adjust {root} > Sound > AV Sync until speech matches lip movement."],
        ["TV turns off by itself", "Sleep timer or Auto Power Off active",
         f"Turn off the sleep timer and set {root} > General > Power and Energy > Auto Power Off to Off."],
        ["Screen mirroring fails", "Phone and TV on different networks",
         "Connect both devices to the same Wi-Fi network and restart screen mirroring."],
        ["Voice commands not recognised", "Microphone permission off",
         f"Allow microphone access for {brand['assistant']} in the privacy settings."],
        ["USB drive not detected", "Unsupported file system or drive needs more power",
         "Format the drive as FAT32 or exFAT, or use a drive with its own power supply."],
    ]
    if tv["vrr"]:
        rows.append(["Screen flickers during games", "VRR range mismatch with the console",
                     "Turn VRR off and on in Game Optimiser, or limit the console output to 120 Hz."])
    else:
        rows.append(["Console shows a blank screen at 120 Hz", f"This model supports up to {tv['refresh_hz']} Hz only",
                     "Set the console video output to 4K at 60 Hz."])
    if tv.get("oled"):
        rows.append(["Faint ghost image remains on screen", "Temporary image retention",
                     "Leave the TV in standby with power connected so the pixel refresh can run."])
    else:
        rows.append(["Uneven brightness in dark scenes", "Normal characteristic of LED backlights",
                     "Enable Local Dimming if available or reduce the Backlight setting."])
    return Section(
        id="troubleshooting", title="Troubleshooting",
        facts={"rows": len(rows)},
        blocks=[
            Paragraph("Before contacting customer care, check the table below. Many common issues can be resolved in a "
                      "few minutes. Also make sure the TV software is up to date.", enrich=True),
            Table(header=["Symptom", "Possible cause", "Solution"], rows=rows, col_widths=[0.27, 0.28, 0.45],
                  caption=f"Troubleshooting guide for the {full_name(tv)}"),
        ],
    )


def _error_section(tv: dict, brand: dict) -> Section:
    return Section(
        id="error_codes", title="Error Codes",
        facts={"codes": [c[0] for c in tv["error_codes"]]},
        blocks=[
            Paragraph(f"If the TV detects a problem it displays an error code beginning with {brand['error_prefix']} in a "
                      "message box. Note the code before contacting customer care.", enrich=True),
            Table(header=["Code", "Meaning", "What to do"], rows=[list(c) for c in tv["error_codes"]],
                  col_widths=[0.12, 0.38, 0.5], caption=f"Error codes for model {tv['model_number']}"),
        ],
    )


def build(tv: dict) -> Document:
    brand = BRANDS[tv["brand"]]
    name = full_name(tv)
    sibs = siblings(tv, TVS)
    warranty_rows = [
        ["Television (comprehensive)", years(tv["warranty_years"])],
        ["Display panel", years(tv["panel_warranty_years"])],
        ["Remote control", "6 months"],
        ["Stand, power cord and accessories", "6 months"],
    ]
    exclusions = [
        "Physical damage, cracked screens and liquid damage.",
        "Damage caused by voltage fluctuation beyond the specified range, lightning or fire.",
        "Repairs or modifications by persons other than authorised service centres.",
        "Commercial use, such as in hotels, shops or offices, unless covered by a commercial warranty.",
        "Consumables such as remote batteries.",
    ]
    if tv.get("oled"):
        exclusions.append("Image retention (burn-in) caused by static images.")
    sections = [
        about_section(tv, brand, "television", sibs),
        _safety_section(tv),
        _box_section(tv, brand),
        _overview_section(tv, brand),
        _installation_section(tv),
        _setup_section(tv, brand),
        _picture_sound_section(tv),
        _gaming_section(tv),
        _smart_section(tv, brand),
        _settings_section(tv),
        _care_section(tv),
        _troubleshooting_section(tv, brand),
        _error_section(tv, brand),
        Section(id="specs", title="Technical Specifications", facts={},
                blocks=[Table(header=["Specification", name], rows=spec_rows(tv), col_widths=[0.4, 0.6],
                              caption=f"Specifications of the {name} ({tv['model_number']})")]),
        warranty_section(tv, brand, warranty_rows, registration_days=30, exclusions=exclusions),
        regulatory_section(tv, brand, "IS 616:2017 (Audio, video and similar electronic apparatus - Safety requirements)"),
        support_section(tv, brand),
    ]
    product_line = f"{tv['screen_size_in']}-inch {tv['panel'].split(' with ')[0]} Smart TV"
    meta = DocMeta(
        doc_id=tv["doc_id"],
        title=f"{name} User Manual",
        subtitle=product_line,
        category="product_manual",
        subcategory="tv",
        publisher=brand["legal_name"],
        version=MANUAL_VERSION,
        effective_date=PUBLISHED,
        filename=f"{tv['doc_id']}_{name.replace(' ', '_')}_User_Manual.pdf",
        relative_dir="product_manuals/tv",
        page_range=(5, 10),
        brand=tv["brand"],
        model=tv["model"],
        model_number=tv["model_number"],
        family=tv["family"],
        keywords=["television", "user manual", tv["brand"], tv["model"], tv["model_number"]],
        sibling_models=sibs,
    )
    return Document(meta=meta, sections=sections, facts=tv,
                    cover=cover_fields(tv, brand, product_line, MANUAL_VERSION, PUBLISHED))
