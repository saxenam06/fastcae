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
 * The tabs, in the order the work happens: what the drawing states, the part as its CAD describes
 * it - where single variants are designed by hand - campaigns of thousands and the designs they
 * keep, surrogates trained on them, and the search.
 *
 * Every tab is shown whether or not it is built yet. A shell that hides its unbuilt stages
 * describes a tool; one that shows them describes a product, and tells anyone looking where what
 * they are doing now leads.
 */
export type View = "drawing" | "cad" | "generate" | "learn" | "optimize";

export const VIEWS: { id: View; label: string; summary: string; ready: boolean }[] = [
  {
    id: "drawing",
    label: "Drawing",
    summary: "What the drawing states, callout by callout, beside the text it was read from.",
    ready: true,
  },
  {
    id: "cad",
    label: "CAD",
    summary:
      "The part as its CAD describes it - faces, axes and the features on them - and single " +
      "variants designed on it by hand.",
    ready: true,
  },
  {
    id: "generate",
    label: "Generate",
    summary:
      "Campaigns: thousands of variants spread over the design space, each screened - and every " +
      "design followed through its stages to the data it yields.",
    ready: true,
  },
  {
    id: "learn",
    label: "Learn",
    summary: "Surrogates trained on a campaign's results, and how far they can be believed.",
    ready: false,
  },
  {
    id: "optimize",
    label: "Optimize",
    summary: "The surrogate searched, candidates proposed, the ones worth solving verified.",
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
