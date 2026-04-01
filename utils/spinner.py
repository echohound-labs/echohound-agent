"""
utils/spinner.py — 187 spinner verbs + stalled animation
"""
import random
import time

SPINNER_VERBS = [
    "Accomplishing", "Actioning", "Actualizing", "Architecting",
    "Baking", "Beaming", "Beboppin'", "Befuddling", "Billowing",
    "Blanching", "Bloviating", "Boogieing", "Boondoggling", "Booping",
    "Bootstrapping", "Brewing", "Bunning", "Burrowing",
    "Calculating", "Canoodling", "Caramelizing", "Cascading",
    "Catapulting", "Cerebrating", "Channeling", "Choreographing",
    "Churning", "Coalescing", "Cogitating", "Combobulating",
    "Composing", "Computing", "Concocting", "Conjuring", "Considering",
    "Crafting", "Crunching",
    "Daydreaming", "Deliberating", "Discombobulating", "Discovering",
    "Distilling", "Doing", "Dreaming",
    "Elaborating", "Elucidating", "Embarking", "Endeavoring",
    "Engaging", "Engineering", "Enlightening", "Envisioning",
    "Evaluating", "Excavating", "Executing", "Expanding", "Exploring",
    "Fabricating", "Fathoming", "Figuring", "Finagling", "Flibbertigibbeting",
    "Flourishing", "Focusing", "Formulating",
    "Generating", "Germinating", "Groking", "Grooving",
    "Hallucinating", "Harmonizing", "Hatching", "Heuristing",
    "Illuminating", "Imagining", "Implementing", "Incubating",
    "Inferring", "Innovating", "Integrating", "Introspecting",
    "Inventing", "Investigating",
    "Jitterbugging", "Juggling",
    "Kibbitzing", "Kneading",
    "Launching", "Levitating", "Llama-izing", "Lucubrating",
    "Machinating", "Manifesting", "Marinating", "Maximizing",
    "Meandering", "Meditating", "Moseying", "Mulling",
    "Noodling",
    "Obfuscating", "Optimizing", "Orchestrating",
    "Perambulating", "Percolating", "Philosophizing", "Pondering",
    "Postulating", "Processing", "Prognosticating", "Puttering",
    "Quantum-leaping", "Questioning",
    "Reticulating", "Riffing", "Rummaging",
    "Scheming", "Scintillating", "Shimming", "Simmering", "Sleuthing",
    "Spitballing", "Strategizing", "Summoning", "Surfacing", "Synthesizing",
    "Tinkering", "Transcending", "Transmuting",
    "Ultraprocessing", "Unraveling",
    "Vibrating", "Visualizing",
    "Wandering", "Whirring", "Wondering", "Working",
    "Zapping", "Zen-ing",
    # EchoHound extras
    "Sniffing", "Tracking", "Hunting", "Howling", "Fetching",
    "Digging", "Stalking", "Scouting", "Baying", "Nosing",
]

STALLED_MESSAGES = [
    "Still thinking... this one's a thinker 🤔",
    "Hang tight — deep in the weeds on this",
    "Still here. Just really into this problem",
    "Processing... at a slightly glacial pace 🧊",
    "Your patience is appreciated. And noticed.",
    "This is taking longer than expected — still on it",
    "Burrowing deep. Won't be long now 🐾",
    "Haven't frozen. Promise.",
    "Cerebrating at maximum capacity...",
    "The answer exists. I'm finding it.",
]

STALL_THRESHOLD_SECONDS = 8


def get_thinking_message() -> str:
    return f"{random.choice(SPINNER_VERBS)}..."


def get_stalled_message() -> str:
    return random.choice(STALLED_MESSAGES)


class ThinkingTimer:
    def __init__(self):
        self._start = time.time()

    def elapsed(self) -> float:
        return time.time() - self._start

    def is_stalled(self) -> bool:
        return self.elapsed() > STALL_THRESHOLD_SECONDS

    def reset(self):
        self._start = time.time()
