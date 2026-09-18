/**
 * The product, its stages, and whatever is loaded in it today.
 *
 * Three different things, and the shell keeps them apart. Collapsing them puts a part's name where
 * the product's belongs, and makes one component look like the whole tool.
 *
 * Nothing here names a component type. The project's name is its folder's name and arrives from the
 * server, so renaming the folder renames the application.
 */

export const VENDOR = {
  name: "ZenryxAI",
  /**
   * The company line.
   *
   * Generate leads because it is the thing a solver cannot do: the campaign, the training set and
   * the search all exist to serve designs that had to be generated first. Simulate is left out on
   * purpose - it is how the learning happens rather than what is sold, and everyone already owns a
   * solver. Optimize is last because it is the payoff.
   */
  tagline: "Generate. Learn. Optimize.",
} as const;

export const PRODUCT = {
  name: "fastcae",
} as const;

/**
 * The tabs, in the order the work happens: what the engineer brought, read into typed entities by
 * the pipeline and the design space derived from them; designs generated in that space; surrogates
 * learnt from them; and the search.
 *
 * Every tab is shown whether or not it is built yet. A shell that hides its unbuilt stages
 * describes a tool; one that shows them describes a product, and tells anyone looking where what
 * they are doing now leads.
 */
export type View = "input" | "generate" | "learn" | "optimize";

/** Input's three: the engineer's own files, as the pipeline read them. */
export type InputTab = "drawing" | "cad" | "mesh";
/** The CAD as its faces, or as the design space derived round it. */
export type CadView = "part" | "space";
/** The deck as it sets the part up, or the answer the engineer's solver gave. */
export type DeckView = "setup" | "answer";
/** Generate's two: campaigns launched, and every design they kept. */
export type GenerateTab = "campaign" | "designs";

export const INPUT_TABS: { id: InputTab; label: string; summary: string }[] = [
  { id: "drawing", label: "Drawing", summary: "What the drawing states, callout by callout" },
  {
    id: "cad",
    label: "CAD",
    summary: "The part as its CAD describes it, and the design space derived round it",
  },
  {
    id: "mesh",
    label: "Mesh & setup",
    summary: "The solver deck's mesh, supports, couplings and loads, and the answer it gave",
  },
];

export const CAD_VIEWS: { id: CadView; label: string }[] = [
  { id: "part", label: "Part" },
  { id: "space", label: "Design space" },
];

export const DECK_VIEWS: { id: DeckView; label: string }[] = [
  { id: "setup", label: "Setup" },
  { id: "answer", label: "Answer" },
];

export const GENERATE_TABS: { id: GenerateTab; label: string; summary: string }[] = [
  { id: "campaign", label: "Campaign", summary: "Campaigns launched, and how each run is going" },
  { id: "designs", label: "Designs", summary: "Every design a campaign kept, through its stages" },
];

export const VIEWS: { id: View; label: string; summary: string; ready: boolean }[] = [
  {
    id: "input",
    label: "Input",
    summary:
      "What the engineer brought - the drawing, the CAD, the solver deck and its answer - read " +
      "into typed entities, and the design space derived from them.",
    ready: true,
  },
  {
    id: "generate",
    label: "Generate",
    summary: "Designs made in the design space, meshed and solved as the deck solves the part.",
    ready: true,
  },
  {
    id: "learn",
    label: "Learn",
    summary: "Surrogates trained on the solved designs, and how far they can be believed.",
    ready: false,
  },
  {
    id: "optimize",
    label: "Optimize",
    summary: "The search on the surrogates, confirmed by the solver.",
    ready: false,
  },
];

/**
 * The supplied lockup is **stacked** - crane over wordmark over tagline - and a stacked lockup
 * cannot work in a horizontal bar: at any height that fits, the tagline degrades to a grey smudge.
 * So the crane is used as the mark and the wordmark and tagline are set as live text beside it,
 * which stays crisp at any size and scales with the type.
 *
 * Both files carry a real alpha channel, so they sit directly on the sheet with no blend mode.
 */
export const ART = {
  /** The crane, cropped out of the full lockup. Used in the bar and as the favicon. */
  mark: "/zenryx-mark.png",
  /** The full stacked lockup. Kept for anywhere it can be shown at size. */
  lockup: "/zenryx-logo.png",
} as const;
