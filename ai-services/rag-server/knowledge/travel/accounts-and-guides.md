# Accounts, sign-in and travel guides

A NextStop account is created with a name, an email address and a password,
and the traveller must agree to the Terms and Conditions. A new account starts
unverified. A verification email is sent on sign-up, and the account becomes
verified once the link in it is opened. The link can only be used once and
expires after five minutes.

## Account password requirements

A password must be between 8 and 64 characters long. It must contain at least
one uppercase letter, one lowercase letter, one number and one special
character. Passwords are stored hashed, never in plain text, and are never
returned by any API response.

## Signing in and out

An unverified account cannot sign in. Signing in to an unverified account with
the correct password is refused, and a fresh verification email is sent
instead. A wrong password and an email with no account both get the same
"Invalid email or password" message, so sign-in cannot reveal which emails are
registered. Signing out ends the traveller's session.

## Verification and password reset emails

A traveller can ask for the verification email to be sent again. Resends must
be at least 60 seconds apart, and after five resends there is a ten minute
wait. A forgotten password is reset through an emailed link. The reset request
gives the same reply whether or not the email is registered. The reset link can
only be used once, expires after five minutes, and the new password must meet
the same requirements as before.

## Travel guides

A travel guide is held per destination. Each guide is written to cover five
areas, which are currency, transportation, visa requirements, weather and
safety. Destinations
can be searched by city or country. Guide content is seeded reference material,
not live data. Currency figures and visa rules in particular are indicative and
are not updated in real time, so a traveller should confirm them with an
official source before relying on them.

## Currency and transportation

The currency section gives the local currency code and name, with tips on
paying and exchanging money. Transportation lists only the modes a destination
actually has, such as flights, metro, train, taxi and car rental. Flights are
the only mode that can be booked in NextStop, through the Bookings & Budget feature. The
other modes are descriptive only.

## Visa, weather and safety

Visa requirements depend on the traveller's nationality, so no nationality is
selected by default and the traveller picks their own. Weather in a guide
describes typical conditions for each month, with the average temperature,
rainfall and the best time to visit. It is not a forecast and does not refer to
any particular date. The safety section gives the destination's safety level
and local safety tips.

## The AI assistant

The AI assistant answers questions about a named city using only that city's
seeded data. If the data does not answer the question, it says so rather than
guessing. Questions about booking travel are pointed to the
Bookings & Budget feature, and questions about food or attractions are pointed
to Attractions & Dining. Each conversation about a destination is saved as a
past chat that can be reopened or deleted.
