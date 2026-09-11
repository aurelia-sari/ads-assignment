# Accounts, profiles, onboarding and travel guides

An account is created with an email address and a password, and starts
unverified. A verification email is sent on sign-up, and the account becomes
verified once the link in it is opened. An unverified account can sign in and
browse, but cannot post a trip post or send a connect request.

Passwords must be at least eight characters and contain a letter and a digit.
Passwords are stored hashed, never in plain text, and are never returned by any
API response.

## Onboarding

Onboarding asks a new traveller for a display name, a home city, and their
travel interests. All three are optional and can be completed later from the
profile page. Skipping onboarding does not restrict any feature; it only means
recommendations have less to work from.

## Travel guides

A travel guide is held per destination and covers six areas: currency,
transportation, visa requirements, weather, safety, and general information.
Guide content is seeded reference material, not live data. Currency figures and
visa rules in particular are indicative and are not updated in real time, so a
traveller should confirm them with an official source before relying on them.

Weather in a guide describes typical seasonal conditions for the destination.
It is not a forecast and does not refer to any particular date.

## The dashboard

The dashboard is the signed-in traveller's landing page. It summarises their
trips, their saved places, and any pending connect requests, by reading each
owning feature's service rather than holding its own copy of that data.
