# Ichiro3000

A little Python script that helps you track a hitter's progress toward an MLB milestone. This is totally just roughed in, but it's working.

## Setup
Make your virtualenv and install the requirements. Note: This uses redis for storage, so you'll need to start up redis as a background service.

Edit CONFIG in `fetch.py` to:
* identify a player by MLB ID and team abbreviation
* set `start_count` and an optional `target_count` for the milestone
* identify which hitting events should increment the player's `current_count`

## Run the script
With your virtual environment active:

    python fetch.py

To inspect or clean out data in your redis instance:

    python fetch.py --check
    python fetch.py --clean

## TODO
* Refactor away some ugliness
* Hook `handle_match()` up to a Twitter bot
* Deploy to Heroku and stick it on a cron
