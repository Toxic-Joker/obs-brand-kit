"""The scene collection, described once. obs.py and streamlabs.py only translate this.

Structure follows the Tokyo Nights reference (Starting, Facecam/Gameplay, Just Chatting, BRB,
Match Reacts, Ending), cleaned up: each source exists once and is shared between scenes, alerts
live in one nested scene, mic/desktop audio are global devices. Coordinates are 1920x1080 pixels.
"""
W, H = 1920, 1080

# Placeholder widget URLs. about:blank renders transparent, so nothing shows until the
# streamer pastes their own link; the text after # says which link goes there.
def placeholder(what):
    return f"about:blank#PASTE_YOUR_{what}_URL"

# Streamlabs widget type ids (stream-labs/desktop app/services/widgets/widgets-data.ts)
SL_ALERT_BOX, SL_CHAT_BOX, SL_EVENT_LIST, SL_VIEWER_COUNT, SL_SUB_GOAL = 0, 6, 7, 9, 15
SL_TIP_GOAL, SL_BITS_GOAL = 1, 4

def sources(b, a):
    """name -> source spec. `a` is the asset manifest (file, w, h per asset)."""
    S = {}
    def media(name, key, loop=True, clear_end=False):
        S[name] = {"kind": "media", "asset": key, "loop": loop, "clear_end": clear_end, "w": a[key]["w"], "h": a[key]["h"]}
    def image(name, key):
        S[name] = {"kind": "image", "asset": key, "w": a[key]["w"], "h": a[key]["h"]}
    def browser(name, what, w, h, sl=None, audio=False):
        S[name] = {"kind": "browser", "url": placeholder(what), "w": w, "h": h, "sl_widget": sl, "audio": audio}

    media("Starting Soon (bg)", "screen_starting")
    media("Be Right Back (bg)", "screen_brb")
    media("Ending (bg)", "screen_ending")
    media("Background Loop", "bg_loop")
    media("Lower Third", "lower_third", loop=False, clear_end=True)
    media("Socials Rotator", "socials_rotator")
    image("Socials Row", "socials_row")
    image("Webcam Frame (large)", "cam_frame_lg")
    image("Webcam Frame (small)", "cam_frame_sm")
    image("Chat Panel", "chat_panel")
    image("Latest Label", "label")
    image("Brand Tag", "brand_tag")
    S["Topic (edit me)"] = {"kind": "text", "text": "Today: edit this line", "size": 40, "font": b.fonts["body"],
                            "color": b.palette["text"],
                            "outline": b.palette["outline"] if b["style"]["title"] == "bubble" else None}
    S["Webcam"] = {"kind": "webcam"}
    S["Game Capture"] = {"kind": "game"}
    S["Content (pick a window)"] = {"kind": "window"}
    S["Music (pick the app)"] = {"kind": "app_audio"}
    browser("Alert Box", "STREAMLABS_ALERTBOX", 800, 600, SL_ALERT_BOX, audio=True)
    browser("Media / Sound Alerts", "MEDIA_OR_SOUND_ALERTS", 1920, 1080, audio=True)
    browser("Chat Box", "CHAT_BOX", 448, 620, SL_CHAT_BOX)
    browser("Latest Events", "EVENT_LIST", 280, 48, SL_EVENT_LIST)
    browser("Viewer Count", "VIEWER_COUNT", 400, 60, SL_VIEWER_COUNT)
    browser("Sub Goal", "SUB_GOAL", 600, 72, SL_SUB_GOAL)
    browser("Tip Goal", "TIP_GOAL", 600, 72, SL_TIP_GOAL)
    browser("Bits Goal", "BITS_GOAL", 600, 72, SL_BITS_GOAL)
    browser("Now Playing", "NOW_PLAYING", 480, 80)
    if "screen_starting_v" in a:  # vertical canvas sources
        media("Starting Soon (bg V)", "screen_starting_v")
        media("Be Right Back (bg V)", "screen_brb_v")
        media("Ending (bg V)", "screen_ending_v")
        media("Background Loop (V)", "bg_loop_v")
        image("Socials Column", "socials_col")
    S["[S] Alerts"] = {"kind": "scene"}
    S["[S] Audio"] = {"kind": "scene"}
    return S

def item(source, x=0, y=0, w=None, h=None, visible=True, center=False, bounds=False, fill=False):
    """w/h: target size on canvas (scale is derived). bounds: fit the source inside w x h
    (for webcams and captures whose resolution we can't know). fill: cover w x h, cropping the
    overflow (a 16:9 webcam filling a portrait area)."""
    return {"source": source, "x": x, "y": y, "w": w, "h": h, "visible": visible, "center": center,
            "bounds": bounds or fill, "fill": fill}

