# Attractions, restaurants and recommendations

A place in NextStop is either an attraction or a restaurant. Every place
carries a name, a category, an address, coordinates, a rating out of five, its
opening hours, and a price range. Ratings come from the seeded place data and
are not traveller-submitted in Release 1.

## Price ranges

Price range is recorded as one to four dollar signs. `$` is under AUD 20 per
person, `$$` is AUD 20 to 50, `$$$` is AUD 50 to 100, and `$$$$` is above
AUD 100. The price range on an attraction refers to its entry cost, not to
food sold on site.

## How recommendations are formed

A recommendation pairs a traveller with a place and records why it was
suggested. Recommendations are generated from candidate places that already
exist in the database - the model selects among real places and never invents
a venue. A recommendation that names a place absent from the places table is
a defect, not a variation.

Candidate selection considers the traveller's destination first, then the
category they asked about, then rating in descending order. Where two places
have the same rating, the one with the wider opening hours is preferred,
because it is more likely to fit an itinerary day that is already busy.

## Favourites

A traveller can mark any place as a favourite. Favourites are per traveller and
do not affect another traveller's recommendations. Removing a favourite does
not remove the place, and deleting a place removes every favourite pointing at
it.

## Opening hours and planning

Opening hours are stored as free text because they vary by day and season.
They are shown to the traveller but are not machine-checked against itinerary
day times in Release 1, so an itinerary can legitimately contain a place that
is closed at the planned hour.
