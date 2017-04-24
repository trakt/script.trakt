# -*- coding: utf-8 -*-
#

import pytest
import mock
import sys

xbmc_mock = mock.Mock()
sys.modules['xbmc'] = xbmc_mock
xbmcgui_mock = mock.Mock()
sys.modules['xbmcgui'] = xbmcgui_mock
xbmcaddon_mock = mock.Mock()
sys.modules['xbmcaddon'] = xbmcaddon_mock
from resources.lib import kodiUtilities


def test_notification():
    assert not xbmc_mock.executebuiltin.called
    kodiUtilities.notification('header', 'message')
    assert xbmc_mock.executebuiltin.called


def test_showSettings():
    assert not xbmcaddon_mock.Addon().openSettings.called
    kodiUtilities.showSettings()
    assert xbmcaddon_mock.Addon().openSettings.called

    
def test_getProperty():
    assert not xbmcgui_mock.Window(10000).getProperty.called
    kodiUtilities.getProperty('setting')
    assert xbmcgui_mock.Window(10000).getProperty.called
