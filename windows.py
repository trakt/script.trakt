# -*- coding: utf-8 -*-
#

import xbmcaddon
import xbmcgui
from utilities import Debug
import utilities
import rating

import functools

__author__ = "Ralph-Gordon Paul, Adrian Cowan"
__credits__ = ["Ralph-Gordon Paul", "Adrian Cowan", "Justin Nemeth",  "Sean Rudford"]
__license__ = "GPL"
__maintainer__ = "Andrew Etches"
__email__ = "andrew.etches@dur.ac.uk"
__status__ = "Production"

# read settings
__settings__ = xbmcaddon.Addon( "script.trakt" )
__language__ = __settings__.getLocalizedString

RATE_TITLE = 100
RATE_CUR_NO_RATING = 101
RATE_CUR_LOVE = 102
RATE_CUR_HATE = 103
RATE_SKIP_RATING = 104
RATE_LOVE_BTN = 105
RATE_HATE_BTN = 106
RATE_RATE_SHOW_BG = 107
RATE_RATE_SHOW_BTN = 108
RATE_ADVANCED_1_BTN = 201
RATE_CUR_ADVANCED_1 = 211
RATE_ADVANCED_2_BTN = 202
RATE_CUR_ADVANCED_2 = 212
RATE_ADVANCED_3_BTN = 203
RATE_CUR_ADVANCED_3 = 213
RATE_ADVANCED_4_BTN = 204
RATE_CUR_ADVANCED_4 = 214
RATE_ADVANCED_5_BTN = 205
RATE_CUR_ADVANCED_5 = 215
RATE_ADVANCED_6_BTN = 206
RATE_CUR_ADVANCED_6 = 216
RATE_ADVANCED_7_BTN = 207
RATE_CUR_ADVANCED_7 = 217
RATE_ADVANCED_8_BTN = 208
RATE_CUR_ADVANCED_8 = 218
RATE_ADVANCED_9_BTN = 209
RATE_CUR_ADVANCED_9 = 219
RATE_ADVANCED_10_BTN = 210
RATE_CUR_ADVANCED_10 = 220


#get actioncodes from keymap.xml
ACTION_PARENT_DIRECTORY = 9
ACTION_PREVIOUS_MENU = 10
ACTION_SELECT_ITEM = 7
ACTION_CONTEXT_MENU = 117


class RateDialog(xbmcgui.WindowXMLDialog):
    """Base class implementing the methods that don't change in the rating dialogues"""
    def __init__(self, xml, fallback_path=__settings__.getAddonInfo('path'), defaultskinname="Default", forcefallback=False):
        xbmcgui.WindowXMLDialog.__init__(xml, fallback_path, defaultskinname, forcefallback)

        self._id_to_rating_string = {
            RATE_SKIP_RATING: "skip", RATE_LOVE_BTN: "love", RATE_HATE_BTN: "hate", RATE_ADVANCED_1_BTN: "1",
            RATE_ADVANCED_2_BTN: "2", RATE_ADVANCED_3_BTN: "3", RATE_ADVANCED_4_BTN: "4",
            RATE_ADVANCED_5_BTN: "5", RATE_ADVANCED_6_BTN: "6", RATE_ADVANCED_7_BTN: "7",
            RATE_ADVANCED_8_BTN: "8", RATE_ADVANCED_9_BTN: "9", RATE_ADVANCED_10_BTN: "10"
        }

        self.curRating = None
        self.controlID = None

    def initDialog(self, cur_rating, rating_type):
        """Set up the generic current rating code"""
        self.curRating = cur_rating
        self.ratingType = rating_type
        if self.curRating not in self._id_to_rating_string.values():
            self.curRating = None

    def onFocus(self, control_id):
        """Update currently selected item id"""
        self.controlID = control_id

    def onInit(self, header):
        """Set up the generic window code"""
        self.getControl(RATE_TITLE).setLabel(header)
        self.getControl(RATE_RATE_SHOW_BG).setVisible(False)
        self.getControl(RATE_RATE_SHOW_BTN).setVisible(False)
        self.getControl(RATE_CUR_NO_RATING).setEnabled(False)
        self.setFocus(self.getControl(RATE_SKIP_RATING))
        self._update_rated_button()

    def onClick(self, control_id, method):
        """Perform action when item clicked"""
        self.curRating = self._id_to_rating_string[control_id]
        self._update_rated_button()

        if control_id in (RATE_CUR_LOVE, RATE_CUR_HATE, RATE_CUR_ADVANCED_1, RATE_CUR_ADVANCED_2, RATE_CUR_ADVANCED_3, RATE_CUR_ADVANCED_4, RATE_CUR_ADVANCED_5, RATE_CUR_ADVANCED_6, RATE_CUR_ADVANCED_7, RATE_CUR_ADVANCED_8, RATE_CUR_ADVANCED_9, RATE_CUR_ADVANCED_10):
            self.curRating = "unrate"

        if self.curRating != "skip":
            method(self.curRating)

        Debug("[Rating] Closing and rated! "+str(self.curRating))
        self.close()

    def _update_rated_button(self):
        """Set the current rating button"""
        self.getControl(RATE_CUR_NO_RATING).setVisible(False if self.curRating != None else True)
        self.getControl(RATE_CUR_LOVE).setVisible(False if self.curRating != "love" else True)
        self.getControl(RATE_CUR_HATE).setVisible(False if self.curRating != "hate" else True)
        if self.ratingType == "advanced":
            self.getControl(RATE_CUR_ADVANCED_1).setVisible(False if self.curRating != "1" else True)
            self.getControl(RATE_CUR_ADVANCED_2).setVisible(False if self.curRating != "2" else True)
            self.getControl(RATE_CUR_ADVANCED_3).setVisible(False if self.curRating != "3" else True)
            self.getControl(RATE_CUR_ADVANCED_4).setVisible(False if self.curRating != "4" else True)
            self.getControl(RATE_CUR_ADVANCED_5).setVisible(False if self.curRating != "5" else True)
            self.getControl(RATE_CUR_ADVANCED_6).setVisible(False if self.curRating != "6" else True)
            self.getControl(RATE_CUR_ADVANCED_7).setVisible(False if self.curRating != "7" else True)
            self.getControl(RATE_CUR_ADVANCED_8).setVisible(False if self.curRating != "8" else True)
            self.getControl(RATE_CUR_ADVANCED_9).setVisible(False if self.curRating != "9" else True)
            self.getControl(RATE_CUR_ADVANCED_10).setVisible(False if self.curRating != "10" else True)

    def onAction(self, action):
        if action.getId() in (ACTION_PARENT_DIRECTORY, ACTION_PREVIOUS_MENU):
            Debug("[Rating] Closing Dialog")
            self.close()

