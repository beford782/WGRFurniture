#!/usr/bin/env python3
"""Generate the WG&R Furniture onboarding workbook from the approved v1 mapping.

Builds an .xlsx whose tab/column headers come from the repo's shared
tools/workbook_schema.py (so they cannot drift from what the converter reads).
Spanish columns are intentionally left blank (languages = en only).

Output: incoming/WGR_Store_Data.xlsx
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import workbook_schema as schema  # noqa: E402
import openpyxl  # noqa: E402

OUT = os.path.join(HERE, "WGR_Store_Data.xlsx")

# ---- Store Info (one row) ---------------------------------------------------
STORE = {
    "Store Name": "WG&R Furniture",
    "Store Key": "wgr",
    "Languages": "en",
    "Logo Line 1": "WG&R",
    "Logo Line 2": "furniture",
    "Primary Color (hex)": "#B12D15",
    "Primary Color Light (hex)": "#C8402A",
    "Primary Color Glow (rgba)": "rgba(177,45,21,0.15)",
    "Accent Color (hex)": "#B8935D",
    "GAS URL": "",
    "Public Asset Root": "https://beford782.github.io/WGRFurniture/",
    "Allowed Hosts": "beford782.github.io",
    "Discount Code Prefix": "DREAM",
    "Discount Code Digits": 3,
    "Page Title": "DreamFinder - WG&R Furniture Sleep Quiz",
    "Meta Description": "Take the WG&R Sleep Shop quiz and get personalized mattress recommendations.",
    "OG Title": "DreamFinder - WG&R Furniture",
    "Trust Signal": "Serving Northeast Wisconsin since 1946 — proudly employee-owned",
    "Heritage": "EST. 1946 · EMPLOYEE-OWNED · NORTHEAST WISCONSIN",
    "Email Privacy": "We'll only use your email to send your results.",
    "Privacy Policy Contact": "",
    "In-Stock Text": "In stock at WG&R",
    "Email Header": "WG&R Furniture x DreamFinder",
    "Email Subtext": "Your personalized mattress matches",
    "Location Label": "Northeast Wisconsin",
    "Voice Eyebrow": "WG&R Sleep Consultation",
    "Voice Headline Main": "Let's find the mattress",
    "Voice Headline Accent": "made for how you sleep",
    "Voice Sub-Copy Before": "Answer a few questions and our sleep specialists will match you to the right mattress — proudly ",
    "Voice Sub-Copy Accent": "employee-owned in Northeast Wisconsin since 1946",
    "Voice Sub-Copy After": ".",
    "Voice CTA Primary": "Start My Sleep Consultation",
    "Voice Time Estimate": "About 2 minutes, no pressure",
    "Manifest Name": "DreamFinder - WG&R Furniture",
    "Manifest Short Name": "DreamFinder",
    "Manifest Description": "Personalized sleep consultation for WG&R Furniture",
    "Manifest Start URL": "/WGRFurniture/",
    "Manifest Theme Color": "#0f1f33",
    "Manifest Background Color": "#0f1f33",
    "App Icon File": "",
}

# ---- Brands (logo file name blank -> text fallback for the demo) ------------
BRANDS = ["Tempur-Pedic", "Stearns & Foster", "PranaSleep", "Purple", "Beautyrest",
          "King Koil", "Sealy", "Casper", "Astor Park", "Nectar", "DreamCloud",
          "WG&R Factory Direct"]

# ---- Mattresses (26) --------------------------------------------------------
# tuple: (tier,id,name,brand,subBrand,archetype,displayPriority,firmnessScore,
#         firmnessLabel,displayBadges,highlight,locally,features,reason_default,topPick)
M = [
 ("gold","g1","Adapt 2.0 Medium","Tempur-Pedic","Adapt","Adaptive memory-foam flagship",1,5,"Medium",
  "Memory Foam|Pressure Relief|Medium","Molds to you for deep pressure relief","no",
  "pressureRelief|motionIsolation|support|medium",
  "Memory foam that molds to your body for deep pressure relief.",
  "TEMPUR material molds to you for pressure relief and zero motion transfer."),
 ("gold","g2","Pro Breeze 2.0 Medium Hybrid","Tempur-Pedic","Pro Breeze","Cooling adaptive hybrid",1,5,"Medium",
  "Cooling|Hybrid|Medium","Adaptive comfort, hybrid support, all-night cooling","no",
  "cooling|pressureRelief|support|hybrid|medium",
  "Adaptive foam comfort with hybrid bounce and all-night cooling.",
  "Sleeps cooler with TEMPUR comfort and responsive hybrid support."),
 ("gold","g3","Luxe Breeze 2.0 Firm","Tempur-Pedic","Luxe Breeze","Top-tier cooling firmness",1,7,"Firm",
  "Cooling|Firm|Pressure Relief","Our coolest TEMPUR, firm and supported","no",
  "cooling|support|firm|pressureRelief",
  "Our coolest sleep with firm, fully-supported comfort.",
  "Our coolest TEMPUR with firm, fully-supported all-night comfort."),
 ("gold","g4","Lux Estate Firm","Stearns & Foster","Lux Estate","Handcrafted firm luxury",1,7,"Firm",
  "Firm|Coil Support|Durable","Handcrafted firm coil support, built to last","no",
  "support|firm|durability|hybrid",
  "Firm, durable coil support handcrafted for lasting comfort.",
  "Precision coils deliver firm, durable support built to last."),
 ("gold","g5","Reserve Medium","Stearns & Foster","Reserve","Heirloom luxury comfort",1,5,"Medium",
  "Luxury Coil|Medium|Durable","Plush-yet-supported handcrafted luxury","no",
  "support|pressureRelief|durability|medium",
  "Premium coils and foams balanced for plush-yet-supported luxury.",
  "Handcrafted premium coils and foams for balanced, lasting luxury."),
 ("gold","g6","Asha Luxe Plush","PranaSleep","Asha","Talalay-latex wellness luxury",1,3,"Plush",
  "Talalay Latex|Plush|Durable","All-latex plush comfort, championship durability","no",
  "pressureRelief|plush|soft|durability",
  "All-natural Talalay latex plushness with championship durability.",
  "All-latex plush comfort with a warranty that outlasts the rest."),
 ("gold","g7","Rejuvenate","Purple","Rejuvenate","Premium GelFlex grid",1,5,"Medium",
  "GelFlex Grid|Cooling|Responsive","Cool, responsive GelFlex grid flagship","no",
  "pressureRelief|responsive|cooling|support|medium",
  "Purple's flagship GelFlex grid - cool, responsive, pressure-free.",
  "Purple's flagship grid for cooling, responsive, no-pressure sleep."),
 ("gold","g8","Black Series Three Medium","Beautyrest","Black","Premium pocketed-coil comfort",1,5,"Medium",
  "Pocketed Coil|Medium|Motion Isolation","Luxury medium feel, premium coil support","no",
  "support|pressureRelief|motionIsolation|medium",
  "Luxury medium comfort over premium pocketed-coil support.",
  "Luxury medium feel over Beautyrest's premium pocketed-coil support."),
 ("gold","g9","SmartLife Lotus 2.0","King Koil","SmartLife","Dual-adjustable smart bed",1,5,"Adjustable",
  "Smart Adjustable|Dual Firmness|Zoned","Smart dual-adjustable firmness, your way","no",
  "support|motionIsolation|responsive|zoned",
  "A smart bed that adjusts each side's firmness to you.",
  "Dial in each side's firmness with app-controlled smart support."),
 ("silver","s1","Purple Mattress","Purple","","The original GelFlex grid",1,5,"Medium",
  "GelFlex Grid|Cooling|Responsive","The original cooling, responsive Purple grid","no",
  "pressureRelief|responsive|cooling|medium",
  "The original Purple grid - cooling, responsive, and adaptive.",
  "Cooling, responsive grid comfort that adapts as you move."),
 ("silver","s2","Restore Firm","Purple","Restore","Responsive firm grid hybrid",1,7,"Firm",
  "Grid Hybrid|Firm|Responsive","Firm grid-over-coil with airflow","no",
  "support|responsive|firm|pressureRelief",
  "Firm grid-over-coil support with airflow and pressure relief.",
  "Firm grid-over-coil support with airflow and pressure relief."),
 ("silver","s3","Snow 3.0 Hybrid","Casper","Snow","Cool-sleeping zoned hybrid",1,5,"Medium",
  "Cooling|Zoned|Hybrid","Sleeps degrees cooler with zoned support","no",
  "cooling|zoned|pressureRelief|hybrid|medium",
  "Sleeps cooler with zoned support tuned for hot sleepers.",
  "Sleeps degrees cooler with zoned support for hot sleepers."),
 ("silver","s4","Dream Hybrid","Casper","Dream","Everyday cooling hybrid",1,5,"Medium",
  "Hybrid|Cooling|Medium","Balanced hybrid comfort and cooling","no",
  "hybrid|support|pressureRelief|medium",
  "Balanced hybrid comfort and cooling at an approachable price.",
  "Balanced hybrid comfort and cooling at an approachable price."),
 ("silver","s5","Brenham 2 Medium","Sealy","Posturepedic","Dependable everyday hybrid",1,5,"Medium",
  "Hybrid|Medium|Support","Dependable Sealy hybrid comfort","no",
  "support|hybrid|medium",
  "Trusted Sealy hybrid support for balanced everyday comfort.",
  "Trusted Sealy hybrid tuned for balanced all-night comfort."),
 ("silver","s6","High Point 2 Firm","Sealy","Posturepedic","Firm Sealy support",1,7,"Firm",
  "Hybrid|Firm|Support","Firm hybrid support, aligned all night","no",
  "support|firm|hybrid|durability",
  "Firm hybrid support that keeps your spine aligned.",
  "Firm hybrid support that keeps your spine aligned."),
 ("silver","s7","Black Series One Firm","Beautyrest","Black","Entry-premium firm coil",1,7,"Firm",
  "Pocketed Coil|Firm|Motion Isolation","Firm coil support, luxury feel","no",
  "support|firm|motionIsolation",
  "Firm pocketed-coil support with a true luxury feel.",
  "Firm Beautyrest pocketed-coil support with a luxury feel."),
 ("silver","s8","Midnight Bliss Plush","Astor Park","","Plush house-brand comfort, WI-made",2,3,"Plush",
  "WI-Made|Plush|Pressure Relief","Plush comfort, handcrafted in Wisconsin","yes",
  "cooling|pressureRelief|plush|soft",
  "Plush, pressure-relieving comfort, handcrafted in Wisconsin.",
  "Astor Park's plush, pressure-relieving comfort - handcrafted in Wisconsin."),
 ("silver","s9","Obsidian Firm","Astor Park","","Firm WI-made support",2,7,"Firm",
  "WI-Made|Firm|Durable","Firm support, handcrafted in Wisconsin","yes",
  "support|firm|durability",
  "Firm, supportive comfort, handcrafted in Wisconsin.",
  "Handcrafted Wisconsin firmness with dependable all-night support."),
 ("silver","s10","Luxe 5.1 Hybrid","Nectar","Luxe","Cooling value hybrid",1,5,"Medium",
  "Hybrid|Cooling|Motion Isolation","Cooling hybrid comfort for couples","no",
  "cooling|pressureRelief|motionIsolation|hybrid|medium",
  "Cooling hybrid comfort with great motion isolation for couples.",
  "Cooling hybrid comfort and motion isolation for couples."),
 ("bronze","b1","Classic 5.1","Nectar","Classic","Easy all-foam starter",1,5,"Medium",
  "Memory Foam|Cooling|Medium","Cooling foam comfort, budget-friendly","no",
  "cooling|pressureRelief|motionIsolation|medium",
  "Cooling bed-in-a-box comfort that won't break the budget.",
  "Cooling bed-in-a-box comfort that won't break the budget."),
 ("bronze","b2","Classic 5.1 Hybrid","Nectar","Classic","Value cooling hybrid",1,5,"Medium",
  "Hybrid|Cooling|Medium","Cooling hybrid bounce, starter price","no",
  "cooling|pressureRelief|hybrid|medium",
  "Hybrid bounce and cooling at a starter-friendly price.",
  "Hybrid bounce and cooling at a starter-friendly price."),
 ("bronze","b3","Classic Hybrid","DreamCloud","4.0","Luxury-feel value hybrid",1,6,"Medium-Firm",
  "Hybrid|Medium-Firm|Value","Plush-firm hybrid above its price","no",
  "support|hybrid|pressureRelief|medium",
  "A plush-firm hybrid that feels well above its price.",
  "A plush-firm hybrid that feels far above its price."),
 ("bronze","b4","Moreland Avenue Plush","Sealy","","Entry plush comfort",1,3,"Plush",
  "Plush|Soft|Value","Soft plush comfort, trusted value","no",
  "plush|soft|pressureRelief",
  "Soft, budget-friendly plush comfort from a name you trust.",
  "Soft, budget-friendly plush comfort from a name you know."),
 ("bronze","b5","Drake","WG&R Factory Direct","","Honest WI-made firm value",2,7,"Firm",
  "WI-Made|Firm|Value","Wisconsin-made firm support, great value","yes",
  "support|firm|durability",
  "Honest Wisconsin-made firm support at a great value.",
  "Wisconsin-made firm support at a guest-room-friendly price."),
 ("bronze","b6","Dreamweaver Medium Euro Top","Beautyrest","BeautySleep","Affordable everyday comfort",1,5,"Medium",
  "Euro Top|Medium|Value","Plush euro-top over solid support","no",
  "support|pressureRelief|medium",
  "Plush euro-top comfort over dependable innerspring support.",
  "Plush euro-top comfort over dependable innerspring support."),
 ("bronze","b7","Hybrid Premier","DreamCloud","4.0","Stepped-up value hybrid",1,5,"Medium",
  "Hybrid|Medium|Value","Stepped-up value hybrid comfort","no",
  "support|hybrid|pressureRelief|medium",
  "Extra foam and support stepped up from the entry hybrid.",
  "More foam and support than the entry hybrid, for a little more."),
]

MATT_COLMAP = ["tier","id","name","brand","subBrand","archetype","displayPriority",
               "firmnessScore","firmnessLabel","displayBadges","highlight",
               "locally-made","features","reason_default","topPickReason"]

def mattress_row(t):
    d = dict(zip(MATT_COLMAP, t))
    return {
        "tier": d["tier"], "id": d["id"], "name": d["name"], "brand": d["brand"],
        "subBrand": d["subBrand"], "pitchKey": "", "archetype": d["archetype"],
        "displayPriority": d["displayPriority"], "firmnessScore": d["firmnessScore"],
        "firmnessLabel": d["firmnessLabel"], "price": "", "quizTags": "",
        "displayBadges": d["displayBadges"], "highlight": d["highlight"],
        "locally-made": d["locally-made"], "features": d["features"],
        "reason_default": d["reason_default"], "topPickReason": d["topPickReason"],
    }

# ---- Accessories (12) -------------------------------------------------------
# (id,name,category,subType,price,desc,imageFull,matchTags,scores{})
A = [
 ("base-bedtech-relax","BedTech Relax Lifestyle Base","Foundations & Support","adjustable",899,
  "Adjustable power base with head & foot articulation, wireless remote, and memory positions.",
  "images/accessories/base-bedtech-relax.jpg","snoring, reflux, back_pain, all_positions",
  {"Score: Back Pain":4,"Score: Snoring":4,"Score: Premium":3}),
 ("base-tempur-ergo-smart","TEMPUR-Ergo Smart 3.0 Base","Foundations & Support","adjustable",2099,
  "Smart adjustable base with app control, head & foot adjustment, and sleep tracking.",
  "images/accessories/base-tempur-ergo-smart.jpg","snoring, reflux, back_pain",
  {"Score: Back Pain":4,"Score: Snoring":4,"Score: Premium":3}),
 ("base-purple-premium-plus","Purple Premium Plus Smart Base","Foundations & Support","adjustable",1595,
  "Smart adjustable base with app control and full head & foot articulation.",
  "images/accessories/base-purple-premium-plus.jpg","snoring, reflux, back_pain",
  {"Score: Back Pain":4,"Score: Snoring":4,"Score: Premium":3}),
 ("foundation-wgr-slate","WG&R Factory Direct Slate Foundation","Foundations & Support","foundation",179,
  "Sturdy standard-height foundation - solid platform support for any mattress.",
  "images/accessories/foundation-wgr-slate.jpg","all",{"Score: Default":2}),
 ("foundation-wgr-slate-lowpro","WG&R Slate Low-Profile Foundation","Foundations & Support","low_profile",179,
  "Reduced-height foundation - ideal for taller mattresses or a low-profile look.",
  "images/accessories/foundation-wgr-slate-lowpro.jpg","all",{"Score: Default":2}),
 ("bunkie-wgr","WG&R Factory Direct Bunkie Board","Foundations & Support","bunkie",59,
  "Slim 2-inch support board for platform and bunk beds.",
  "images/accessories/bunkie-wgr.jpg","all",{"Score: Default":1}),
 ("pillow-tempur-breeze-prolo","TEMPUR-Breeze ProLo 2.0 Pillow","Pillows","",225,
  "Cooling low-profile TEMPUR pillow for back and stomach sleepers.",
  "images/accessories/pillow-tempur-breeze-prolo.jpg","cooling, hot_sleeper, all",
  {"Score: Cooling":3,"Score: Hot":3,"Score: Position Back":2,"Score: Position Stomach":1}),
 ("pillow-tempur-proadjust","TEMPUR-Adapt ProAdjust Pillow","Pillows","",125,
  "Adjustable-fill TEMPUR pillow that customizes to any sleep position.",
  "images/accessories/pillow-tempur-proadjust.jpg","all, all_positions",
  {"Score: Default":2,"Score: Position Side":1,"Score: Position Back":1,"Score: Position Stomach":1}),
 ("pillow-cooltech-graphite","Healthy Sleep Cool-Tech Graphite Pillow","Pillows","",109,
  "Graphite-infused cooling pillow that draws heat away all night.",
  "images/accessories/pillow-cooltech-graphite.jpg","cooling, hot_sleeper",
  {"Score: Cooling":4,"Score: Hot":4,"Score: Position Side":1,"Score: Position Back":2}),
 ("protector-purple-waterproof","Purple Waterproof Protector","Protectors","",119,
  "Waterproof protector that guards your mattress while staying breathable.",
  "images/accessories/protector-purple-waterproof.jpg","all, allergies",
  {"Score: Default":1,"Score: Allergies":2}),
 ("protector-healthy-sleep-encasement","Healthy Sleep Premium Encasement","Protectors","",79,
  "Full-zip encasement - allergen and dust-mite barrier on all six sides.",
  "images/accessories/protector-healthy-sleep-encasement.jpg","allergies, all",
  {"Score: Allergies":3,"Score: Default":1}),
 ("protector-tempur-breeze","TEMPUR-Protect Breeze Protector","Protectors","",249,
  "Cooling protector that adds a breathable layer of protection.",
  "images/accessories/protector-tempur-breeze.jpg","cooling, hot_sleeper, all",
  {"Score: Cooling":3,"Score: Hot":2}),
]

def accessory_row(a):
    aid,name,cat,sub,price,desc,img,tags,scores = a
    row = {"ID":aid,"Name":name,"Category":cat,"Sub-Type":sub,"Price":price,
           "Description":desc,"Image File Name":img,"Match Tags":tags}
    row.update(scores)
    return row

# ---- write workbook ---------------------------------------------------------

def write_sheet(wb, tab, rows):
    ws = wb.create_sheet(title=tab)
    headers = schema.get_column_headers(tab)  # all columns (EN+ES), in order
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])

def main():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    write_sheet(wb, "Store Info", [STORE])
    write_sheet(wb, "Brands", [{"Brand Name": b, "Logo File Name": ""} for b in BRANDS])
    write_sheet(wb, "Mattresses", [mattress_row(t) for t in M])
    write_sheet(wb, "Accessories", [accessory_row(a) for a in A])
    write_sheet(wb, "SalesNotes", [])  # deferred / sparse for v1 (headers only)
    wb.save(OUT)
    print(f"Wrote {OUT}")
    print(f"  Brands: {len(BRANDS)}  Mattresses: {len(M)}  Accessories: {len(A)}  SalesNotes: 0")
    # sanity: tier counts
    from collections import Counter
    c = Counter(t[0] for t in M)
    print(f"  tiers: gold={c['gold']} silver={c['silver']} bronze={c['bronze']}")

if __name__ == "__main__":
    main()
