trakt.tv TV and movie scrobbler for XBMC Eden
=============================================

Automatically scrobble all TV episodes and movies you are watching to trakt.tv! Keep a comprehensive history of everything you've watched and be part of a global community of TV and movie enthusiasts. Sign up for a free account at http://trakt.tv and get a ton of features including:

* automatically scrobble what you're watching
* mobile apps for iPhone, iPad, Android, Windows Phone, Blackberry, and Symbian
* share what you're watching (in real time) and rating to facebook, twitter, and tumblr
* use watchlists so you don't forget to what to watch
* track your media collections and impress your friends
* create custom lists around any topics you choose
* easily track your TV show progress across all seasons and episodes
* discover new shows and movies based on your viewing habits

###What can be scrobbled?

This plugin will scrobble local media and most remote streaming content. Local content should be played in XBMC library mode and you should use TVDb (for tv shows) and TMDb (for movies) as your scrapers. TV shows are identified using their TVDb ID. Movies are identified using the IMDB ID. This helps trakt match up the correct show or movie regardless of the title and improves accuracy a lot.

Remote streaming content will scrobble assuming the metadata is correctly set in XBMC. The various streaming plugins need to correctly identify TV episodes and movies with as much metadata as they can for trakt to know what you're watching.

###Tested and scrobbling correctly

* XBMC library mode
* Amazon (bluecop repo)
* CBS (bluecop repo)

###Installation

1. Clone this repository (or [download it here](https://github.com/rectifyer/script.trakt/zipball/master)) into a folder called **script.trakt** inside your XBMC **addons** folder
2. Start up XMBC (or restart if its already running)
3. Navigate to *Settings* > *Add-ons* > *Enabled add-ons* > *Services* > **trakt**
4. Select *trakt* and go to **Configure**
5. Enter your **username**, **password**, and change any other settings as needed
6. Select **OK** to save your settings
7. Watch something and see it show up on trakt.tv!