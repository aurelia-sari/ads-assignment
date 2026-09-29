# Attractions, restaurants and recommendations

NextStop stores attractions, restaurants, and activities in Australia and Japan. Each place has a name, category, address, coordinates, rating, opening hours, price, description, and optional image URL.

Ratings and prices are seeded demonstration data. They are not live traveller reviews or live prices.

## Supported destinations

Student 2 currently supports:

- Australia: Sydney, Melbourne, and Brisbane
- Japan: Tokyo, Osaka, and Sapporo

Sydney retains its existing attractions and restaurants. Melbourne, Brisbane, Tokyo, Osaka, and Sapporo each contain one attraction, one restaurant, and one activity.

## Categories

A place has one of these categories:

- `attraction`: a landmark, gallery, beach, park, or sightseeing destination
- `restaurant`: a place primarily used for food or dining
- `activity`: an experience or entertainment activity

## Price values

The `price_range` field stores a numeric demonstration price.

- `0`: free
- `10`: low cost
- `30`: affordable
- `50`: moderate
- `70`: higher priced
- `100`: expensive
- `200`: premium

For recommendations, a place costing A$30 or less is treated as affordable. A value of `0` means that general entry is free. Prices are approximate demonstration values and should not be treated as live prices.

## Affordable restaurants

The lowest-priced seeded restaurants are:

- Harry's Cafe de Wheels in Sydney: A$10, rating 4.3
- Bourke Street Bakery in Sydney: A$10, rating 4.5
- Gelato Messina Darlinghurst in Sydney: A$10, rating 4.6
- ICHIRAN Shibuya in Tokyo: A$30, rating 4.4
- Dotonbori Imai Honten in Osaka: A$30, rating 4.3
- Eat Street Northshore in Brisbane: A$30, rating 4.6

Other seeded restaurants include:

- Chat Thai Haymarket in Sydney: A$30, rating 4.0
- Mamak in Sydney: A$30, rating 4.3
- The Grounds of Alexandria in Sydney: A$30, rating 4.0
- Mr Wong in Sydney: A$70, rating 4.4
- Sapporo Beer Garden in Sapporo: A$50, rating 4.3
- Chin Chin Melbourne in Melbourne: A$50, rating 4.4

When a traveller asks for a cheap or affordable restaurant without specifying a city, the recommendation should prefer restaurants with the lowest stored price. When a city is specified, only restaurants in that city should be considered.

## Sydney places

Sydney attractions are:

- Sydney Opera House: free, rating 4.8
- Sydney Harbour Bridge: free, rating 4.8
- Taronga Zoo: A$50, rating 4.5
- Royal Botanic Garden Sydney: free, rating 4.7
- Bondi Beach: free, rating 4.6
- The Rocks: free, rating 4.6
- Manly Beach: free, rating 4.7
- Art Gallery of New South Wales: free, rating 4.7

Sydney restaurants are:

- Harry's Cafe de Wheels: A$10, rating 4.3
- Chat Thai Haymarket: A$30, rating 4.0
- Mamak: A$30, rating 4.3
- The Grounds of Alexandria: A$30, rating 4.0
- Mr Wong: A$70, rating 4.4
- Bourke Street Bakery: A$10, rating 4.5
- Gelato Messina Darlinghurst: A$10, rating 4.6

## Tokyo places

- Tokyo Skytree is an attraction costing A$30 with a rating of 4.6.
- ICHIRAN Shibuya is a restaurant costing A$30 with a rating of 4.4.
- teamLab Planets Tokyo is an activity costing A$50 with a rating of 4.7.

## Osaka places

- Osaka Castle is an attraction costing A$10 with a rating of 4.5.
- Dotonbori Imai Honten is a restaurant costing A$30 with a rating of 4.3.
- Universal Studios Japan is an activity costing A$100 with a rating of 4.5.

## Sapporo places

- Sapporo TV Tower is an attraction costing A$10 with a rating of 4.3.
- Sapporo Beer Garden is a restaurant costing A$50 with a rating of 4.3.
- Shiroi Koibito Park is an activity costing A$10 with a rating of 4.4.

## Melbourne places

- NGV International is a free attraction with a rating of 4.7.
- Chin Chin Melbourne is a restaurant costing A$50 with a rating of 4.4.
- Melbourne Skydeck is an activity costing A$30 with a rating of 4.5.

## Brisbane places

- Gallery of Modern Art is a free attraction with a rating of 4.6.
- Eat Street Northshore is a restaurant costing A$30 with a rating of 4.6.
- Story Bridge Adventure Climb is an activity costing A$100 with a rating of 4.8.

## How recommendations are formed

Recommendations can only select places that already exist in the Student 2 places database. A recommendation that invents a venue or names a place absent from the database is invalid.

Candidate selection follows these rules:

1. If the traveller names a supported city, only places in that city are considered.
2. If the traveller requests an attraction, restaurant, or activity, only that category is considered.
3. A request for a cheap place selects candidates with the lowest stored price.
4. A request for an expensive place selects candidates with the highest stored price.
5. A request for the highest-rated or best-rated place selects candidates with the highest stored rating.
6. A request for one place returns at most one recommendation.
7. Other requests return at most three candidate places.

The final recommendation must be grounded in the filtered candidate records.

## Favourites

A traveller can mark any place as a favourite. Favourites belong to an individual traveller and do not affect another traveller's favourites.

Removing a favourite does not remove the original place. Deleting a place removes favourites that point to that place.

## Opening hours and planning

Opening hours are stored as free text because they can vary by day and season. Opening hours are displayed but are not automatically compared with itinerary times.

Opening hours and prices are demonstration data. Travellers should check the venue's official information before visiting.