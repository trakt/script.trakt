# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import xbmcgui
import utilities as utils

__addon__ = xbmcaddon.Addon("script.trakt")

ACTION_LIST = 111
DIALOG_IMAGE = 2
ACTION_PREVIOUS_MENU2 = 92
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
ACTION_CLOSE_LIST = [ACTION_PREVIOUS_MENU2, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU]
ACTION_ITEM_SELECT = [ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK]


class traktContextMenu(xbmcgui.WindowXMLDialog):

    action = None

    def __new__(cls, media_type=None, buttons=None):
        return super(traktContextMenu, cls).__new__(cls, "traktContextMenu.xml", __addon__.getAddonInfo('path'), media_type=media_type, buttons=None)

    def __init__(self, *args, **kwargs):
        self.buttons = kwargs['buttons']
        self.media_type = kwargs['media_type']
        super(traktContextMenu, self).__init__()

    def onInit(self):
        lang = utils.getString
        mange_string = lang(2000) if utils.isMovie(self.media_type) else lang(2001)
        rate_string = lang(2030)
        if utils.isShow(self.media_type):
            rate_string = lang(2031)
        elif utils.isEpisode(self.media_type):
            rate_string = lang(2032)

        actions = [mange_string, lang(2010), lang(2020), rate_string, lang(2040), lang(2050), lang(2060), lang(2070)]
        keys = ["itemlists", "removefromlist", "addtolist", "rate", "togglewatched", "managelists", "updatetags", "sync"]

        l = self.getControl(ACTION_LIST)
        for i in range(len(actions)):
            if keys[i] in self.buttons:
                l.addItem(self.newListItem(actions[i], id=keys[i]))

        h = ((len(self.buttons)) * 46) - 6
        l.setHeight(h)

        d = self.getControl(DIALOG_IMAGE)
        d.setHeight(h + 40)

        offset = (316 - h) / 2

        d.setPosition(0, offset - 20)
        l.setPosition(20, offset)

        self.setFocus(l)

    def newListItem(self, label, selected=False, *args, **kwargs):
        item = xbmcgui.ListItem(label)
        item.select(selected)
        for key in kwargs:
            item.setProperty(key, str(kwargs[key]))
        return item

    def onAction(self, action):
        if not action.getId() in ACTION_ITEM_SELECT:
            if action in ACTION_CLOSE_LIST:
                self.close()

        if action in ACTION_ITEM_SELECT:
            cID = self.getFocusId()
            if cID == ACTION_LIST:
                l = self.getControl(cID)
                item = l.getSelectedItem()
                self.action = item.getProperty('id')
                self.close()