def scenes(b, a):
    """Ordered list of (scene name, [items bottom -> top]). Nested scenes come last.
    brand.layout picks between variants: just_chatting framed|fullcam, chat panel|floating,
    chat_on_screens (chat over Starting / BRB / Ending, on the right)."""
    L = b["layout"]
    floating = L["chat"] == "floating"
    row_w, row_h = a["socials_row"]["w"], a["socials_row"]["h"]
    rot_w = a["socials_rotator"]["w"]
    socials_row = item("Socials Row", (W - row_w) // 2, 990 - row_h // 2)
    shared = [item("[S] Alerts"), item("[S] Audio")]

    def cam(x, y, iw, ih, frame):
        st = a["cam_frame_lg" if "large" in frame else "cam_frame_sm"].get("inset", 3)
        return [item("Webcam", x, y, iw, ih, bounds=True), item(frame, x - st, y - st)]

    def chat(x, y, w, h):
        """Chat area at x,y of w x h: a branded panel with the widget inside, or the widget alone."""
        if floating:
            return [item("Chat Box", x, y, w, h * 620 / 720)]
        k = w / 480
        return [item("Chat Panel", x, y, w, h), item("Chat Box", x + 16 * k, y + 84 * k, 448 * k, 620 * k)]

    screen_chat = chat(1340, 300, 440, 600) if L["chat_on_screens"] else []
    def screen(bg, extra=()):
        return [item(bg), *extra, *screen_chat, socials_row, *shared]

    goals = [item("Tip Goal", 40, 760, 600, 72), item("Sub Goal", 40, 840, 600, 72),
             item("Bits Goal", 40, 920, 600, 72, visible=False)]
    if L["just_chatting"] == "fullcam":
        just_chatting = [
            item("Webcam", 0, 0, W, H, bounds=True),
            *chat(1420, 260, 460, 720),
            *goals,
            item("Socials Rotator", 24, 24),
            item("Lower Third", 40, 560),
            *shared,
        ]
    else:
        just_chatting = [
            item("Background Loop"),
            item("Brand Tag", 64, 52),
            *cam(64, 150, 1280, 720, "Webcam Frame (large)"),
            *chat(1376, 150, 480, 720),
            item("Now Playing", 1376, 900, 480, 80),
            item("Sub Goal", 700, 950, 600, 72, visible=False),
            item("Socials Rotator", 56, 930),
            item("Lower Third", 84, 690),
            *shared,
        ]
    gameplay = [
        item("Game Capture", 0, 0, W, H, bounds=True),
        item("Latest Label", 32, 740),
        item("Latest Events", 32 + 128, 744, 280, 48),
        *cam(32, 812, 384, 216, "Webcam Frame (small)"),
        item("Socials Rotator", W - 24 - rot_w, 24),
        item("Chat Box", 1450, 300, 448, 620, visible=False),
        item("Viewer Count", 1496, 1000, 400, 60, visible=False),
        *shared,
    ]
    react = [
        item("Background Loop"),
        item("Content (pick a window)", 32, 32, 1440, 810, bounds=True),
        *cam(1504, 40, 384, 216, "Webcam Frame (small)"),
        *chat(1504, 300, 384, 576),
        item("Viewer Count", 32, 880, 400, 60),
        item("Socials Rotator", 24, 960),
        item("Brand Tag", 1504, 980),
        *shared,
    ]
    topic_y = 880 if b["style"]["title"] == "bubble" else 800
    return [
        ("Starting Soon", screen("Starting Soon (bg)", [item("Topic (edit me)", 960, topic_y, center=True)])),
        ("Just Chatting", just_chatting),
        ("Gameplay", gameplay),
        ("React", react),
        ("Be Right Back", screen("Be Right Back (bg)")),
        ("Ending", screen("Ending (bg)")),
        ("[S] Alerts", [item("Media / Sound Alerts", 0, 0, W, H), item("Alert Box", (W - 800) // 2, 40, 800, 600)]),
        ("[S] Audio", [item("Music (pick the app)")]),
    ]

FIRST_SCENE = "Starting Soon"

# ---------------------------------------------------------------- vertical canvas
VW, VH = 1080, 1920
VERTICAL_CANVAS = "Aitum Vertical"   # the Aitum Vertical plugin finds its canvas by this name
V = " (V)"                           # vertical scene names: "Gameplay (V)" ...

def vertical_scenes(b, a):
    """1080x1920 scenes for the vertical canvas, same sources as horizontal (one webcam, one alert box).
    Proportions follow the reference: full-height cam for chatting, cam over game for gameplay,
    stacked socials on the screens; labels, goals and viewer counts stay horizontal-only."""
    if "screen_starting_v" not in a:
        return []
    cw, chh = a["socials_col"]["w"], a["socials_col"]["h"]
    socials = item("Socials Column", (VW - cw) // 2, VH - chh - 150)
    alerts = [item("Media / Sound Alerts", 0, 420, VW, 608), item("Alert Box", 90, 300, 900, 675),
              item("Music (pick the app)")]
    def screen(bg, extra=()):
        return [item(bg), *extra, socials, *alerts]
    def framed_cam(x, y, iw, frame_key, frame):
        """Webcam iw wide (16:9) with the brand frame scaled to match."""
        f = a[frame_key]; inner = f["w"] - 2 * f.get("inset", 3)
        k = iw / inner; ih = iw * 9 / 16
        return [item("Webcam", x, y, iw, ih, bounds=True),
                item(frame, x - f.get("inset", 3) * k, y - f.get("inset", 3) * k, f["w"] * k, f["h"] * k)]
    chat_w = 470
    return [
        ("Starting Soon" + V, screen("Starting Soon (bg V)", [  # topic line sits above the socials column
            item("Topic (edit me)", VW // 2, min(1290, VH - chh - 150 - 70), center=True)])),
        ("Just Chatting" + V, [
            item("Webcam", 0, 0, VW, VH, fill=True),
            item("Chat Box", 40, 1180, chat_w, chat_w * 620 / 448),
            item("Socials Rotator", 40, 80),
            item("Lower Third", 40, 1000),
            *alerts]),
        ("Gameplay" + V, [
            item("Webcam", 0, 0, VW, 760, fill=True),
            item("Game Capture", 0, 760, VW, VH - 760, fill=True),
            item("Socials Rotator", 40, 712),
            *alerts]),
        ("React" + V, [
            item("Background Loop (V)"),
            item("Content (pick a window)", 0, 160, VW, 608, bounds=True),
            *framed_cam(60, 860, 960, "cam_frame_lg", "Webcam Frame (large)"),
            item("Brand Tag", 60, 1490),
            item("Socials Rotator", 52, 1590),
            *alerts]),
        ("Be Right Back" + V, screen("Be Right Back (bg V)")),
        ("Ending" + V, screen("Ending (bg V)")),
    ]
