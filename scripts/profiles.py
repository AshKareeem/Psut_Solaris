"""Lander presets for the web app's "Your lander" choice: each is a set of mission requirements, never weights.

Every preset is one full Step 4 run (scripts/score_sites.py with these flags; scripts/run_profiles.py), so the page
only loads a different results.json and computes nothing. The lander itself (battery, panel, load) is the Nova-C
class profile in scripts/battery.py, with its sources; the variants change one requirement each and say which.
"""

DEFAULT = "nova-c-14d"

PROFILES = {
    "nova-c-14d": {
        "label": "Nova-C-class lander, 14-day mission",
        "description": "The default: a lander like Intuitive Machines' Nova-C (700 Wh battery, 200 W of panels), "
                       "working for 14 days, with Earth counted as soon as any part of it shows above the horizon.",
        "args": [],
    },
    "nova-c-28d": {
        "label": "Long mission: 28 days",
        "description": "The same lander, asked to work for 28 days: about one full lunar day and night, so the "
                       "site has to get it through a long darkness and keep Earth in view for half of a longer mission.",
        "args": ["--days", "28"],
    },
    "weak-antenna": {
        "label": "Weak antenna: Earth 2° above the horizon",
        "description": "The same lander and 14 days, but its antenna only links when Earth clears the horizon by "
                       "2° (a terrain or antenna mask), instead of as soon as any part of Earth shows.",
        "args": ["--earth-margin", "2"],
    },
}
