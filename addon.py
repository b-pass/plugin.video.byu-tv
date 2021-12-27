#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import re
import requests
import json
from urllib.parse import parse_qsl

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

API_BASE = 'https://api.byutv.org/api3'
API_HEADERS = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
    'x-byutv-context':'web$us',
    'x-byutv-platformkey':'xsaaw9c7y5',
    #'Referer':'https://www.byutv.org/',
    #'Origin':'https://www.byutv.org',
    #'Sec-Fetch-Mode':'cors',
    #'Sec-Fetch-Dest':'empty',
	#'Sec-Fetch-Site':'same-site',
}

def log(txt, *args, level=xbmc.LOGINFO):
    xbmc.log('byu-tv : ' + txt.format(*args), level=level)

def get_json(url, **params):
    if 'channel' not in params:
        params['channel'] = 'byutv'
    resp = requests.get(API_BASE + url, params=params, headers=API_HEADERS)
    if resp.status_code != 200:
        log('GET {} failed: code {}', url, resp.status_code)
        return {}
    else:
        return resp.json()

def list_categories():
    items = []
    # pageid 56c21af3-61cc-4b15-b21c-ec68762fcfeb = magic number for main category listing
    resp = get_json('/page/getpage', pageid='56c21af3-61cc-4b15-b21c-ec68762fcfeb')
    for cat in resp.get('lists', []):
        if cat.get('contentType', '') != 'Show':
            continue
        id = cat.get('id', '')
        if not id:
            continue
        item = xbmcgui.ListItem(label=cat['name'])
        item.setInfo('video', {'title':cat['name'], 'set':cat['name'], 'genre':cat['name'].split()})
        url = '{0}?action=category&id={1}'.format(PLUGIN_BASE, id)
        items.append((url, item, True))
    log('Listed {} categories', len(items))
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.endOfDirectory(HANDLE)

def getart(img):
    art = {}
    if img and 'images' in img[0] and img[0]['images'] and 'url' in img[0]['images'][0]:
        for i in img[0]['images']:
            if 'size' in i:
                if i['size'].startswith('512'):
                    art['poster'] = i['url']
                    art['banner'] = i['url']
                    art['fanart'] = i['url']
                elif i['size'].startswith('128x'):
                    art['icon'] = i['url']
    return art


def list_category(listid):
    items = []
    # start and limit are required, webapp uses 0,20
    # response has a "hasMore" key (boolean value) to indicate items over the limit
    resp = get_json('/list/getlistitems', listid=listid, start=0, limit=100)
    for show in resp.get('items', []):
        if show.get('type', '') != 'Show':
            continue

        id = show.get('target', {}).get('value', None)
        if not id:
            id = show.get('id', '')
            if not id:
                continue
        
        item = xbmcgui.ListItem(label=show['title'])
        if show.get('subtitle', ''):
            item.setLabel2(show['subtitle'])
        item.setArt(getart(show.get('images', [])))
        item.setInfo('video', {'title':show['title'], 'set':show['title'], 'setoverview':show.get('description', ''), 'mediatype':'tvshow'})
        url = '{0}?action=show&id={1}'.format(PLUGIN_BASE, id)
        items.append((url, item, True))
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.endOfDirectory(HANDLE)

def list_show(showid):
    # catalog/getshow?showid=<UUID> gives title/subtitle/description images, season count, episode count
    # ... but does not give the season list with season IDs
    items = []
    n = 0
    resp = get_json('/page/getpage', pageid=showid)
    for season in resp.get('lists', []):
        if season.get('type', '') != 'ShowSeason':
            continue
        n += 1
        id = season.get('id', '')
        if not id:
            continue
        
        item = xbmcgui.ListItem(label=season['name'])
        item.setInfo('video', {'title':season['name'], 'set':season['name'], 'setoverview':season['name'], 'season':n, 'mediatype':'season'})
        url = '{0}?action=season&id={1}&num={2}'.format(PLUGIN_BASE, id, n)
        items.append((url, item, True))
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.endOfDirectory(HANDLE)

def list_season(sid, snum):
    n = 0
    items = []

    # getpage for an episode just gives the title, nothing useful
    # start and limit are required, webapp uses 0,20
    # response has a "hasMore" key (boolean value) to indicate items over the limit
    resp = get_json('/list/getlistitems', listid=sid, start=0, limit=50)
    for ep in resp.get('items', []):
        if ep.get('type', '') != 'Episode':
            continue
    
        n += 1

        id = ep.get('target', {}).get('value', None)
        if not id:
            id = ep.get('id', '')
            if not id:
                continue
        
        item = xbmcgui.ListItem(label=ep['subtitle'])
        item.setArt(getart(ep.get('images', [])))
        dur = 0
        if 'videoLength' in ep:
            p = ep['videoLength'].split(':', 2)
            if len(p) >= 3:
                dur = int(p[0]) * 3600
                del p[0]
            if len(p) > 1:
                dur += int(p[0]) * 60
                del p[0]
            if len(p):
                dur += int(p[0])
        item.setInfo('video', {
            'title':ep['subtitle'], 
            'tvshowtitle':ep['title'],
            'plot':ep.get('description', ''),
            'duration': dur,
            'mediatype':'episode',
            'season':snum,
            'episode':n
        })
        item.setProperty('IsPlayable', 'true')
        url = '{0}?action=play&id={1}'.format(PLUGIN_BASE, id)
        items.append((url, item, False))
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    xbmcplugin.endOfDirectory(HANDLE)

def play_video(vid):
    vr = get_json('/catalog/getvideosforcontentv2', contentid=vid)
    if 'videos' in vr:
        vr = vr['videos']
        if 'dash1' in vr:
            vr = vr['dash1']
        elif 'dash' in vr:
            vr = vr['dash']
        else:
            log('No DASH section found in getvideosforcontentv2')
    
    if 'videoUrl' in vr:
        url = vr['videoUrl']
    else:
        log('No videoUrl :(')
        url = ''

    if url:
        mpdresp = requests.get(url, headers=API_HEADERS)
        m = re.search(r'"([^"]*/wv\?[^"]*)"', mpdresp.text)
        lic = m.group(1).replace('&amp;', '&')
        lic += '||R{SSM}|'

        item = xbmcgui.ListItem(path=url, offscreen=True)
        item.setProperty('inputstream','inputstream.adaptive')
        item.setProperty('inputstream.adaptive.manifest_type', 'mpd'')
        item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
        item.setProperty('inputstream.adaptive.license_key', lic)
        item.setMimeType('application/dash+xml')
        item.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(HANDLE, True, item)
    else:
        log('No video URL? vid={}, resp={}', vid, vr, level=xbmc.LOGERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem(path='', offscreen=True))

if __name__ == '__main__':
    PLUGIN_BASE = sys.argv[0]
    HANDLE = int(sys.argv[1])

    if len(sys.argv) > 2 and len(sys.argv[2]) > 1:
        args = dict(parse_qsl(sys.argv[2][1:]))
    else:
        args = {}
    
    action = args.get('action', None)
    if not action:
        list_categories()
    elif action == 'category':
        list_category(args.get('id'))
    elif action == 'show':
        list_show(args.get('id'))
    elif action == 'season':
        list_season(args.get('id'), int(args.get('n', 0)))
    elif action == 'play':
        play_video(args.get('id'))
    else:
        log('Unknown action in params: {}', args, level=xbmc.LOGERROR)
