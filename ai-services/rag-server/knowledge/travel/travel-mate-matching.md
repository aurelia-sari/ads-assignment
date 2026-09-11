# Travel mate matching

A trip post advertises a trip that a traveller is willing to share, so other
travellers can ask to join. A post carries a destination, start and end dates,
a short description, and a status. Posts move through `open`, `matched` and
`closed`.

## Connect requests

Another traveller asks to join by sending a connect request against a post. A
connect request has a status of `pending`, `accepted` or `declined`. Only the
traveller who owns the post can accept or decline a request. Accepting a
request moves the post to `matched`; it does not close the post, because a
group trip can accept several travellers.

A traveller cannot send a connect request against their own post, and cannot
send more than one pending request to the same post. A declined request can be
re-sent only after the post owner has edited the post.

## Matching signals

Posts are matched to travellers on overlapping destination first and
overlapping dates second. Two trips overlap in dates when the later start date
falls on or before the earlier end date. A partial date overlap of at least
three days is treated as a viable match, because travellers frequently join
for part of a longer trip.

Matching does not consider budget, age or gender in Release 1. Those are
deliberately excluded: the data is not collected, and inferring them would be
both unreliable and inappropriate.

## Safety

Travellers are shown a verified badge when the account behind a post has
completed email verification. An unverified account can still post, but the
badge is absent. Contact details are never included in a post body; the
intended path is a connect request, so an interaction is always recorded.