class RateEpisodeDialog(RateDialog):
    def __init__(self, xml, fallback_path=__settings__.getAddonInfo('path'), defaultskinname="Default", forcefallback=False):
        super(RateEpisodeDialog, self).__init__(xml, fallback_path, defaultskinname, forcefallback)
        self.tvdbid = None
        self.title = None
        self.year = None
        self.season = None
        self.episode = None

    def initDialog(self, tvdbid, title, year, season, episode, curRating, rating_type):
        self.tvdbid = tvdbid
        self.title = title
        self.year = year
        self.season = season
        self.episode = episode
        super(RateEpisodeDialog, self).initDialog(curRating, rating_type)

    def onInit(self):
        super(RateEpisodeDialog, self).onInit(__language__(1304).encode("utf-8", "ignore"))
        self.getControl(RATE_RATE_SHOW_BTN).setLabel(__language__(1305).encode( "utf-8", "ignore" ))
        self.getControl(RATE_RATE_SHOW_BTN).setVisible(True)
        self.getControl(RATE_RATE_SHOW_BG).setVisible(True)

    def onClick(self, controlId):
        if controlId == RATE_RATE_SHOW_BTN:
            self.getControl(RATE_RATE_SHOW_BG).setVisible(False)
            self.getControl(RATE_RATE_SHOW_BTN).setVisible(False)
            self.setFocus(self.getControl(RATE_SKIP_RATING))

            if self.ratingType == "advanced":
                rateShow = RateShowDialog("rate_advanced.xml", __settings__.getAddonInfo('path'))
            else:
                rateShow = RateShowDialog("rate.xml", __settings__.getAddonInfo('path'))

            rateShow.initDialog(self.tvdbid, self.title, self.year, utilities.getShowRatingFromTrakt(self.tvdbid, self.title, self.year), rating_type)
            rateShow.doModal()
            del rateShow
        else:
            method = functools.partial(utilities.rateEpisodeOnTrakt, self.tvdbid, self.title, self.year, self.season, self.episode)
            super(RateEpisodeDialog, self).onClick(controlId, method)

class RateShowDialog(RateDialog):
    def __init__(self, xml, fallback_path=__settings__.getAddonInfo('path'), defaultskinname="Default", forcefallback=False):
        super(RateShowDialog, self).__init__(xml, fallback_path, defaultskinname, forcefallback)
        self.tvdbid = None
        self.title = None
        self.year = None

    def initDialog(self, tvdbid, title, year, curRating, rating_type):
        self.tvdbid = tvdbid
        self.title = title
        self.year = year
        super(RateShowDialog, self).initDialog(curRating, rating_type)

    def onInit(self):
        super(RateShowDialog, self).onInit(__language__(1306).encode("utf-8", "ignore"))

    def onClick(self, controlId):
        method = functools.partial(utilities.rateShowOnTrakt, self.tvdbid, self.title, self.year)
        super(RateShowDialog, self).onClick(controlId, method)

