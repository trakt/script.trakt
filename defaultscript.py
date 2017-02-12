# -*- coding: utf-8 -*-
from resources.lib import script
import logging
import xbmcaddon

logger = logging.getLogger(__name__)

__addon__ = xbmcaddon.Addon("script.trakt")

def Main():
  script.run()

if __name__ == '__main__':
    Main()
