# Flights, hotels, car rentals and budget

Flight, hotel and car rental records in NextStop are seeded sample inventory
used to demonstrate search and selection. They are not live availability and
cannot be booked with a real provider.

## Searching

A flight search accepts an origin, a destination, a date range, and a maximum
fare in AUD. All four are optional; an empty search returns the full seeded
inventory. Fares are per person, one way, and include taxes. A hotel search
accepts a destination, a date range, and a maximum nightly rate. Hotel rates
are per room per night, not per person.

Search results are ordered by identifier rather than by price, so a traveller
comparing on price should sort in the interface rather than assume the first
result is cheapest.

## Selections

A selection records that a traveller has chosen a particular flight, hotel or
car rental for a trip. A trip can hold at most one selected flight, one
selected hotel, and one selected car rental at a time. Selecting a replacement
removes the previous selection of that kind.

## Budget

A budget belongs to one trip and records a total in AUD alongside the amount
committed by current selections. The remaining budget is the total minus the
committed amount, and it is allowed to go negative - the traveller is warned
rather than blocked, because a plan is often over budget before it is trimmed.

Budget totals are computed in the backend and passed to the AI as a finished
figure. The model is never asked to add up fares itself, because small local
models make arithmetic errors on aggregation and state the wrong total
confidently.

## Currency

Every stored amount is in Australian dollars. There is no currency conversion
in Release 1, so a fare quoted by a real airline in another currency will not
match a seeded fare.
