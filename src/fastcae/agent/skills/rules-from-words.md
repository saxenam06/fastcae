# Rules from words
when: the words say what must hold - how tall, how many, how far apart, what not to do

Each rule is a kind the platform knows, the entities it names in `refs`, and what it needs in
`params`. Hard only when the engineer said it; cites may be left out.

- no taller than something: `not_above` it. At most so tall: `height_at_most`.
- clear of, not crossing, not touching, not interfering with something: `keep_clear_of` - see the
  skill on keeping clear.
- how many, as a range: `count_between`; at least so many at something: `at_least_at`.
- how far apart: `spacing_at_least`. No crossings: `no_x_junctions`. Ribs meeting at least so far
  apart in angle: `junction_angle_at_least`. At most so many meeting at a point: `at_most_meeting`.
- symmetric about something: `symmetric_about`. Something tied together by ribs: `tie`.
- the smallest radius the part allows: `smallest_radius`. Draft: `draft_at_least`.
- running along a face, or square to it: `along`, `square_to`.

A value the words give for a setting - a count, a thickness, an angle - is a setting of the block,
not a rule. A rule no kind fits is still written, as a new kind with the engineer's words as its
text: it is kept, and listed as not enforced - say so in an attention line.
