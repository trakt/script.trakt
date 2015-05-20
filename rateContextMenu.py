# -*- coding: utf-8 -*-

import xbmc
import utilities

if __name__ == '__main__':
	xbmc.executebuiltin("RunScript(script.trakt,action=rate,media_type=%s,dbid=%s)" % (utilities.getMediaType(), xbmc.getInfoLabel("ListItem.DBID")))