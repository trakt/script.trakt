# -*- coding: utf-8 -*-
#

import pytest
import mock
import sys

xbmc_mock = mock.Mock()
sys.modules['xbmc'] = xbmc_mock
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
