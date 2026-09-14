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
 * The tabs, in the order the work happens: what the engineer brought - the drawing, the CAD, the
 * solver deck and the answer it gave - then what fastcae will vary and how every variant will be
 * meshed and solved, the campaigns and the designs they keep, surrogates trained on them, and the
 * search.
 *
 * Every tab is shown whether or not it is built yet. A shell that hides its unbuilt stages
 * describes a tool; one that shows them describes a product, and tells anyone looking where what
 * they are doing now leads.
 */
export type View = "input" | "reproduce" | "variants" | "campaign" | "explore" | "models";

/** Input's four: the engineer's own files, as read. */
export type InputTab = "drawing" | "cad" | "mesh" | "solve";
/** Variant Setup's two: what will vary, and the route every design takes. */
export type VariantTab = "variants" | "route";

export const INPUT_TABS: { id: InputTab; label: string; summary: string }[] = [
  { id: "drawing", label: "Drawing", summary: "What the drawing states, callout by callout" },
  { id: "cad", label: "CAD", summary: "The part as its CAD describes it: faces, axes, features" },
  { id: "mesh", label: "Mesh & setup", summary: "The solver deck's mesh, supports, couplings and loads, as the deck names them" },
  { id: "solve", label: "Solve", summary: "The answer the engineer's solver gave, as it wrote it" },
];

export const VARIANT_TABS: { id: VariantTab; label: string; summary: string }[] = [
  { id: "variants", label: "Variants", summary: "One change in one place, designed on the CAD" },
  { id: "route", label: "Route", summary: "How every variant is built, meshed, set up and solved - walked on the baseline" },
];

/**
 * The lifecycle: the engineer's truth, reproduced before anything is built on it; what may change
 * and how each change is solved; the campaigns that make the data; the designs they keep; the models
 * trained on them.
 */
export const VIEWS: { id: View; label: string; summary: string; ready: boolean }[] = [
  {
    id: "input",
    label: "Input",
    summary:
      "What the engineer brought: the drawing, the CAD, the solver deck with its mesh, supports and " +
      "loads, and the answer it gave - read, never assumed.",
    ready: true,
  },
  {
    id: "reproduce",
    label: "Reproduce",
    summary:
      "The engineer's answer set beside fastcae's to the same question - side by side, as a " +
      "difference, and quantity by quantity - before a single design is trusted to fastcae.",
    ready: true,
  },
  {
    id: "variants",
    label: "Variant Setup",
    summary:
      "What may change - variants designed on the CAD - and the route every variant takes: field, " +
      "mesh, the deck's own setup, solve.",
    ready: true,
  },
  {
    id: "campaign",
    label: "Campaign",
    summary: "Campaigns composed from variants and launched: how many designs, from which seed, and how each run is going.",
    ready: true,
  },
  {
    id: "explore",
    label: "Explore",
    summary: "Every design a campaign kept, followed through its stages to the data it yields.",
    ready: true,
  },
  {
    id: "models",
    label: "Models",
    summary: "Surrogates trained on the accepted designs, how far they can be believed, and the search on them.",
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
