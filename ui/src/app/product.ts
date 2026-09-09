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
 * The stages of the product, shown in full whether or not each one is built yet.
 *
 * Deliberately visible before they work. A shell that hides its unbuilt stages describes a tool;
 * one that shows them describes a product, and it tells anyone looking where the thing they are
 * doing now leads. `available` is what gates interaction, not what gates display.
 */
export interface Stage {
  id: string;
  label: string;
  summary: string;
  available: boolean;
}

export const STAGES: Stage[] = [
  {
    id: "extract",
    label: "Extract",
    summary: "Artifacts in. What each one yielded, and what could not be read.",
    available: true,
  },
  {
    id: "model",
    label: "Model",
    summary: "What the part geometrically is, and which of it a drawing controls.",
    available: true,
  },
  {
    id: "generate",
    label: "Generate",
    summary: "Author design parameters on the geometry and produce variants.",
    available: false,
  },
  {
    id: "simulate",
    label: "Simulate",
    summary: "Run campaigns across the design space and collect responses.",
    available: false,
  },
  {
    id: "learn",
    label: "Learn",
    summary: "Train surrogates on the campaign, and measure whether they can be believed.",
    available: false,
  },
  {
    id: "optimize",
    label: "Optimize",
    summary: "Search the surrogate, propose candidates, verify the ones worth solving.",
    available: false,
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
