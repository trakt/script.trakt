# -*- coding: utf-8 -*-

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
        return super(traktContextMenu, cls).__new__(cls, "script-trakt-ContextMenu.xml", __addon__.getAddonInfo('path'),
                                                    media_type=media_type, buttons=None)

    def __init__(self, *args, **kwargs):
        self.buttons = kwargs['buttons']
        self.media_type = kwargs['media_type']
        super(traktContextMenu, self).__init__()

    def onInit(self):
        lang = utils.getString
        mange_string = lang(32133) if utils.isMovie(self.media_type) else lang(32134)
        rate_string = lang(32137)
        if utils.isShow(self.media_type):
            rate_string = lang(32138)
        elif utils.isSeason(self.media_type):
            rate_string = lang(32149)
        elif utils.isEpisode(self.media_type):
            rate_string = lang(32139)

        actions = [mange_string, lang(32135), lang(32136), rate_string, lang(32140), lang(32141), lang(32142), lang(32143)]
        keys = ["itemlists", "removefromlist", "addtowatchlist", "rate", "togglewatched", "managelists", "updatetags",
                "sync"]

        l = self.getControl(ACTION_LIST)
        for i in range(len(actions)):
            if keys[i] in self.buttons:
                l.addItem(self.newListItem(actions[i], id=keys[i]))

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
                selected = not item.isSelected()
                self.action = item.getProperty('id')
                self.close()
