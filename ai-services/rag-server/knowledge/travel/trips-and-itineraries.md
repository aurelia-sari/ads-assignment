# Trip planning and day-by-day itineraries

A trip in NextStop records a destination, a start and end date, a budget in
Australian dollars, and a status. A trip moves through three statuses:
`planned` while it is being designed, `booked` once travel and accommodation
are confirmed, and `completed` after the return date has passed. A trip cannot
be marked `booked` until it has at least one itinerary day.

## Itinerary days

An itinerary day belongs to exactly one trip and carries a day number, a
calendar date, a location, and a planned activity. Day numbers start at 1 and
should run consecutively to the length of the trip. A three-night trip has four
itinerary days, counting arrival and departure days, because both involve
activity even if that activity is only transit.

Leaving a day with no activity is valid and is how travellers record rest days.
A rest day is recommended after any flight of more than eight hours, and after
every third consecutive day of full-day activities.

## Budget guidance

The budget recorded against a trip is a total ceiling in AUD, not a per-day
figure, and it is intended to cover flights, accommodation, food and
activities together. As a planning rule of thumb for a mid-range traveller,
allocate roughly 40 per cent of a trip budget to flights, 30 per cent to
accommodation, 20 per cent to food and activities, and keep 10 per cent as
contingency. Short domestic trips skew the other way: flights fall to about 25
per cent and accommodation rises.

A trip whose itinerary days total more activity cost than the recorded budget
should be flagged to the traveller rather than silently rejected, because
travellers routinely set a budget first and adjust it once the plan is real.

## Changing a trip after booking

Changing the destination of a `booked` trip is not supported. The intended
path is to mark the existing trip `completed` or delete it, and create a new
trip. Changing dates on a `booked` trip is allowed, but every itinerary day
keeps its own date, so the days must be edited individually afterwards.
